import gc
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

import joblib
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline

from src.config.settings import Settings, load_settings, logger
from src.dataset.builder import DatasetBuilder, get_feature_columns
from src.models.baseline import build_linear_regression, build_zero_baseline
from src.models.elastic_net import build_elastic_net_pipeline, get_elastic_net_param_candidates
from src.models.ridge import build_ridge_pipeline, get_ridge_param_candidates
from src.models.xgboost import (
    build_lightgbm_pipeline,
    build_random_forest_pipeline,
    build_xgboost_pipeline,
    get_gbdt_param_candidates,
)
from src.training.evaluation import (
    analyze_by_period,
    analyze_by_stock,
    build_prediction_analysis_table,
    compute_metrics,
)
from src.training.validation import WalkForwardValidator

MODEL_DISPLAY_NAMES = {
    "dummy": "ZeroBaseline",
    "linear_regression": "LinearRegression",
    "ridge": "Ridge",
    "elastic_net": "ElasticNet",
    "xgboost": "XGBoost",
    "lightgbm": "LightGBM",
    "random_forest": "RandomForest",
}


class ModelTrainer:
    """Orchestrates training, hyperparameter tuning, walk-forward evaluation, model selection, and persistence."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or load_settings()
        self.validator = WalkForwardValidator(self.settings)

    def make_model_factory(
        self,
        model_key: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Callable[[], Pipeline]:
        """Return a zero-argument callable that constructs a fresh Pipeline for `model_key`."""
        key = model_key.lower().strip()
        p = dict(params or {})
        seed = self.settings.training.random_seed

        if key in ("dummy", "baseline", "zero_baseline"):
            return build_zero_baseline
        if key in ("linear_regression", "linear"):
            return build_linear_regression
        if key == "ridge":
            alpha = float(p.get("alpha", self.settings.model.get("alpha", 1.0)))
            return lambda: build_ridge_pipeline(alpha=alpha, random_state=seed)
        if key == "elastic_net":
            alpha = float(p.get("alpha", 0.001))
            l1_ratio = float(p.get("l1_ratio", 0.5))
            return lambda: build_elastic_net_pipeline(alpha=alpha, l1_ratio=l1_ratio, random_state=seed)
        if key == "xgboost":
            return lambda: build_xgboost_pipeline(
                max_depth=int(p.get("max_depth", 4)),
                learning_rate=float(p.get("learning_rate", 0.05)),
                n_estimators=int(p.get("n_estimators", 150)),
                subsample=float(p.get("subsample", 0.8)),
                colsample_bytree=float(p.get("colsample_bytree", 0.8)),
                random_state=seed,
            )
        if key == "lightgbm":
            return lambda: build_lightgbm_pipeline(
                max_depth=int(p.get("max_depth", 4)),
                learning_rate=float(p.get("learning_rate", 0.05)),
                n_estimators=int(p.get("n_estimators", 150)),
                subsample=float(p.get("subsample", 0.8)),
                colsample_bytree=float(p.get("colsample_bytree", 0.8)),
                random_state=seed,
            )
        if key == "random_forest":
            return lambda: build_random_forest_pipeline(
                n_estimators=int(p.get("n_estimators", 100)),
                max_depth=int(p.get("max_depth", 8)),
                random_state=seed,
            )
        raise ValueError(f"Unsupported model type: '{model_key}'")

    def get_tuning_candidates(self, model_key: str) -> List[Dict[str, Any]]:
        """Return hyperparameter candidates for tuning on validation folds (Point 33)."""
        key = model_key.lower().strip()
        tuning_cfg = self.settings.tuning.get(key, {})

        if key == "ridge":
            alphas = tuning_cfg.get("alpha", [0.01, 0.1, 1.0, 10.0, 100.0])
            return get_ridge_param_candidates(alphas)
        if key == "elastic_net":
            alphas = tuning_cfg.get("alpha", [0.0005, 0.001, 0.005, 0.01])
            l1s = tuning_cfg.get("l1_ratio", [0.1, 0.5, 0.9])
            return get_elastic_net_param_candidates(alphas, l1s)
        if key in ("xgboost", "lightgbm"):
            return get_gbdt_param_candidates(
                max_depths=tuning_cfg.get("max_depth", [3, 5]),
                learning_rates=tuning_cfg.get("learning_rate", [0.05, 0.1]),
                n_estimators_list=tuning_cfg.get("n_estimators", [100, 200]),
                subsamples=tuning_cfg.get("subsample", [0.8]),
                colsample_bytrees=tuning_cfg.get("colsample_bytree", [0.8]),
            )
        return [{}]

    @staticmethod
    def compute_composite_selection_score(
        mean_metrics: Dict[str, float],
        stability: Dict[str, float],
        baseline_metrics: Optional[Dict[str, float]] = None,
    ) -> float:
        """Compute multi-criteria selection score (Point 56)."""
        mae = mean_metrics["mae"]
        rmse = mean_metrics["rmse"]
        dir_acc = mean_metrics["direction_accuracy"]
        pearson = mean_metrics["pearson"]

        base_mae = baseline_metrics["mae"] if baseline_metrics and baseline_metrics["mae"] > 0 else max(mae, 1e-6)
        base_rmse = (
            baseline_metrics["rmse"] if baseline_metrics and baseline_metrics["rmse"] > 0 else max(rmse, 1e-6)
        )

        rel_mae_gain = (base_mae - mae) / base_mae
        rel_rmse_gain = (base_rmse - rmse) / base_rmse

        fold_instability = stability.get("fold_mae_std", 0.0) / base_mae + stability.get(
            "fold_direction_acc_std", 0.0
        )
        period_instability = stability.get("period_direction_acc_std", 0.0)
        stock_dir_median = stability.get("stock_direction_acc_median", dir_acc)

        score = (
            0.30 * rel_mae_gain
            + 0.25 * rel_rmse_gain
            + 0.20 * (dir_acc - 0.50)
            + 0.15 * pearson
            + 0.10 * (stock_dir_median - 0.50)
            - 0.10 * (fold_instability + period_instability)
        )
        if abs(pearson) < 1e-6 and abs(mean_metrics.get("spearman", 0.0)) < 1e-6:
            score -= 0.15
        return float(score)

    def tune_and_validate_model(
        self,
        df: Union[pd.DataFrame, Path],
        model_key: str,
        target_col: str = "target_7d",
        feature_cols: Optional[Sequence[str]] = None,
        training_years: Optional[int] = None,
        tune_hyperparameters: bool = True,
        baseline_metrics: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """Tune hyperparameters on walk-forward validation folds (loading each fold once) and return best result."""
        t0 = time.perf_counter()
        display_name = MODEL_DISPLAY_NAMES.get(model_key.lower(), model_key)
        logger.info("Training & validating %s...", display_name)

        candidates = self.get_tuning_candidates(model_key) if tune_hyperparameters else [{}]
        cand_factories = [(p, self.make_model_factory(model_key, p)) for p in candidates]

        evaluated = self.validator.evaluate_candidates_walk_forward(
            data_source=df,
            candidate_factories=cand_factories,
            target_col=target_col,
            feature_cols=feature_cols,
            training_years=training_years,
        )

        best_result: Optional[Dict[str, Any]] = None
        best_params: Dict[str, Any] = {}
        best_score = -float("inf")

        for params, wf_res in evaluated:
            score = self.compute_composite_selection_score(
                wf_res["mean_metrics"],  # type: ignore[arg-type]
                wf_res["stability"],  # type: ignore[arg-type]
                baseline_metrics=baseline_metrics,
            )
            if best_result is None or score > best_score:
                best_score = score
                best_result = wf_res
                best_params = params

        assert best_result is not None
        elapsed = time.perf_counter() - t0
        m = best_result["mean_metrics"]
        logger.info("Model: %s (params=%s, time=%.2fs)", display_name, best_params, elapsed)
        logger.info("MAE: %.4f", m["mae"])
        logger.info("RMSE: %.4f", m["rmse"])
        logger.info("R2: %.4f", m["r2"])
        logger.info("Direction Accuracy: %.1f%%", m["direction_accuracy"] * 100.0)
        logger.info("Pearson: %.4f | Spearman: %.4f", m["pearson"], m["spearman"])

        return {
            "model_key": model_key.lower(),
            "model_name": display_name,
            "best_params": best_params,
            "selection_score": best_score,
            "training_time_sec": elapsed,
            **best_result,
        }

    def run_model_comparison_and_selection(
        self,
        df: Union[pd.DataFrame, Path],
        model_keys: Optional[Sequence[str]] = None,
        target_col: Optional[str] = None,
        feature_cols: Optional[Sequence[str]] = None,
        training_years: Optional[int] = None,
        tune_hyperparameters: bool = True,
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any]]:
        """Evaluate baseline and candidate ML models via walk-forward validation, select the best model,
        and evaluate the selected model on the final held-out test set.
        """
        eff_target = target_col or self.settings.target.target_col
        eff_years = training_years if training_years is not None else self.settings.training.years
        if feature_cols is not None:
            cols = list(feature_cols)
        elif isinstance(df, pd.DataFrame):
            cols = get_feature_columns(df)
        else:
            cols = get_feature_columns(pd.read_parquet(df).head(1))

        keys = list(model_keys or self.settings.models)

        baseline_res = self.tune_and_validate_model(
            df=df,
            model_key="dummy",
            target_col=eff_target,
            feature_cols=cols,
            training_years=eff_years,
            tune_hyperparameters=False,
        )
        baseline_metrics = baseline_res["mean_metrics"]

        all_results: List[Dict[str, Any]] = [baseline_res]
        ml_candidates: List[Dict[str, Any]] = []

        for key in keys:
            if key.lower() in ("dummy", "baseline", "zero_baseline"):
                continue
            res = self.tune_and_validate_model(
                df=df,
                model_key=key,
                target_col=eff_target,
                feature_cols=cols,
                training_years=eff_years,
                tune_hyperparameters=tune_hyperparameters,
                baseline_metrics=baseline_metrics,
            )
            all_results.append(res)
            ml_candidates.append(res)

        if not ml_candidates:
            raise ValueError("No ML candidate models were evaluated.")

        ml_candidates.sort(key=lambda r: r["selection_score"], reverse=True)
        best_candidate = ml_candidates[0]
        logger.info(
            "Selected best model: %s (selection_score=%.4f, params=%s)",
            best_candidate["model_name"],
            best_candidate["selection_score"],
            best_candidate["best_params"],
        )

        final_eval = self.fit_final_and_evaluate_test(
            df=df,
            model_key=best_candidate["model_key"],
            params=best_candidate["best_params"],
            target_col=eff_target,
            feature_cols=cols,
            training_years=eff_years,
        )
        return best_candidate, all_results, final_eval

    def fit_final_and_evaluate_test(
        self,
        df: Union[pd.DataFrame, Path],
        model_key: str,
        params: Dict[str, Any],
        target_col: str,
        feature_cols: Sequence[str],
        training_years: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Fit the chosen model on the pre-test training window and evaluate once on the held-out test set."""
        folds = self.validator.build_folds(df, training_years=training_years, include_test_fold=True)
        test_folds = [f for f in folds if f.is_test]
        needed_cols = list(dict.fromkeys(["stock_id", "datetime", target_col] + list(feature_cols)))

        if test_folds:
            test_fold = test_folds[-1]
            train_df, test_df = self.validator.slice_fold(df, test_fold, columns=needed_cols)
        else:
            if isinstance(df, (str, Path)):
                full_df = pd.read_parquet(df, columns=needed_cols)
            else:
                full_df = df
            train_df = full_df.iloc[: int(len(full_df) * 0.85)].reset_index(drop=True)
            test_df = full_df.iloc[int(len(full_df) * 0.85) :].reset_index(drop=True)

        X_train, y_train = DatasetBuilder.extract_xy(train_df, target_col=target_col, feature_cols=feature_cols)
        factory = self.make_model_factory(model_key, params)
        pipeline = factory()
        pipeline.fit(X_train, y_train)

        training_start = train_df["datetime"].min().strftime("%Y-%m-%d")
        training_end = train_df["datetime"].max().strftime("%Y-%m-%d")
        training_samples = len(train_df)
        del train_df, X_train, y_train
        gc.collect()

        test_metrics: Dict[str, float] = {}
        pred_table = pd.DataFrame()
        stock_report = pd.DataFrame()
        period_report = pd.DataFrame()

        if not test_df.empty:
            X_test, y_test = DatasetBuilder.extract_xy(test_df, target_col=target_col, feature_cols=feature_cols)
            y_pred = pipeline.predict(X_test)
            test_metrics = compute_metrics(y_test, y_pred)
            pred_table = build_prediction_analysis_table(test_df, y_test, y_pred)
            stock_report = analyze_by_stock(pred_table)
            period_report = analyze_by_period(pred_table)
            logger.info(
                "Final Test Set (%s..%s, %s samples) | MAE: %.4f | RMSE: %.4f | R2: %.4f | DirAcc: %.1f%% | Pearson: %.4f",
                test_df["datetime"].min().strftime("%Y-%m-%d"),
                test_df["datetime"].max().strftime("%Y-%m-%d"),
                f"{len(test_df):,}",
                test_metrics["mae"],
                test_metrics["rmse"],
                test_metrics["r2"],
                test_metrics["direction_accuracy"] * 100.0,
                test_metrics["pearson"],
            )

        return {
            "pipeline": pipeline,
            "training_start": training_start,
            "training_end": training_end,
            "training_samples": training_samples,
            "test_metrics": test_metrics,
            "test_prediction_table": pred_table,
            "test_stock_report": stock_report,
            "test_period_report": period_report,
        }

    def save_model(
        self,
        pipeline: Pipeline,
        model_key: str,
        model_name: str,
        params: Dict[str, Any],
        feature_cols: Sequence[str],
        training_start: str,
        training_end: str,
        validation_metrics: Dict[str, float],
        test_metrics: Optional[Dict[str, float]] = None,
        fold_metrics: Optional[List[Dict[str, Any]]] = None,
        stability: Optional[Dict[str, float]] = None,
        target_horizon: Optional[int] = None,
        lookback: Optional[int] = None,
        training_years: Optional[int] = None,
        output_dir: Optional[Path] = None,
    ) -> Dict[str, Path]:
        """Save trained Pipeline (scaler + model) to model.joblib and reproducibility info to metadata.json."""
        eff_horizon = int(target_horizon if target_horizon is not None else self.settings.target.horizon)
        eff_lookback = int(lookback if lookback is not None else self.settings.features.lookback)
        eff_years = int(training_years if training_years is not None else self.settings.training.years)

        base_models_dir = Path(output_dir or self.settings.models_dir)
        model_dir = base_models_dir / model_key.lower()
        model_dir.mkdir(parents=True, exist_ok=True)

        model_path = model_dir / "model.joblib"
        metadata_path = model_dir / "metadata.json"

        try:
            if model_path.exists():
                model_path.unlink()
            joblib.dump(pipeline, model_path)
        except PermissionError:
            alt_path = model_dir / f"model_{int(time.time())}.joblib"
            joblib.dump(pipeline, alt_path)
            try:
                alt_path.replace(model_path)
            except PermissionError:
                model_path = alt_path

        metadata = {
            "model": model_name,
            "model_key": model_key.lower(),
            "model_version": "1.0.0",
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "random_seed": self.settings.training.random_seed,
            "model_parameters": params,
            "target": f"target_{eff_horizon}d",
            "target_horizon": eff_horizon,
            "lookback": eff_lookback,
            "training_years": eff_years,
            "training_start": training_start,
            "training_end": training_end,
            "features": list(feature_cols),
            "metrics": validation_metrics,
            "test_metrics": test_metrics or {},
            "fold_metrics": fold_metrics or [],
            "stability": stability or {},
        }
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=4)

        logger.info("Model saved to %s (metadata: %s)", model_path, metadata_path)
        return {"model_path": model_path, "metadata_path": metadata_path}

    def run_experiments_grid(
        self,
        raw_df: pd.DataFrame,
        horizons: Sequence[int] = (1, 3, 5, 7, 10),
        lookbacks: Sequence[int] = (5, 10, 20, 30, 60),
        training_periods: Sequence[int] = (1, 2, 3, 5),
        models: Sequence[str] = ("linear_regression", "ridge", "elastic_net", "xgboost", "lightgbm"),
        save_path: Optional[Path] = None,
    ) -> pd.DataFrame:
        """Run systematic experiments across horizons, lookbacks, training periods, and models (Point 55)."""
        builder = DatasetBuilder(self.settings)
        records: List[Dict[str, Any]] = []

        for h in horizons:
            for lb in lookbacks:
                proc_df = builder.process_dataframe(
                    raw_df,
                    horizon=h,
                    lookback=lb,
                    drop_incomplete=True,
                    require_target=True,
                    validate_input=True,
                )
                if proc_df.empty:
                    continue
                target_col = f"target_{h}d"
                feat_cols = get_feature_columns(proc_df)

                for tp in training_periods:
                    for m_key in models:
                        factory = self.make_model_factory(m_key)
                        wf = self.validator.evaluate_model_walk_forward(
                            df=proc_df,
                            model_builder_fn=factory,
                            target_col=target_col,
                            feature_cols=feat_cols,
                            training_years=tp,
                        )
                        mm = wf["mean_metrics"]
                        records.append(
                            {
                                "model": MODEL_DISPLAY_NAMES.get(m_key.lower(), m_key),
                                "horizon": int(h),
                                "lookback": int(lb),
                                "training_period": f"{tp}y",
                                "MAE": mm["mae"],
                                "RMSE": mm["rmse"],
                                "R2": mm["r2"],
                                "direction_accuracy": mm["direction_accuracy"],
                                "pearson": mm["pearson"],
                                "spearman": mm["spearman"],
                            }
                        )

        exp_df = pd.DataFrame(records)
        out_file = save_path or (self.settings.experiments_dir / "experiments_results.csv")
        out_file.parent.mkdir(parents=True, exist_ok=True)
        exp_df.to_csv(out_file, index=False)
        logger.info("Saved %d experiment results to %s", len(exp_df), out_file)
        return exp_df
