from typing import Sequence

import pandas as pd

from src.features.returns import add_return_features

DEFAULT_VOLATILITY_WINDOWS: tuple[int, ...] = (5, 10, 20)


def add_volatility_features(
    df: pd.DataFrame,
    windows: Sequence[int] = DEFAULT_VOLATILITY_WINDOWS,
    return_col: str = "return_1d",
) -> pd.DataFrame:
    """Compute rolling standard deviation of 1-day returns separately for each stock_id."""
    if df.empty:
        return df.copy()

    out = df.copy()
    if return_col not in out.columns:
        out = add_return_features(out, windows=(1,))

    grouped_ret = out.groupby("stock_id", sort=False)[return_col]
    for w in windows:
        if w <= 1:
            raise ValueError(f"Volatility window must be > 1 (got {w}).")
        out[f"volatility_{w}d"] = (
            grouped_ret.rolling(window=w, min_periods=w).std().reset_index(level=0, drop=True)
        )

    return out
