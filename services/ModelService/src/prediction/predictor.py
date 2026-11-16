import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import joblib
import numpy as np
import pandas as pd

from src.config.settings import Settings, load_settings, logger
from src.data.loader import DataLoader
from src.dataset.builder import DatasetBuilder


class StockPredictor:
    """Loads a persisted model pipeline and metadata to perform single-stock, multi-stock, and ranked predictions."""

    def __init__(
        self,
        model_dir: Optional[Path] = None,
        model_key: Optional[str] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        self.settings = settings or load_settings()
        self.model_dir = self._resolve_model_dir(model_dir, model_key)
        self.model_path = self.model_dir / "model.joblib"
        self.metadata_path = self.model_dir / "metadata.json"

        if not self.model_path.exists() or not self.metadata_path.exists():
            raise FileNotFoundError(
                f"Persisted model or metadata not found in {self.model_dir}. Run training first."
            )

        self.pipeline = joblib.load(self.model_path)
        with open(self.metadata_path, "r", encoding="utf-8") as f:
            self.metadata: Dict[str, Any] = json.load(f)

        self.feature_cols: List[str] = list(self.metadata["features"])
        self.horizon: int = int(self.metadata.get("target_horizon", self.settings.target.horizon))
        self.lookback: int = int(self.metadata.get("lookback", self.settings.features.lookback))
        self.builder = DatasetBuilder(self.settings)

    def _resolve_model_dir(self, model_dir: Optional[Path], model_key: Optional[str]) -> Path:
        if model_dir is not None:
            return Path(model_dir)
        base = self.settings.models_dir
        if model_key:
            candidate = base / model_key.lower()
            if (candidate / "model.joblib").exists():
                return candidate
        # Prefer default configured model type if saved, otherwise pick most recently saved model
        default_dir = base / str(self.settings.model.get("type", "ridge")).lower()
        if (default_dir / "model.joblib").exists():
            return default_dir

        if base.exists():
            subdirs = [
                d for d in base.iterdir() if d.is_dir() and (d / "model.joblib").exists()
            ]
            if subdirs:
                subdirs.sort(key=lambda d: (d / "model.joblib").stat().st_mtime, reverse=True)
                return subdirs[0]
        return default_dir

    def predict_from_dataframe(self, raw_history_df: pd.DataFrame) -> pd.DataFrame:
        """Transform raw historical records into features + lags and predict return for the latest row of each stock_id."""
        if raw_history_df.empty:
            return pd.DataFrame(
                columns=["stock_id", "datetime", "horizon", "predicted_return", "predicted_direction"]
            )

        processed = self.builder.process_dataframe(
            raw_history_df,
            horizon=self.horizon,
            lookback=self.lookback,
            drop_incomplete=True,
            require_target=False,
            validate_input=False,
        )
        if processed.empty:
            return pd.DataFrame(
                columns=["stock_id", "datetime", "horizon", "predicted_return", "predicted_direction"]
            )

        # Keep only the latest session for each stock_id
        latest_df = (
            processed.sort_values(["stock_id", "datetime"], ascending=[True, True])
            .groupby("stock_id", as_index=False)
            .tail(1)
            .reset_index(drop=True)
        )

        missing_feats = [c for c in self.feature_cols if c not in latest_df.columns]
        if missing_feats:
            raise ValueError(f"Engineered data is missing model features: {missing_feats}")

        X_latest = latest_df[self.feature_cols].copy()
        preds = np.asarray(self.pipeline.predict(X_latest), dtype=np.float64)

        result = pd.DataFrame(
            {
                "stock_id": latest_df["stock_id"].astype(int),
                "datetime": pd.to_datetime(latest_df["datetime"]).dt.strftime("%Y-%m-%d"),
                "horizon": self.horizon,
                "predicted_return": preds,
                "predicted_direction": np.where(preds >= 0.0, "UP", "DOWN"),
            }
        )
        return result

    def predict_for_stock(
        self,
        stock_id: int,
        loader: Optional[DataLoader] = None,
        lookback_days: int = 120,
    ) -> Dict[str, Any]:
        """Fetch recent history for a single stock_id from PostgreSQL and return its predicted return."""
        own_loader = loader is None
        data_loader = loader or DataLoader(settings=self.settings)
        try:
            raw_df = data_loader.load_latest_stock_history(
                stock_ids=[int(stock_id)],
                lookback_days=max(lookback_days, self.lookback * 3),
            )
            if raw_df.empty:
                raise ValueError(f"No historical data found in PostgreSQL for stock_id={stock_id}")

            pred_df = self.predict_from_dataframe(raw_df)
            if pred_df.empty:
                raise ValueError(
                    f"Insufficient recent history to compute all lag features for stock_id={stock_id}"
                )

            row = pred_df.iloc[-1]
            return {
                "stock_id": int(row["stock_id"]),
                "datetime": str(row["datetime"]),
                "horizon": int(row["horizon"]),
                "predicted_return": round(float(row["predicted_return"]), 6),
                "predicted_direction": str(row["predicted_direction"]),
            }
        finally:
            if own_loader:
                data_loader.db.close()

    def predict_for_multiple_stocks(
        self,
        stock_ids: Optional[Sequence[int]] = None,
        max_stocks: Optional[int] = 100,
        loader: Optional[DataLoader] = None,
        lookback_days: int = 120,
    ) -> pd.DataFrame:
        """Predict returns for multiple stocks in memory-controlled chunks (Point 43)."""
        own_loader = loader is None
        data_loader = loader or DataLoader(settings=self.settings)
        try:
            if stock_ids is None:
                stock_ids = data_loader.get_available_stock_ids(
                    start_date="2025-01-01",
                    min_rows=max(self.lookback + 25, 45),
                    limit=max_stocks,
                )

            raw_df = data_loader.load_latest_stock_history(
                stock_ids=stock_ids,
                lookback_days=max(lookback_days, self.lookback * 3),
            )
            return self.predict_from_dataframe(raw_df)
        finally:
            if own_loader:
                data_loader.db.close()

    def build_stock_ranking(
        self,
        stock_ids: Optional[Sequence[int]] = None,
        max_stocks: Optional[int] = 100,
        loader: Optional[DataLoader] = None,
    ) -> pd.DataFrame:
        """Create a ranked table of stocks sorted by predicted_return DESC (Point 44)."""
        preds_df = self.predict_for_multiple_stocks(
            stock_ids=stock_ids,
            max_stocks=max_stocks,
            loader=loader,
        )
        if preds_df.empty:
            return preds_df

        ranked = preds_df.sort_values("predicted_return", ascending=False).reset_index(drop=True)
        ranked["predicted_return_pct"] = ranked["predicted_return"].map(lambda x: f"{x:+.2%}")
        return ranked
