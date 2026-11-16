import numpy as np
import pandas as pd


def add_ema_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add ema_12_distance, ema_26_distance, and ema_difference relative to close price."""
    out = df.copy()
    if "close" not in out.columns:
        return out

    close = out["close"]
    safe_close = np.where(close != 0, close, np.nan)

    if "ema_12" in out.columns:
        out["ema_12_distance"] = (out["ema_12"] - close) / safe_close
    if "ema_26" in out.columns:
        out["ema_26_distance"] = (out["ema_26"] - close) / safe_close
    if "ema_12" in out.columns and "ema_26" in out.columns:
        out["ema_difference"] = (out["ema_12"] - out["ema_26"]) / safe_close

    return out


def add_bollinger_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add bollinger_position = (close - bollinger_lower) / (bollinger_upper - bollinger_lower) with zero guard."""
    out = df.copy()
    if not {"close", "bollinger_lower", "bollinger_upper"}.issubset(out.columns):
        return out

    band_span = out["bollinger_upper"] - out["bollinger_lower"]
    valid_inputs = out["close"].notna() & out["bollinger_lower"].notna() & out["bollinger_upper"].notna()
    nonzero_span = valid_inputs & (np.abs(band_span) > 1e-12)

    position = np.full(len(out), np.nan, dtype=np.float64)
    # When upper == lower (zero band width), default position to neutral 0.5 instead of inf/NaN
    zero_span_mask = valid_inputs & ~nonzero_span
    position[zero_span_mask] = 0.5
    position[nonzero_span] = (
        (out.loc[nonzero_span, "close"] - out.loc[nonzero_span, "bollinger_lower"])
        / band_span.loc[nonzero_span]
    )
    out["bollinger_position"] = position
    return out


def add_volume_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add volume_change, volume_ma_5, volume_ma_20, and volume_ratio per stock_id."""
    out = df.copy()
    if "volume" not in out.columns:
        return out

    vol_float = out["volume"].astype(np.float64)
    grouped_vol = vol_float.groupby(out["stock_id"], sort=False)

    prev_vol = grouped_vol.shift(1)
    out["volume_change"] = np.where(prev_vol > 0, (vol_float / prev_vol) - 1.0, 0.0)
    out.loc[prev_vol.isna(), "volume_change"] = np.nan

    out["volume_ma_5"] = grouped_vol.rolling(window=5, min_periods=5).mean().reset_index(level=0, drop=True)
    out["volume_ma_20"] = (
        grouped_vol.rolling(window=20, min_periods=20).mean().reset_index(level=0, drop=True)
    )
    out["volume_ratio"] = np.where(
        out["volume_ma_20"] > 0,
        vol_float / out["volume_ma_20"],
        np.nan,
    )
    return out


def add_rsi_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add rsi_change_1d and rsi_change_5d per stock_id."""
    out = df.copy()
    if "rsi" not in out.columns:
        return out

    grouped_rsi = out.groupby("stock_id", sort=False)["rsi"]
    out["rsi_change_1d"] = out["rsi"] - grouped_rsi.shift(1)
    out["rsi_change_5d"] = out["rsi"] - grouped_rsi.shift(5)
    return out


def add_macd_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add macd_difference, macd_change_1d, and macd_change_5d per stock_id."""
    out = df.copy()
    if "macd" not in out.columns:
        return out

    if "macd_signal" in out.columns:
        out["macd_difference"] = out["macd"] - out["macd_signal"]

    grouped_macd = out.groupby("stock_id", sort=False)["macd"]
    out["macd_change_1d"] = out["macd"] - grouped_macd.shift(1)
    out["macd_change_5d"] = out["macd"] - grouped_macd.shift(5)
    return out


def add_obv_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add obv_change_1d, obv_change_5d, and obv_change_20d per stock_id."""
    out = df.copy()
    if "obv" not in out.columns:
        return out

    obv_float = out["obv"].astype(np.float64)
    grouped_obv = obv_float.groupby(out["stock_id"], sort=False)
    out["obv_change_1d"] = obv_float - grouped_obv.shift(1)
    out["obv_change_5d"] = obv_float - grouped_obv.shift(5)
    out["obv_change_20d"] = obv_float - grouped_obv.shift(20)
    return out


def add_all_technical_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute all technical and volume features (Points 15-20)."""
    out = add_ema_features(df)
    out = add_bollinger_features(out)
    out = add_volume_features(out)
    out = add_rsi_features(out)
    out = add_macd_features(out)
    out = add_obv_features(out)
    return out
