from typing import Dict

import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


def compute_metrics(y_true: np.ndarray | pd.Series, y_pred: np.ndarray | pd.Series) -> Dict[str, float]:
    """Compute MAE, RMSE, R2, Direction Accuracy, Pearson correlation, and Spearman correlation."""
    yt = np.asarray(y_true, dtype=np.float64)
    yp = np.asarray(y_pred, dtype=np.float64)

    if len(yt) == 0:
        return {
            "mae": float("nan"),
            "rmse": float("nan"),
            "r2": float("nan"),
            "direction_accuracy": float("nan"),
            "pearson": float("nan"),
            "spearman": float("nan"),
        }

    mae = float(mean_absolute_error(yt, yp))
    rmse = float(np.sqrt(mean_squared_error(yt, yp)))
    r2 = float(r2_score(yt, yp)) if len(yt) > 1 and np.std(yt) > 0 else 0.0
    direction_acc = float(np.mean(np.sign(yp) == np.sign(yt)))

    if len(yt) > 2 and np.std(yt) > 1e-12 and np.std(yp) > 1e-12:
        p_val, _ = pearsonr(yt, yp)
        s_val, _ = spearmanr(yt, yp)
        pearson = float(0.0 if np.isnan(p_val) else p_val)
        spearman = float(0.0 if np.isnan(s_val) else s_val)
    else:
        pearson = 0.0
        spearman = 0.0

    return {
        "mae": mae,
        "rmse": rmse,
        "r2": r2,
        "direction_accuracy": direction_acc,
        "pearson": pearson,
        "spearman": spearman,
    }


def build_prediction_analysis_table(
    df: pd.DataFrame,
    y_true: np.ndarray | pd.Series,
    y_pred: np.ndarray | pd.Series,
) -> pd.DataFrame:
    """Create detailed prediction analysis table (Point 37)."""
    yt = np.asarray(y_true, dtype=np.float64)
    yp = np.asarray(y_pred, dtype=np.float64)

    table = pd.DataFrame(
        {
            "datetime": pd.to_datetime(df["datetime"].values),
            "stock_id": df["stock_id"].values,
            "actual_return": yt,
            "predicted_return": yp,
            "prediction_error": yp - yt,
            "actual_direction": np.sign(yt).astype(np.int8),
            "predicted_direction": np.sign(yp).astype(np.int8),
        }
    )
    return table


def analyze_by_stock(pred_table: pd.DataFrame) -> pd.DataFrame:
    """Compute evaluation metrics separately for each stock_id using vectorized groupby (Point 38)."""
    if pred_table.empty:
        return pd.DataFrame(columns=["stock_id", "samples", "MAE", "RMSE", "R2", "direction_accuracy"])

    work = pd.DataFrame(
        {
            "stock_id": pred_table["stock_id"].values,
            "yt": np.asarray(pred_table["actual_return"], dtype=np.float64),
            "yp": np.asarray(pred_table["predicted_return"], dtype=np.float64),
        }
    )
    err = work["yp"] - work["yt"]
    work["abs_err"] = np.abs(err)
    work["sq_err"] = err * err
    work["dir_match"] = (np.sign(work["yp"]) == np.sign(work["yt"])).astype(np.float64)

    grp = work.groupby("stock_id", sort=True)
    agg = grp.agg(
        samples=("yt", "count"),
        MAE=("abs_err", "mean"),
        mse=("sq_err", "mean"),
        direction_accuracy=("dir_match", "mean"),
        yt_var=("yt", lambda s: np.var(s.values, ddof=0)),
    ).reset_index()

    agg["RMSE"] = np.sqrt(agg["mse"])
    agg["R2"] = np.where(agg["yt_var"] > 1e-12, 1.0 - (agg["mse"] / agg["yt_var"]), 0.0)
    agg["stock_id"] = agg["stock_id"].astype(int)
    return agg[["stock_id", "samples", "MAE", "RMSE", "R2", "direction_accuracy"]]


def analyze_by_period(pred_table: pd.DataFrame) -> pd.DataFrame:
    """Compute evaluation metrics grouped by calendar year (Point 39)."""
    if pred_table.empty:
        return pd.DataFrame(
            columns=["year", "samples", "MAE", "RMSE", "R2", "direction_accuracy", "pearson", "spearman"]
        )

    work = pred_table.copy()
    work["year"] = pd.to_datetime(work["datetime"]).dt.year
    rows = []
    for year, grp in work.groupby("year", sort=True):
        m = compute_metrics(grp["actual_return"].values, grp["predicted_return"].values)
        rows.append(
            {
                "year": int(year),
                "samples": len(grp),
                "MAE": m["mae"],
                "RMSE": m["rmse"],
                "R2": m["r2"],
                "direction_accuracy": m["direction_accuracy"],
                "pearson": m["pearson"],
                "spearman": m["spearman"],
            }
        )
    return pd.DataFrame(rows)
