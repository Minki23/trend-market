from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.data.validation import DataValidationError, DataValidator, sort_stock_data
from src.dataset.builder import DatasetBuilder, generate_target, get_feature_columns
from src.dataset.splitter import ChronologicalSplitter
from src.features.lag_features import add_lag_features
from src.features.returns import add_return_features
from src.features.technical import (
    add_all_technical_features,
    add_bollinger_features,
    add_ema_features,
)
from src.features.volatility import add_volatility_features
from src.prediction.predictor import StockPredictor
from src.training.evaluation import compute_metrics
from src.training.trainer import ModelTrainer


def _make_synthetic_stock_df(n_days: int = 80, stocks: tuple[int, ...] = (101, 202)) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    dates = pd.date_range("2022-01-01", periods=n_days, freq="B")
    frames = []
    for sid in stocks:
        base_price = 100.0 if sid == 101 else 50.0
        rets = rng.normal(0.001, 0.015, size=n_days)
        close = base_price * np.cumprod(1.0 + rets)
        open_p = close * (1.0 + rng.normal(0, 0.003, size=n_days))
        high_p = np.maximum(open_p, close) * 1.01
        low_p = np.minimum(open_p, close) * 0.99
        vol = rng.integers(10_000, 100_000, size=n_days)

        sma_20 = pd.Series(close).rolling(20, min_periods=1).mean().values
        ema_12 = pd.Series(close).ewm(span=12, adjust=False).mean().values
        ema_26 = pd.Series(close).ewm(span=26, adjust=False).mean().values
        macd = ema_12 - ema_26
        macd_sig = pd.Series(macd).ewm(span=9, adjust=False).mean().values
        macd_hist = macd - macd_sig
        boll_low = sma_20 * 0.95
        boll_up = sma_20 * 1.05
        boll_w = (boll_up - boll_low) / sma_20

        frames.append(
            pd.DataFrame(
                {
                    "indicator_id": np.arange(len(dates)) + sid * 1000,
                    "stock_id": sid,
                    "datetime": dates,
                    "open": open_p,
                    "high": high_p,
                    "low": low_p,
                    "close": close,
                    "volume": vol,
                    "atr": close * 0.02,
                    "bollinger_lower": boll_low,
                    "bollinger_upper": boll_up,
                    "bollinger_width": boll_w,
                    "date_continuity": True,
                    "ema_12": ema_12,
                    "ema_26": ema_26,
                    "macd": macd,
                    "macd_signal": macd_sig,
                    "macd_hist": macd_hist,
                    "obv": np.cumsum(vol * np.sign(rets)).astype(np.int64),
                    "rsi": np.clip(50.0 + rng.normal(0, 10, size=n_days), 5.0, 95.0),
                    "sma_20": sma_20,
                    "two_crows": False,
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def test_return_calculation_per_stock() -> None:
    df = pd.DataFrame(
        {
            "stock_id": [1, 1, 1, 2, 2, 2],
            "datetime": pd.to_datetime(
                ["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-01", "2025-01-02", "2025-01-03"]
            ),
            "close": [100.0, 110.0, 121.0, 50.0, 45.0, 54.0],
        }
    )
    out = add_return_features(df, windows=(1, 2))
    assert np.isnan(out.loc[0, "return_1d"])
    assert np.isclose(out.loc[1, "return_1d"], 0.10)
    assert np.isclose(out.loc[2, "return_2d"], 0.21)
    # Stock 2 first row must NOT use Stock 1's last close!
    assert np.isnan(out.loc[3, "return_1d"])
    assert np.isclose(out.loc[4, "return_1d"], -0.10)
    assert np.isclose(out.loc[5, "return_2d"], 0.08)


def test_volatility_calculation_per_stock() -> None:
    df = _make_synthetic_stock_df(n_days=30, stocks=(1, 2))
    df = add_return_features(df, windows=(1,))
    out = add_volatility_features(df, windows=(5, 10))
    assert "volatility_5d" in out.columns
    assert "volatility_10d" in out.columns

    s1 = out[out["stock_id"] == 1].reset_index(drop=True)
    # First 4 rows of return_1d have <5 valid values (since index 0 is NaN)
    assert s1["volatility_5d"].iloc[:5].isna().all()
    expected_std = s1["return_1d"].iloc[1:6].std(ddof=1)
    assert np.isclose(s1["volatility_5d"].iloc[5], expected_std)


def test_bollinger_position_and_zero_division_guard() -> None:
    df = pd.DataFrame(
        {
            "stock_id": [1, 1],
            "datetime": pd.to_datetime(["2025-01-01", "2025-01-02"]),
            "close": [105.0, 100.0],
            "bollinger_lower": [100.0, 100.0],
            "bollinger_upper": [110.0, 100.0],  # Row 1 has upper == lower (zero width)
        }
    )
    out = add_bollinger_features(df)
    assert np.isclose(out.loc[0, "bollinger_position"], 0.5)
    assert np.isfinite(out.loc[1, "bollinger_position"])
    assert np.isclose(out.loc[1, "bollinger_position"], 0.5)


def test_ema_distance_and_difference() -> None:
    df = pd.DataFrame(
        {
            "stock_id": [1],
            "datetime": pd.to_datetime(["2025-01-01"]),
            "close": [100.0],
            "ema_12": [104.0],
            "ema_26": [98.0],
        }
    )
    out = add_ema_features(df)
    assert np.isclose(out.loc[0, "ema_12_distance"], 0.04)
    assert np.isclose(out.loc[0, "ema_26_distance"], -0.02)
    assert np.isclose(out.loc[0, "ema_difference"], 0.06)


def test_lag_generation_per_stock_and_leakage_rejection() -> None:
    df = _make_synthetic_stock_df(n_days=25, stocks=(1, 2))
    out = add_lag_features(df, lags=(1, 2, 5), columns=("rsi", "macd"))
    for k in (1, 2, 5):
        assert f"rsi_lag_{k}" in out.columns
        assert f"macd_lag_{k}" in out.columns

    s2 = out[out["stock_id"] == 2].reset_index(drop=True)
    assert np.isnan(s2.loc[0, "rsi_lag_1"])
    assert np.isclose(s2.loc[1, "rsi_lag_1"], s2.loc[0, "rsi"])

    with pytest.raises(ValueError, match="strictly positive"):
        add_lag_features(df, lags=(-1,), columns=("rsi",))


def test_target_generation_7d_and_configurable_horizon() -> None:
    prices = [100.0 + i for i in range(15)]
    df = pd.DataFrame(
        {
            "stock_id": [1] * 15,
            "datetime": pd.date_range("2025-01-01", periods=15, freq="B"),
            "close": prices,
        }
    )
    out7 = generate_target(df, horizon=7)
    assert np.isclose(out7.loc[0, "target_7d"], 107.0 / 100.0 - 1.0)
    assert out7["target_7d"].iloc[-7:].isna().all()

    out3 = generate_target(df, horizon=3)
    assert np.isclose(out3.loc[0, "target_3d"], 103.0 / 100.0 - 1.0)
    assert out3["target_3d"].iloc[-3:].isna().all()


def test_data_validation_duplicates_and_sorting() -> None:
    df = pd.DataFrame(
        {
            "stock_id": [2, 1, 1, 1, -5],
            "datetime": ["2025-01-02", "2025-01-03", "2025-01-01", "2025-01-01", "2025-01-01"],
            "open": [50.0, 100.0, 99.0, 100.0, 10.0],
            "high": [52.0, 102.0, 101.0, 102.0, 11.0],
            "low": [49.0, 98.0, 98.0, 99.0, 9.0],
            "close": [51.0, 101.0, 100.0, 100.5, 10.0],
            "volume": [1000, 2000, 1500, 1600, 500],
            "rsi": [55.0, 60.0, 45.0, 46.0, 50.0],
            "atr": [1.0, 1.2, 1.1, 1.1, 0.5],
        }
    )
    validator = DataValidator(min_history_rows=1)
    clean_df, report = validator.validate(df, return_report=True)

    assert report.invalid_stock_id_count == 1
    assert report.duplicate_count == 1
    assert not clean_df.duplicated(subset=["stock_id", "datetime"]).any()
    # Must be sorted by stock_id ASC, datetime ASC
    assert list(clean_df["stock_id"]) == [1, 1, 2]
    assert clean_df.loc[0, "datetime"] < clean_df.loc[1, "datetime"]


def test_chronological_split_no_overlap() -> None:
    df = _make_synthetic_stock_df(n_days=90, stocks=(101, 202))
    splitter = ChronologicalSplitter()
    train_df, val_df, test_df = splitter.split_by_dates(df)

    assert len(train_df) > 0 and len(val_df) > 0 and len(test_df) > 0
    assert train_df["datetime"].max() < val_df["datetime"].min()
    assert val_df["datetime"].max() < test_df["datetime"].min()


def test_no_data_leakage_from_future_rows() -> None:
    """Critical test (Point 24 & 53): mutating future rows t+1..t+N must NEVER change any feature at row t."""
    df_orig = _make_synthetic_stock_df(n_days=70, stocks=(101,))
    df_modified = df_orig.copy()

    cutoff_idx = 45
    # Drastically alter all future prices, volumes, and indicators after cutoff_idx
    df_modified.loc[cutoff_idx + 1 :, "close"] *= 10.0
    df_modified.loc[cutoff_idx + 1 :, "high"] *= 10.0
    df_modified.loc[cutoff_idx + 1 :, "low"] *= 10.0
    df_modified.loc[cutoff_idx + 1 :, "open"] *= 10.0
    df_modified.loc[cutoff_idx + 1 :, "volume"] *= 50
    df_modified.loc[cutoff_idx + 1 :, "rsi"] = 99.0
    df_modified.loc[cutoff_idx + 1 :, "macd"] = 999.0

    builder = DatasetBuilder()
    proc_orig = builder.process_dataframe(df_orig, drop_incomplete=False, require_target=True, validate_input=False)
    proc_mod = builder.process_dataframe(
        df_modified, drop_incomplete=False, require_target=True, validate_input=False
    )

    feature_cols = get_feature_columns(proc_orig)
    # Every single feature up to and including cutoff_idx must be identical
    pd.testing.assert_frame_equal(
        proc_orig.loc[:cutoff_idx, feature_cols],
        proc_mod.loc[:cutoff_idx, feature_cols],
        check_exact=False,
        rtol=1e-12,
        atol=1e-12,
    )


def test_end_to_end_training_persistence_and_prediction(tmp_path: Path) -> None:
    raw_df = _make_synthetic_stock_df(n_days=120, stocks=(101, 202))
    builder = DatasetBuilder()
    proc_df = builder.process_dataframe(raw_df, horizon=7, lookback=10)
    feature_cols = get_feature_columns(proc_df)

    trainer = ModelTrainer()
    best, all_res, final_eval = trainer.run_model_comparison_and_selection(
        df=proc_df,
        model_keys=["dummy", "linear_regression", "ridge"],
        target_col="target_7d",
        feature_cols=feature_cols,
        tune_hyperparameters=True,
    )

    saved = trainer.save_model(
        pipeline=final_eval["pipeline"],
        model_key=best["model_key"],
        model_name=best["model_name"],
        params=best["best_params"],
        feature_cols=feature_cols,
        training_start=final_eval["training_start"],
        training_end=final_eval["training_end"],
        validation_metrics=best["mean_metrics"],
        test_metrics=final_eval["test_metrics"],
        target_horizon=7,
        lookback=10,
        output_dir=tmp_path,
    )
    assert saved["model_path"].exists()
    assert saved["metadata_path"].exists()

    predictor = StockPredictor(model_dir=saved["model_path"].parent)
    preds = predictor.predict_from_dataframe(raw_df)
    assert len(preds) == 2
    assert set(preds["stock_id"]) == {101, 202}
    assert set(preds["predicted_direction"]).issubset({"UP", "DOWN"})
