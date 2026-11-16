import argparse
from typing import Optional

from src.config.settings import load_settings, logger
from src.data.database import DatabaseManager
from src.data.loader import DataLoader
from src.dataset.builder import DatasetBuilder
from src.prediction.predictor import StockPredictor
from src.training.trainer import ModelTrainer


def run_training_pipeline(
    max_stocks: Optional[int] = None,
    horizon: Optional[int] = None,
    lookback: Optional[int] = None,
    training_years: Optional[int] = None,
    tune: bool = True,
    reuse_parquet: bool = False,
) -> dict:
    """Execute the complete Stock Prediction ML Pipeline end-to-end with bounded memory."""
    settings = load_settings()
    if max_stocks is not None:
        settings.data.max_stocks = max_stocks
    if horizon is not None:
        settings.target.horizon = horizon
        settings.training.target_horizon = horizon
    if lookback is not None:
        settings.features.lookback = lookback
        settings.training.lookback = lookback
    if training_years is not None:
        settings.training.years = training_years
        settings.training.training_years = training_years

    out_dir = settings.data.processed_dir
    dataset_parquet_path = out_dir / "dataset.parquet"

    if reuse_parquet and dataset_parquet_path.exists():
        import pandas as pd
        from src.dataset.builder import get_feature_columns

        logger.info("Reusing existing full Parquet dataset at %s", dataset_parquet_path)
        parquet_paths = {
            "dataset": dataset_parquet_path,
            "train": out_dir / "train.parquet",
            "validation": out_dir / "validation.parquet",
            "test": out_dir / "test.parquet",
        }
        sample_df = pd.read_parquet(dataset_parquet_path).head(1)
        feature_cols = get_feature_columns(sample_df)
    else:
        db = DatabaseManager(settings.database)
        try:
            db.check_and_ensure_indexes(create_if_missing=True)
            loader = DataLoader(db_manager=db, settings=settings)
            builder = DatasetBuilder(settings=settings)

            stream_info = builder.build_and_stream_to_parquet(
                loader=loader,
                max_stocks=settings.data.max_stocks,
                horizon=settings.target.horizon,
                lookback=settings.features.lookback,
            )
            parquet_paths = stream_info["paths"]  # type: ignore[assignment]
            feature_cols = stream_info["feature_cols"]  # type: ignore[assignment]
            dataset_parquet_path = parquet_paths["dataset"]
        finally:
            db.close()

    trainer = ModelTrainer(settings=settings)
    best_candidate, all_results, final_eval = trainer.run_model_comparison_and_selection(
        df=dataset_parquet_path,
        target_col=settings.target.target_col,
        feature_cols=feature_cols,
        training_years=settings.training.years,
        tune_hyperparameters=tune,
    )

    saved_paths = trainer.save_model(
        pipeline=final_eval["pipeline"],
        model_key=best_candidate["model_key"],
        model_name=best_candidate["model_name"],
        params=best_candidate["best_params"],
        feature_cols=feature_cols,
        training_start=final_eval["training_start"],
        training_end=final_eval["training_end"],
        validation_metrics=best_candidate["mean_metrics"],
        test_metrics=final_eval["test_metrics"],
        fold_metrics=best_candidate["fold_metrics"],
        stability=best_candidate["stability"],
        target_horizon=settings.target.horizon,
        lookback=settings.features.lookback,
        training_years=settings.training.years,
    )

    if best_candidate["model_key"] != "ridge":
        ridge_candidates = [r for r in all_results if r["model_key"] == "ridge"]
        if ridge_candidates:
            rc = ridge_candidates[0]
            ridge_eval = trainer.fit_final_and_evaluate_test(
                df=dataset_parquet_path,
                model_key="ridge",
                params=rc["best_params"],
                target_col=settings.target.target_col,
                feature_cols=feature_cols,
                training_years=settings.training.years,
            )
            trainer.save_model(
                pipeline=ridge_eval["pipeline"],
                model_key="ridge",
                model_name="Ridge",
                params=rc["best_params"],
                feature_cols=feature_cols,
                training_start=ridge_eval["training_start"],
                training_end=ridge_eval["training_end"],
                validation_metrics=rc["mean_metrics"],
                test_metrics=ridge_eval["test_metrics"],
                fold_metrics=rc["fold_metrics"],
                stability=rc["stability"],
                target_horizon=settings.target.horizon,
                lookback=settings.features.lookback,
                training_years=settings.training.years,
            )

    exp_dir = settings.experiments_dir
    exp_dir.mkdir(parents=True, exist_ok=True)
    if not final_eval["test_prediction_table"].empty:
        final_eval["test_prediction_table"].to_parquet(
            exp_dir / "test_predictions.parquet", index=False
        )
        final_eval["test_stock_report"].to_csv(exp_dir / "stock_analysis_report.csv", index=False)
        final_eval["test_period_report"].to_csv(exp_dir / "period_analysis_report.csv", index=False)

    best_candidate["period_report"].to_csv(
        exp_dir / "validation_period_analysis_report.csv", index=False
    )
    best_candidate["stock_report"].to_csv(
        exp_dir / "validation_stock_analysis_report.csv", index=False
    )

    return {
        "best_candidate": best_candidate,
        "all_results": all_results,
        "final_eval": final_eval,
        "parquet_paths": parquet_paths,
        "saved_paths": saved_paths,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Stock Prediction ML Pipeline CLI")
    subparsers = parser.add_subparsers(dest="command", required=False)

    train_p = subparsers.add_parser("train", help="Run full training and walk-forward validation pipeline")
    train_p.add_argument("--max-stocks", type=int, default=None, help="Limit number of stocks loaded")
    train_p.add_argument("--horizon", type=int, default=None, help="Target horizon in sessions (1,3,5,7,10)")
    train_p.add_argument("--lookback", type=int, default=None, help="Feature lookback sessions")
    train_p.add_argument("--training-years", type=int, default=None, help="Training window in years (1,2,3,5)")
    train_p.add_argument("--no-tune", action="store_true", help="Disable hyperparameter grid tuning")
    train_p.add_argument("--reuse-parquet", action="store_true", help="Reuse existing data/processed/dataset.parquet")

    pred_p = subparsers.add_parser("predict", help="Predict future return for a single stock_id")
    pred_p.add_argument("--stock-id", type=int, required=True, help="Target stock_id")
    pred_p.add_argument("--model", type=str, default=None, help="Optional model key (e.g. ridge)")

    rank_p = subparsers.add_parser("rank", help="Predict and rank multiple stocks")
    rank_p.add_argument("--max-stocks", type=int, default=50, help="Number of stocks to rank")
    rank_p.add_argument("--top", type=int, default=15, help="Display top N stocks")
    rank_p.add_argument("--model", type=str, default=None, help="Optional model key")

    exp_p = subparsers.add_parser("experiments", help="Run multi-configuration experiment grid")
    exp_p.add_argument("--max-stocks", type=int, default=30, help="Number of stocks for experiment grid")

    serve_p = subparsers.add_parser("serve", help="Run FastAPI prediction server")
    serve_p.add_argument("--host", type=str, default="0.0.0.0")
    serve_p.add_argument("--port", type=int, default=8000)

    args = parser.parse_args()
    cmd = args.command or "train"

    if cmd == "train":
        run_training_pipeline(
            max_stocks=getattr(args, "max_stocks", None),
            horizon=getattr(args, "horizon", None),
            lookback=getattr(args, "lookback", None),
            training_years=getattr(args, "training_years", None),
            tune=not getattr(args, "no_tune", False),
            reuse_parquet=getattr(args, "reuse_parquet", False),
        )
    elif cmd == "predict":
        predictor = StockPredictor(model_key=args.model)
        result = predictor.predict_for_stock(stock_id=args.stock_id)
        logger.info(
            "Prediction for stock_id=%d (date=%s, horizon=%dd): %+.4f (%+.2f%%) [%s]",
            result["stock_id"],
            result["datetime"],
            result["horizon"],
            result["predicted_return"],
            result["predicted_return"] * 100.0,
            result["predicted_direction"],
        )
    elif cmd == "rank":
        predictor = StockPredictor(model_key=args.model)
        ranking_df = predictor.build_stock_ranking(max_stocks=args.max_stocks)
        print(ranking_df.head(args.top).to_string(index=False))
    elif cmd == "experiments":
        settings = load_settings()
        loader = DataLoader(settings=settings)
        try:
            raw_df = loader.load_data(max_stocks=args.max_stocks)
            trainer = ModelTrainer(settings=settings)
            exp_df = trainer.run_experiments_grid(raw_df=raw_df)
            print(exp_df.head(20).to_string(index=False))
        finally:
            loader.db.close()
    elif cmd == "serve":
        import uvicorn

        uvicorn.run("src.api:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
