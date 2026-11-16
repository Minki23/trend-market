from typing import Optional, Sequence

import pandas as pd

DEFAULT_LAGS: tuple[int, ...] = (1, 2, 3, 5, 10, 20)
DEFAULT_LAG_COLUMNS: tuple[str, ...] = (
    "rsi",
    "macd",
    "macd_hist",
    "atr",
    "bollinger_position",
    "bollinger_width",
    "ema_difference",
    "return_1d",
    "return_5d",
    "volume_ratio",
)


def add_lag_features(
    df: pd.DataFrame,
    lags: Sequence[int] = DEFAULT_LAGS,
    columns: Sequence[str] = DEFAULT_LAG_COLUMNS,
    max_lookback: Optional[int] = None,
) -> pd.DataFrame:
    """Create lag features {col}_lag_{k} per stock_id using only past sessions (k > 0)."""
    if df.empty:
        return df.copy()

    effective_lags = [int(k) for k in lags]
    for k in effective_lags:
        if k <= 0:
            raise ValueError(f"Lag value must be strictly positive (got {k}) to prevent data leakage.")

    if max_lookback is not None:
        effective_lags = [k for k in effective_lags if k <= max_lookback]
        if max_lookback not in effective_lags and max_lookback > 0:
            effective_lags.append(int(max_lookback))
        effective_lags = sorted(set(effective_lags))

    present_cols = [c for c in columns if c in df.columns]
    if not present_cols or not effective_lags:
        return df.copy()

    out = df.copy()
    grouped = out.groupby("stock_id", sort=False)[present_cols]

    lag_frames = {}
    for k in effective_lags:
        shifted = grouped.shift(k)
        for col in present_cols:
            lag_frames[f"{col}_lag_{k}"] = shifted[col]

    lag_df = pd.DataFrame(lag_frames, index=out.index)
    return pd.concat([out, lag_df], axis=1)
