import gc
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd

from src.config.settings import Settings, load_settings, logger
from src.dataset.builder import DatasetBuilder, get_feature_columns
from src.training.evaluation import (
    analyze_by_period,
    analyze_by_stock,
    build_prediction_analysis_table,
    compute_metrics,
)


@dataclass
class WalkForwardFold:
    name: str
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    eval_start: pd.Timestamp
    eval_end: pd.Timestamp
    is_test: bool = False


class WalkForwardValidator:
    """Implements walk-forward validation across chronological folds and configurable training windows.
    Supports both in-memory DataFrames and disk-backed Parquet datasets for bounded-RAM execution.
    """

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or load_settings()

    def _get_date_bounds(self, data_source: Union[pd.DataFrame, Path]) -> Tuple[pd.Timestamp, pd.Timestamp]:
        if isinstance(data_source, (str, Path)):
            dt_df = pd.read_parquet(data_source, columns=["datetime"])
            dt_series = pd.to_datetime(dt_df["datetime"])
            return dt_series.min(), dt_series.max()
        dt_series = pd.to_datetime(data_source["datetime"])
        return dt_series.min(), dt_series.max()

    def build_folds(
        self,
        data_source: Union[pd.DataFrame, Path],
        training_years: Optional[int] = None,
        include_test_fold: bool = False,
    ) -> List[WalkForwardFold]:
        """Build chronological walk-forward folds, applying `training_years` lookback window if specified."""
        min_dt, max_dt = self._get_date_bounds(data_source)

        raw_folds = self.settings.validation.folds or [
            {
                "name": "Fold_1",
                "train_start": "2019-01-01",
                "train_end": "2022-12-31",
                "val_start": "2023-01-01",
                "val_end": "2023-12-31",
            },
            {
                "name": "Fold_2",
                "train_start": "2019-01-01",
                "train_end": "2023-12-31",
                "val_start": "2024-01-01",
                "val_end": "2024-12-31",
            },
            {
                "name": "Fold_3",
                "train_start": "2019-01-01",
                "train_end": "2024-12-31",
                "val_start": "2025-01-01",
                "val_end": "2025-12-31",
            },
        ]

        folds: List[WalkForwardFold] = []
        for rf in raw_folds:
            t_end = pd.Timestamp(rf["train_end"])
            if training_years is not None and training_years > 0:
                t_start = max(
                    min_dt,
                    t_end - pd.DateOffset(years=int(training_years)) + pd.Timedelta(days=1),
                )
            else:
                t_start = max(min_dt, pd.Timestamp(rf["train_start"]))

            v_start = pd.Timestamp(rf["val_start"])
            v_end = pd.Timestamp(rf["val_end"])
            if v_start <= max_dt and t_end >= min_dt:
                folds.append(
                    WalkForwardFold(
                        name=rf["name"],
                        train_start=t_start,
                        train_end=t_end,
                        eval_start=v_start,
                        eval_end=v_end,
                        is_test=False,
                    )
                )

        if include_test_fold:
            test_cfg = self.settings.validation.test_period or {
                "train_start": "2019-01-01",
                "train_end": "2025-12-31",
                "test_start": "2026-01-01",
                "test_end": "2026-12-31",
            }
            t_end = pd.Timestamp(test_cfg["train_end"])
            if training_years is not None and training_years > 0:
                t_start = max(
                    min_dt,
                    t_end - pd.DateOffset(years=int(training_years)) + pd.Timedelta(days=1),
                )
            else:
                t_start = max(min_dt, pd.Timestamp(test_cfg["train_start"]))
            test_start = pd.Timestamp(test_cfg["test_start"])
            test_end = pd.Timestamp(test_cfg["test_end"])
            if test_start <= max_dt:
                folds.append(
                    WalkForwardFold(
                        name="Fold_4_Test",
                        train_start=t_start,
                        train_end=t_end,
                        eval_start=test_start,
                        eval_end=test_end,
                        is_test=True,
                    )
                )

        # Fallback dynamic walk-forward splits for synthetic/short datasets in unit tests
        if not folds and isinstance(data_source, pd.DataFrame):
            dt_series = pd.to_datetime(data_source["datetime"])
            unique_dates = np.sort(dt_series.unique())
            n_dates = len(unique_dates)
            if n_dates >= 6:
                s1 = int(n_dates * 0.5)
                s2 = int(n_dates * 0.7)
                s3 = int(n_dates * 0.85)
                folds = [
                    WalkForwardFold(
                        name="Fold_1",
                        train_start=pd.Timestamp(unique_dates[0]),
                        train_end=pd.Timestamp(unique_dates[s1 - 1]),
                        eval_start=pd.Timestamp(unique_dates[s1]),
                        eval_end=pd.Timestamp(unique_dates[s2 - 1]),
                        is_test=False,
                    ),
                    WalkForwardFold(
                        name="Fold_2",
                        train_start=pd.Timestamp(unique_dates[0]),
                        train_end=pd.Timestamp(unique_dates[s2 - 1]),
                        eval_start=pd.Timestamp(unique_dates[s2]),
                        eval_end=pd.Timestamp(unique_dates[s3 - 1]),
                        is_test=False,
                    ),
                ]
                if include_test_fold:
                    folds.append(
                        WalkForwardFold(
                            name="Fold_3_Test",
                            train_start=pd.Timestamp(unique_dates[0]),
                            train_end=pd.Timestamp(unique_dates[s3 - 1]),
                            eval_start=pd.Timestamp(unique_dates[s3]),
                            eval_end=pd.Timestamp(unique_dates[-1]),
                            is_test=True,
                        )
                    )

        return folds

    @staticmethod
    def slice_fold(
        data_source: Union[pd.DataFrame, Path],
        fold: WalkForwardFold,
        columns: Optional[Sequence[str]] = None,
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Return (train_df, eval_df) for a walk-forward fold with strict date separation."""
        if isinstance(data_source, (str, Path)):
            read_cols = list(columns) if columns is not None else None
            train_df = pd.read_parquet(
                data_source,
                columns=read_cols,
                filters=[
                    ("datetime", ">=", fold.train_start),
                    ("datetime", "<=", fold.train_end),
                ],
            )
            eval_df = pd.read_parquet(
                data_source,
                columns=read_cols,
                filters=[
                    ("datetime", ">=", fold.eval_start),
                    ("datetime", "<=", fold.eval_end),
                ],
            )
        else:
            dt = pd.to_datetime(data_source["datetime"])
            train_mask = (dt >= fold.train_start) & (dt <= fold.train_end)
            eval_mask = (dt >= fold.eval_start) & (dt <= fold.eval_end)
            train_df = data_source.loc[train_mask].reset_index(drop=True)
            eval_df = data_source.loc[eval_mask].reset_index(drop=True)

        if not train_df.empty and not eval_df.empty:
            assert train_df["datetime"].max() < eval_df["datetime"].min(), (
                f"Data leakage in {fold.name}: train_end >= eval_start"
            )
        return train_df, eval_df

    @staticmethod
    def summarize_candidate_predictions(
        fold_metrics_list: List[Dict[str, object]],
        pred_tables: List[pd.DataFrame],
    ) -> Dict[str, object]:
        all_preds = pd.concat(pred_tables, ignore_index=True)
        overall_metrics = compute_metrics(all_preds["actual_return"], all_preds["predicted_return"])

        fold_df = pd.DataFrame(fold_metrics_list)
        stock_report = analyze_by_stock(all_preds)
        period_report = analyze_by_period(all_preds)

        stability = {
            "fold_mae_std": float(fold_df["mae"].std(ddof=0)) if len(fold_df) > 1 else 0.0,
            "fold_rmse_std": float(fold_df["rmse"].std(ddof=0)) if len(fold_df) > 1 else 0.0,
            "fold_direction_acc_std": float(fold_df["direction_accuracy"].std(ddof=0)) if len(fold_df) > 1 else 0.0,
            "fold_min_direction_acc": float(fold_df["direction_accuracy"].min()),
            "stock_direction_acc_median": float(stock_report["direction_accuracy"].median())
            if not stock_report.empty
            else 0.0,
            "stock_mae_iqr": float(
                stock_report["MAE"].quantile(0.75) - stock_report["MAE"].quantile(0.25)
            )
            if not stock_report.empty
            else 0.0,
            "period_direction_acc_std": float(period_report["direction_accuracy"].std(ddof=0))
            if len(period_report) > 1
            else 0.0,
        }

        return {
            "mean_metrics": overall_metrics,
            "fold_metrics": fold_metrics_list,
            "stability": stability,
            "prediction_table": all_preds,
            "stock_report": stock_report,
            "period_report": period_report,
        }

    def evaluate_candidates_walk_forward(
        self,
        data_source: Union[pd.DataFrame, Path],
        candidate_factories: Sequence[Tuple[Dict[str, Any], Callable[[], Any]]],
        target_col: str = "target_7d",
        feature_cols: Optional[Sequence[str]] = None,
        training_years: Optional[int] = None,
    ) -> List[Tuple[Dict[str, Any], Dict[str, object]]]:
        """Evaluate one or more hyperparameter candidates across all walk-forward folds,
        loading each fold once and freeing memory between folds.
        """
        if feature_cols is None:
            if isinstance(data_source, pd.DataFrame):
                cols = get_feature_columns(data_source)
            else:
                sample_df = pd.read_parquet(data_source).head(1)
                cols = get_feature_columns(sample_df)
        else:
            cols = list(feature_cols)

        folds = self.build_folds(data_source, training_years=training_years, include_test_fold=False)
        needed_cols = list(dict.fromkeys(["stock_id", "datetime", target_col] + cols))

        per_cand_folds: List[List[Dict[str, object]]] = [[] for _ in candidate_factories]
        per_cand_preds: List[List[pd.DataFrame]] = [[] for _ in candidate_factories]

        for fold in folds:
            train_df, val_df = self.slice_fold(data_source, fold, columns=needed_cols)
            if train_df.empty or val_df.empty:
                continue

            X_train, y_train = DatasetBuilder.extract_xy(train_df, target_col=target_col, feature_cols=cols)
            X_val, y_val = DatasetBuilder.extract_xy(val_df, target_col=target_col, feature_cols=cols)
            val_meta_df = val_df[["datetime", "stock_id"]].copy()
            del train_df, val_df
            gc.collect()

            for idx, (_, factory) in enumerate(candidate_factories):
                pipeline = factory()
                pipeline.fit(X_train, y_train)
                y_pred = np.asarray(pipeline.predict(X_val), dtype=np.float32)

                m = compute_metrics(y_val, y_pred)
                m_record: Dict[str, object] = {
                    "fold": fold.name,
                    "train_start": fold.train_start.strftime("%Y-%m-%d"),
                    "train_end": fold.train_end.strftime("%Y-%m-%d"),
                    "val_start": fold.eval_start.strftime("%Y-%m-%d"),
                    "val_end": fold.eval_end.strftime("%Y-%m-%d"),
                    "train_samples": len(X_train),
                    "val_samples": len(X_val),
                    **m,
                }
                per_cand_folds[idx].append(m_record)
                per_cand_preds[idx].append(build_prediction_analysis_table(val_meta_df, y_val, y_pred))
                del pipeline, y_pred
                gc.collect()

            del X_train, y_train, X_val, y_val, val_meta_df
            gc.collect()

        if not per_cand_folds or not per_cand_folds[0]:
            raise ValueError("No valid walk-forward folds had both training and validation samples.")

        results: List[Tuple[Dict[str, Any], Dict[str, object]]] = []
        for idx, (params, _) in enumerate(candidate_factories):
            summary = self.summarize_candidate_predictions(per_cand_folds[idx], per_cand_preds[idx])
            results.append((params, summary))
        return results

    def evaluate_model_walk_forward(
        self,
        df: Union[pd.DataFrame, Path],
        model_builder_fn: Callable[[], Any],
        target_col: str = "target_7d",
        feature_cols: Optional[Sequence[str]] = None,
        training_years: Optional[int] = None,
    ) -> Dict[str, object]:
        """Run walk-forward validation across all validation folds for a single model builder."""
        res = self.evaluate_candidates_walk_forward(
            data_source=df,
            candidate_factories=[({}, model_builder_fn)],
            target_col=target_col,
            feature_cols=feature_cols,
            training_years=training_years,
        )
        return res[0][1]
