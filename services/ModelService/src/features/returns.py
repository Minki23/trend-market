from typing import Sequence

import numpy as np
import pandas as pd

DEFAULT_RETURN_WINDOWS: tuple[int, ...] = (1, 3, 5, 10, 20)


def add_return_features(
    df: pd.DataFrame,
    windows: Sequence[int] = DEFAULT_RETURN_WINDOWS,
    price_col: str = "close",
) -> pd.DataFrame:
    """Compute historical return_Nd = close[t] / close[t-N] - 1 separately for each stock_id."""
    if df.empty or price_col not in df.columns:
        return df.copy()

    out = df.copy()
    grouped_close = out.groupby("stock_id", sort=False)[price_col]

    for w in windows:
        if w <= 0:
            raise ValueError(f"Return window must be positive (got {w}) to prevent data leakage.")
        lagged = grouped_close.shift(w)
        out[f"return_{w}d"] = np.where(lagged > 0, (out[price_col] / lagged) - 1.0, np.nan)

    return out
