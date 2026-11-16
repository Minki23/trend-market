from pathlib import Path
from typing import Dict, Optional, Tuple

import pandas as pd

from src.config.settings import Settings, load_settings, logger


class ChronologicalSplitter:
    """Splits time-series stock dataset chronologically (NEVER shuffling) and persists to Parquet."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or load_settings()

    def split_by_dates(
        self,
        df: pd.DataFrame,
        train_end: Optional[str] = None,
        val_end: Optional[str] = None,
        train_start: Optional[str] = None,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Chronological split into (train_df, val_df, test_df) based on date cutoffs.

        Example default:
            Train: <= 2023-12-31
            Validation: 2024-01-01 .. 2024-12-31
            Test: >= 2025-01-01
        """
        if df.empty:
            raise ValueError("Cannot split an empty DataFrame.")

        work = df.copy()
        work["datetime"] = pd.to_datetime(work["datetime"])

        eff_train_end = pd.Timestamp(train_end or self.settings.training.train_end)
        eff_val_end = pd.Timestamp(val_end or self.settings.training.val_end)
        if eff_val_end <= eff_train_end:
            raise ValueError(
                f"val_end ({eff_val_end}) must be strictly after train_end ({eff_train_end})."
            )

        train_mask = work["datetime"] <= eff_train_end
        if train_start:
            train_mask &= work["datetime"] >= pd.Timestamp(train_start)

        val_mask = (work["datetime"] > eff_train_end) & (work["datetime"] <= eff_val_end)
        test_mask = work["datetime"] > eff_val_end

        train_df = work.loc[train_mask].reset_index(drop=True)
        val_df = work.loc[val_mask].reset_index(drop=True)
        test_df = work.loc[test_mask].reset_index(drop=True)

        # Fallback to quantile chronological split if date range of dataset doesn't span fixed years
        if train_df.empty or val_df.empty or test_df.empty:
            logger.info("Dataset dates do not span fixed year boundaries; using 70/15/15 chronological date quantiles.")
            unique_dates = work["datetime"].sort_values().unique()
            if len(unique_dates) < 3:
                raise ValueError("Dataset must contain at least 3 distinct dates for chronological splitting.")
            q1_idx = max(0, int(len(unique_dates) * 0.70) - 1)
            q2_idx = max(q1_idx + 1, int(len(unique_dates) * 0.85) - 1)
            c1 = unique_dates[q1_idx]
            c2 = unique_dates[q2_idx]

            train_df = work.loc[work["datetime"] <= c1].reset_index(drop=True)
            val_df = work.loc[(work["datetime"] > c1) & (work["datetime"] <= c2)].reset_index(drop=True)
            test_df = work.loc[work["datetime"] > c2].reset_index(drop=True)

        # Verify strict chronological ordering between splits
        if not train_df.empty and not val_df.empty:
            assert train_df["datetime"].max() < val_df["datetime"].min(), "Leakage: train overlaps validation!"
        if not val_df.empty and not test_df.empty:
            assert val_df["datetime"].max() < test_df["datetime"].min(), "Leakage: validation overlaps test!"

        logger.info(
            "Chronological split sizes | Train: %s (%s..%s) | Validation: %s (%s..%s) | Test: %s (%s..%s)",
            f"{len(train_df):,}",
            train_df["datetime"].min().strftime("%Y-%m-%d") if not train_df.empty else "N/A",
            train_df["datetime"].max().strftime("%Y-%m-%d") if not train_df.empty else "N/A",
            f"{len(val_df):,}",
            val_df["datetime"].min().strftime("%Y-%m-%d") if not val_df.empty else "N/A",
            val_df["datetime"].max().strftime("%Y-%m-%d") if not val_df.empty else "N/A",
            f"{len(test_df):,}",
            test_df["datetime"].min().strftime("%Y-%m-%d") if not test_df.empty else "N/A",
            test_df["datetime"].max().strftime("%Y-%m-%d") if not test_df.empty else "N/A",
        )
        return train_df, val_df, test_df

    def save_splits_to_parquet(
        self,
        train_df: pd.DataFrame,
        val_df: pd.DataFrame,
        test_df: pd.DataFrame,
        output_dir: Optional[Path] = None,
    ) -> Dict[str, Path]:
        """Save train.parquet, validation.parquet, and test.parquet to data/processed/."""
        out_dir = Path(output_dir or self.settings.data.processed_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        paths = {
            "train": out_dir / "train.parquet",
            "validation": out_dir / "validation.parquet",
            "test": out_dir / "test.parquet",
        }
        train_df.to_parquet(paths["train"], index=False)
        val_df.to_parquet(paths["validation"], index=False)
        test_df.to_parquet(paths["test"], index=False)

        logger.info(
            "Saved Parquet datasets to %s (train.parquet, validation.parquet, test.parquet)",
            out_dir,
        )
        return paths

    def load_splits_from_parquet(
        self,
        input_dir: Optional[Path] = None,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Load train.parquet, validation.parquet, and test.parquet from disk."""
        in_dir = Path(input_dir or self.settings.data.processed_dir)
        train_df = pd.read_parquet(in_dir / "train.parquet")
        val_df = pd.read_parquet(in_dir / "validation.parquet")
        test_df = pd.read_parquet(in_dir / "test.parquet")
        return train_df, val_df, test_df
