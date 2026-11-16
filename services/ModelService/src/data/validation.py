from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.config.settings import logger


class DataValidationError(ValueError):
    """Raised when input dataset fails critical validation checks."""


@dataclass
class ValidationReport:
    initial_rows: int = 0
    final_rows: int = 0
    removed_rows: int = 0
    duplicate_count: int = 0
    invalid_stock_id_count: int = 0
    invalid_date_count: int = 0
    invalid_price_count: int = 0
    invalid_indicator_count: int = 0
    missing_values_by_col: Dict[str, int] = field(default_factory=dict)
    total_missing_values: int = 0
    stocks_count: int = 0
    dropped_short_history_stocks: int = 0
    min_date: Optional[str] = None
    max_date: Optional[str] = None


REQUIRED_BASE_COLUMNS = ["stock_id", "datetime", "close"]
PRICE_COLUMNS = ["open", "high", "low", "close"]
INDICATOR_NUMERIC_COLUMNS = [
    "atr",
    "bollinger_lower",
    "bollinger_upper",
    "bollinger_width",
    "ema_12",
    "ema_26",
    "macd",
    "macd_hist",
    "macd_signal",
    "obv",
    "rsi",
    "sma_20",
]


def sort_stock_data(df: pd.DataFrame) -> pd.DataFrame:
    """Sort dataset strictly by stock_id ASC, datetime ASC."""
    if df.empty:
        return df.copy()
    return df.sort_values(by=["stock_id", "datetime"], ascending=[True, True]).reset_index(drop=True)


class DataValidator:
    """Validates and cleans stock indicator & price data, enforcing (stock_id, datetime) uniqueness and sorting."""

    def __init__(
        self,
        min_history_rows: int = 1,
        drop_missing_indicators: bool = False,
    ) -> None:
        self.min_history_rows = min_history_rows
        self.drop_missing_indicators = drop_missing_indicators

    def validate(
        self,
        df: pd.DataFrame,
        return_report: bool = False,
    ) -> pd.DataFrame | Tuple[pd.DataFrame, ValidationReport]:
        if df is None or df.empty:
            logger.error("Data validation failed: dataset is empty.")
            raise DataValidationError("Dataset is empty.")

        missing_cols = [c for c in REQUIRED_BASE_COLUMNS if c not in df.columns]
        if missing_cols:
            logger.error("Data validation failed: missing required columns %s", missing_cols)
            raise DataValidationError(f"Missing required columns: {missing_cols}")

        report = ValidationReport(initial_rows=len(df))
        work = df.copy()

        # Replace +/-inf with NaN across numeric columns
        num_cols = work.select_dtypes(include=[np.number]).columns
        work[num_cols] = work[num_cols].replace([np.inf, -np.inf], np.nan)

        # Log missing value counts before cleaning
        na_counts = work.isna().sum()
        report.missing_values_by_col = {col: int(cnt) for col, cnt in na_counts.items() if cnt > 0}
        report.total_missing_values = int(na_counts.sum())
        logger.info("Missing values count across dataset: %s", f"{report.total_missing_values:,}")

        # 1. Validate stock_id
        valid_stock_mask = work["stock_id"].notna()
        numeric_stock_id = pd.to_numeric(work["stock_id"], errors="coerce")
        valid_stock_mask &= numeric_stock_id.notna() & (numeric_stock_id > 0)
        report.invalid_stock_id_count = int((~valid_stock_mask).sum())
        if report.invalid_stock_id_count > 0:
            logger.warning("Removing %d rows with invalid stock_id", report.invalid_stock_id_count)
            work = work.loc[valid_stock_mask].copy()
        work["stock_id"] = work["stock_id"].astype(np.int64)

        # 2. Validate datetime
        parsed_dt = pd.to_datetime(work["datetime"], errors="coerce")
        valid_dt_mask = (
            parsed_dt.notna()
            & (parsed_dt >= pd.Timestamp("1950-01-01"))
            & (parsed_dt <= pd.Timestamp("2100-01-01"))
        )
        report.invalid_date_count = int((~valid_dt_mask).sum())
        if report.invalid_date_count > 0:
            logger.warning("Removing %d rows with invalid datetime", report.invalid_date_count)
            work = work.loc[valid_dt_mask].copy()
            parsed_dt = parsed_dt.loc[valid_dt_mask]
        work["datetime"] = parsed_dt

        # 3. Check and remove duplicates on (stock_id, datetime)
        dup_mask = work.duplicated(subset=["stock_id", "datetime"], keep="last")
        report.duplicate_count = int(dup_mask.sum())
        if report.duplicate_count > 0:
            logger.warning(
                "Removing %d duplicate records for (stock_id, datetime)",
                report.duplicate_count,
            )
            work = work.loc[~dup_mask].copy()

        # 4. Validate prices (close > 0, open/high/low > 0, high >= low, volume >= 0)
        valid_price_mask = work["close"].notna() & (work["close"] > 0)
        for pcol in ("open", "high", "low"):
            if pcol in work.columns:
                valid_price_mask &= work[pcol].notna() & (work[pcol] > 0)
        if "high" in work.columns and "low" in work.columns:
            valid_price_mask &= work["high"] >= work["low"]
        if "volume" in work.columns:
            valid_price_mask &= work["volume"].notna() & (work["volume"] >= 0)

        report.invalid_price_count = int((~valid_price_mask).sum())
        if report.invalid_price_count > 0:
            logger.warning("Removing %d rows with invalid price/volume values", report.invalid_price_count)
            work = work.loc[valid_price_mask].copy()

        # 5. Validate indicator domains (RSI in [0, 100], ATR >= 0, bollinger_upper >= bollinger_lower)
        invalid_ind_mask = pd.Series(False, index=work.index)
        if "rsi" in work.columns:
            invalid_ind_mask |= work["rsi"].notna() & ((work["rsi"] < 0) | (work["rsi"] > 100))
        if "atr" in work.columns:
            invalid_ind_mask |= work["atr"].notna() & (work["atr"] < 0)
        if "bollinger_upper" in work.columns and "bollinger_lower" in work.columns:
            both_present = work["bollinger_upper"].notna() & work["bollinger_lower"].notna()
            invalid_ind_mask |= both_present & (work["bollinger_upper"] < work["bollinger_lower"])

        report.invalid_indicator_count = int(invalid_ind_mask.sum())
        if report.invalid_indicator_count > 0:
            logger.warning("Removing %d rows with out-of-range indicator values", report.invalid_indicator_count)
            work = work.loc[~invalid_ind_mask].copy()

        # Optional drop of missing core indicators
        if self.drop_missing_indicators:
            present_ind_cols = [c for c in INDICATOR_NUMERIC_COLUMNS if c in work.columns]
            if present_ind_cols:
                work = work.dropna(subset=present_ind_cols).copy()

        # Normalize boolean columns if present
        for bcol in ("date_continuity", "two_crows"):
            if bcol in work.columns:
                work[bcol] = work[bcol].fillna(False).astype(np.int8)

        # 6. Check minimum history per stock_id
        if self.min_history_rows > 1 and not work.empty:
            counts = work.groupby("stock_id")["datetime"].transform("count")
            short_mask = counts < self.min_history_rows
            if short_mask.any():
                report.dropped_short_history_stocks = int(work.loc[short_mask, "stock_id"].nunique())
                work = work.loc[~short_mask].copy()

        if work.empty:
            logger.error("Data validation failed: no valid records remain after validation.")
            raise DataValidationError("No valid records remain after validation.")

        # 7. Sort chronologically by stock_id ASC, datetime ASC
        work = sort_stock_data(work)

        # Final uniqueness assertion on (stock_id, datetime)
        if work.duplicated(subset=["stock_id", "datetime"]).any():
            raise DataValidationError("Duplicate (stock_id, datetime) records detected after validation.")

        report.final_rows = len(work)
        report.removed_rows = report.initial_rows - report.final_rows
        report.stocks_count = int(work["stock_id"].nunique())
        report.min_date = work["datetime"].min().strftime("%Y-%m-%d")
        report.max_date = work["datetime"].max().strftime("%Y-%m-%d")

        logger.info(
            "Validation finished: removed %s records, remaining %s records (%s stocks, %s to %s)",
            f"{report.removed_rows:,}",
            f"{report.final_rows:,}",
            f"{report.stocks_count:,}",
            report.min_date,
            report.max_date,
        )

        if return_report:
            return work, report
        return work
