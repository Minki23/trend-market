import gc
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from src.config.settings import Settings, load_settings, logger
from src.data.loader import DataLoader
from src.data.validation import DataValidator, sort_stock_data
from src.features.lag_features import DEFAULT_LAG_COLUMNS, DEFAULT_LAGS, add_lag_features
from src.features.returns import DEFAULT_RETURN_WINDOWS, add_return_features
from src.features.technical import add_all_technical_features
from src.features.volatility import DEFAULT_VOLATILITY_WINDOWS, add_volatility_features

ALLOWED_HORIZONS: tuple[int, ...] = (1, 3, 5, 7, 10)

NON_FEATURE_COLUMNS = {
    "indicator_id",
    "stock_id",
    "datetime",
    "ticker",
    "sector",
    "market",
}


def generate_target(
    df: pd.DataFrame,
    horizon: int = 7,
    price_col: str = "close",
) -> pd.DataFrame:
    """Compute forward return target_{horizon}d = close[t + horizon] / close[t] - 1 per stock_id."""
    if horizon <= 0:
        raise ValueError(f"Target horizon must be positive, got {horizon}.")
    if df.empty or price_col not in df.columns:
        return df.copy()

    out = df.copy()
    grouped_close = out.groupby("stock_id", sort=False)[price_col]
    future_close = grouped_close.shift(-int(horizon))
    target_col = f"target_{int(horizon)}d"
    out[target_col] = np.where(out[price_col] > 0, (future_close / out[price_col]) - 1.0, np.nan)
    return out


def add_stock_profile_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add leakage-free historical company characteristics so global models distinguish stock profiles
    without treating raw stock_id as an arbitrary continuous number (Point 26).
    """
    if df.empty:
        return df.copy()

    out = df.copy()
    if "close" in out.columns:
        out["stock_log_price"] = np.log1p(np.maximum(out["close"], 0.0))
    if "volume" in out.columns:
        log_vol = np.log1p(np.maximum(out["volume"].astype(np.float64), 0.0))
        out["stock_log_volume_ma_20"] = (
            log_vol.groupby(out["stock_id"], sort=False)
            .rolling(window=20, min_periods=5)
            .mean()
            .reset_index(level=0, drop=True)
        )
    if "return_1d" in out.columns:
        grouped_ret = out.groupby("stock_id", sort=False)["return_1d"]
        out["stock_mean_return_20d"] = (
            grouped_ret.rolling(window=20, min_periods=5).mean().reset_index(level=0, drop=True)
        )
    return out


def get_feature_columns(df: pd.DataFrame) -> List[str]:
    """Return ordered list of numeric model feature columns (excluding stock_id, datetime, and targets)."""
    feature_cols: List[str] = []
    for col in df.columns:
        if col in NON_FEATURE_COLUMNS or col.startswith("target_"):
            continue
        if pd.api.types.is_numeric_dtype(df[col]) or pd.api.types.is_bool_dtype(df[col]):
            feature_cols.append(col)
    return feature_cols


class DatasetBuilder:
    """Builds feature-engineered ML dataset with configurable horizon and lookback."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or load_settings()

    def process_dataframe(
        self,
        df: pd.DataFrame,
        horizon: Optional[int] = None,
        lookback: Optional[int] = None,
        lags: Optional[Sequence[int]] = None,
        drop_incomplete: bool = True,
        require_target: bool = True,
        validate_input: bool = True,
    ) -> pd.DataFrame:
        """Run sorting, feature engineering, lag generation, target generation, and NaN removal."""
        t0 = time.perf_counter()
        eff_horizon = int(horizon if horizon is not None else self.settings.target.horizon)
        eff_lookback = int(lookback if lookback is not None else self.settings.features.lookback)
        eff_lags = list(lags if lags is not None else self.settings.features.lags)

        if validate_input:
            validator = DataValidator(min_history_rows=max(eff_lookback + eff_horizon + 5, 30))
            work = validator.validate(df)
        else:
            work = sort_stock_data(df)

        ret_windows = sorted(set(DEFAULT_RETURN_WINDOWS) | ({eff_lookback} if eff_lookback > 0 else set()))
        vol_windows = sorted(set(DEFAULT_VOLATILITY_WINDOWS) | ({eff_lookback} if eff_lookback > 1 else set()))

        work = add_return_features(work, windows=ret_windows)
        work = add_volatility_features(work, windows=vol_windows)
        work = add_all_technical_features(work)
        work = add_stock_profile_features(work)
        work = add_lag_features(
            work,
            lags=eff_lags,
            columns=self.settings.features.lag_columns or DEFAULT_LAG_COLUMNS,
            max_lookback=eff_lookback,
        )

        if require_target:
            work = generate_target(work, horizon=eff_horizon)

        feature_cols = get_feature_columns(work)
        work[feature_cols] = work[feature_cols].replace([np.inf, -np.inf], np.nan)

        before_drop = len(work)
        if drop_incomplete:
            required_cols = list(feature_cols)
            target_col = f"target_{eff_horizon}d"
            if require_target and target_col in work.columns:
                required_cols.append(target_col)
            work = work.dropna(subset=required_cols)
            if validate_input and require_target and target_col in work.columns:
                valid_ret_mask = (work[target_col].abs() <= 5.0) & (work["return_1d"].abs() <= 5.0)
                work = work.loc[valid_ret_mask]
            work = work.reset_index(drop=True)

        # Downcast float64 features & targets to float32 to halve RAM footprint on large datasets (Point 47)
        float_cols = [c for c in feature_cols if c in work.columns]
        target_col = f"target_{eff_horizon}d"
        if target_col in work.columns:
            float_cols.append(target_col)
        work[float_cols] = work[float_cols].astype(np.float32)
        if "stock_id" in work.columns:
            work["stock_id"] = work["stock_id"].astype(np.int32)

        removed = before_drop - len(work)
        elapsed = time.perf_counter() - t0
        logger.info(
            "Feature engineering completed in %.2fs | Features: %d | Removed incomplete rows: %s | Final rows: %s",
            elapsed,
            len(feature_cols),
            f"{removed:,}",
            f"{len(work):,}",
        )
        return work

    def build_and_stream_to_parquet(
        self,
        loader: Optional[DataLoader] = None,
        stock_ids: Optional[Sequence[int]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        max_stocks: Optional[int] = None,
        batch_size: Optional[int] = None,
        horizon: Optional[int] = None,
        lookback: Optional[int] = None,
        output_dir: Optional[Path] = None,
    ) -> Dict[str, object]:
        """Stream stock batches from PostgreSQL, engineer features per batch, and write directly to
        Parquet files (dataset.parquet, train.parquet, validation.parquet, test.parquet) using PyArrow
        so the entire multi-million-row dataset is processed with bounded RAM (Points 7, 47, 48).
        """
        own_loader = loader is None
        data_loader = loader or DataLoader(settings=self.settings)
        out_dir = Path(output_dir or self.settings.data.processed_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        paths = {
            "dataset": out_dir / "dataset.parquet",
            "train": out_dir / "train.parquet",
            "validation": out_dir / "validation.parquet",
            "test": out_dir / "test.parquet",
        }
        writers: Dict[str, pq.ParquetWriter] = {}

        try:
            eff_start = start_date if start_date is not None else self.settings.data.start_date
            eff_end = end_date if end_date is not None else self.settings.data.end_date
            eff_max_stocks = max_stocks if max_stocks is not None else self.settings.data.max_stocks
            eff_batch_size = batch_size or self.settings.database.stock_batch_size

            if stock_ids is None:
                stock_ids = data_loader.get_available_stock_ids(
                    start_date=eff_start,
                    min_rows=self.settings.data.min_history_rows,
                    limit=eff_max_stocks,
                )

            total_batches = (len(stock_ids) + eff_batch_size - 1) // eff_batch_size
            logger.info(
                "Building full dataset across %s stocks in %d batches (batch_size=%d)...",
                f"{len(stock_ids):,}",
                total_batches,
                eff_batch_size,
            )

            train_end_ts = pd.Timestamp(self.settings.training.train_end)
            val_end_ts = pd.Timestamp(self.settings.training.val_end)

            total_raw = 0
            total_proc = 0
            split_counts = {"train": 0, "validation": 0, "test": 0}
            unique_stocks: set[int] = set()
            feature_cols: List[str] = []
            min_dt_seen: Optional[pd.Timestamp] = None
            max_dt_seen: Optional[pd.Timestamp] = None

            for batch_idx, raw_chunk in enumerate(
                data_loader.iter_chunks_by_stock_batches(
                    stock_ids=stock_ids,
                    batch_size=eff_batch_size,
                    start_date=eff_start,
                    end_date=eff_end,
                ),
                start=1,
            ):
                total_raw += len(raw_chunk)
                proc_chunk = self.process_dataframe(
                    raw_chunk,
                    horizon=horizon,
                    lookback=lookback,
                    drop_incomplete=True,
                    require_target=True,
                    validate_input=True,
                )
                del raw_chunk
                if proc_chunk.empty:
                    continue

                if not feature_cols:
                    feature_cols = get_feature_columns(proc_chunk)

                total_proc += len(proc_chunk)
                unique_stocks.update(proc_chunk["stock_id"].unique().tolist())
                c_min = proc_chunk["datetime"].min()
                c_max = proc_chunk["datetime"].max()
                min_dt_seen = c_min if min_dt_seen is None or c_min < min_dt_seen else min_dt_seen
                max_dt_seen = c_max if max_dt_seen is None or c_max > max_dt_seen else max_dt_seen

                # Split chunk chronologically
                dt = proc_chunk["datetime"]
                sub_chunks = {
                    "dataset": proc_chunk,
                    "train": proc_chunk.loc[dt <= train_end_ts],
                    "validation": proc_chunk.loc[(dt > train_end_ts) & (dt <= val_end_ts)],
                    "test": proc_chunk.loc[dt > val_end_ts],
                }
                for key, sub_df in sub_chunks.items():
                    if sub_df.empty:
                        continue
                    if key in split_counts:
                        split_counts[key] += len(sub_df)
                    table = pa.Table.from_pandas(sub_df, preserve_index=False)
                    if key not in writers:
                        writers[key] = pq.ParquetWriter(paths[key], table.schema, compression="snappy")
                    writers[key].write_table(table)

                logger.info(
                    "Progress: batch %d/%d complete | Cumulative processed rows: %s (%s stocks)",
                    batch_idx,
                    total_batches,
                    f"{total_proc:,}",
                    f"{len(unique_stocks):,}",
                )
                del proc_chunk, sub_chunks
                gc.collect()

            if total_proc == 0:
                raise ValueError("No valid processed records produced from database chunks.")

        finally:
            for w in writers.values():
                w.close()
            if own_loader:
                data_loader.db.close()

        logger.info(
            "Full dataset built & saved to Parquet: raw=%s -> processed=%s across %s stocks (%s..%s)",
            f"{total_raw:,}",
            f"{total_proc:,}",
            f"{len(unique_stocks):,}",
            min_dt_seen.strftime("%Y-%m-%d") if min_dt_seen else "N/A",
            max_dt_seen.strftime("%Y-%m-%d") if max_dt_seen else "N/A",
        )
        logger.info(
            "Chronological split sizes | Train: %s | Validation: %s | Test: %s",
            f"{split_counts['train']:,}",
            f"{split_counts['validation']:,}",
            f"{split_counts['test']:,}",
        )
        return {
            "paths": paths,
            "feature_cols": feature_cols,
            "total_rows": total_proc,
            "stocks_count": len(unique_stocks),
            "split_counts": split_counts,
            "min_date": min_dt_seen.strftime("%Y-%m-%d") if min_dt_seen else None,
            "max_date": max_dt_seen.strftime("%Y-%m-%d") if max_dt_seen else None,
        }

    def build_from_database(
        self,
        loader: Optional[DataLoader] = None,
        stock_ids: Optional[Sequence[int]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        max_stocks: Optional[int] = None,
        batch_size: Optional[int] = None,
        horizon: Optional[int] = None,
        lookback: Optional[int] = None,
    ) -> pd.DataFrame:
        """Load data in stock batches from PostgreSQL, engineer features per batch to control RAM, and combine."""
        info = self.build_and_stream_to_parquet(
            loader=loader,
            stock_ids=stock_ids,
            start_date=start_date,
            end_date=end_date,
            max_stocks=max_stocks,
            batch_size=batch_size,
            horizon=horizon,
            lookback=lookback,
        )
        return pd.read_parquet(info["paths"]["dataset"])  # type: ignore[index]

    @staticmethod
    def extract_xy(
        df: pd.DataFrame,
        target_col: str = "target_7d",
        feature_cols: Optional[Sequence[str]] = None,
    ) -> Tuple[pd.DataFrame, pd.Series]:
        """Extract consolidated single-block float32 feature matrix X and float32 target vector y."""
        cols = list(feature_cols) if feature_cols is not None else get_feature_columns(df)
        if target_col not in df.columns:
            raise KeyError(f"Target column '{target_col}' not found in DataFrame.")
        x_arr = df[cols].to_numpy(dtype=np.float32, copy=False)
        X = pd.DataFrame(x_arr, columns=cols, copy=False)
        y = pd.Series(df[target_col].to_numpy(dtype=np.float32, copy=False), name=target_col, copy=False)
        return X, y
