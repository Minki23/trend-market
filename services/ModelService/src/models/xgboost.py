from itertools import product
from typing import Any, Dict, List, Sequence

from lightgbm import LGBMRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.pipeline import Pipeline
from xgboost import XGBRegressor


def build_xgboost_pipeline(
    max_depth: int = 4,
    learning_rate: float = 0.05,
    n_estimators: int = 150,
    subsample: float = 0.8,
    colsample_bytree: float = 0.8,
    random_state: int = 42,
    n_jobs: int = -1,
) -> Pipeline:
    """Build XGBoost regression pipeline (Points 30 & 33)."""
    model = XGBRegressor(
        max_depth=int(max_depth),
        learning_rate=float(learning_rate),
        n_estimators=int(n_estimators),
        subsample=float(subsample),
        colsample_bytree=float(colsample_bytree),
        random_state=random_state,
        n_jobs=n_jobs,
        objective="reg:squarederror",
        tree_method="hist",
    )
    return Pipeline([("model", model)])


def build_lightgbm_pipeline(
    max_depth: int = 4,
    learning_rate: float = 0.05,
    n_estimators: int = 150,
    subsample: float = 0.8,
    colsample_bytree: float = 0.8,
    random_state: int = 42,
    n_jobs: int = -1,
) -> Pipeline:
    """Build LightGBM regression pipeline (Points 30 & 33)."""
    num_leaves = max(7, min(31, (2 ** int(max_depth)) - 1))
    model = LGBMRegressor(
        max_depth=int(max_depth),
        num_leaves=num_leaves,
        learning_rate=float(learning_rate),
        n_estimators=int(n_estimators),
        subsample=float(subsample),
        colsample_bytree=float(colsample_bytree),
        random_state=random_state,
        n_jobs=n_jobs,
        verbose=-1,
    )
    return Pipeline([("model", model)])


def build_random_forest_pipeline(
    n_estimators: int = 100,
    max_depth: int = 8,
    random_state: int = 42,
    n_jobs: int = -1,
) -> Pipeline:
    """Build optional RandomForestRegressor pipeline (Point 30)."""
    model = RandomForestRegressor(
        n_estimators=int(n_estimators),
        max_depth=int(max_depth),
        random_state=random_state,
        n_jobs=n_jobs,
    )
    return Pipeline([("model", model)])


def get_gbdt_param_candidates(
    max_depths: Sequence[int] = (3, 5),
    learning_rates: Sequence[float] = (0.05, 0.1),
    n_estimators_list: Sequence[int] = (100, 200),
    subsamples: Sequence[float] = (0.8,),
    colsample_bytrees: Sequence[float] = (0.8,),
) -> List[Dict[str, Any]]:
    """Return hyperparameter candidates for XGBoost / LightGBM tuning (Point 33)."""
    candidates: List[Dict[str, Any]] = []
    for md, lr, ne, ss, cs in product(
        max_depths, learning_rates, n_estimators_list, subsamples, colsample_bytrees
    ):
        candidates.append(
            {
                "max_depth": int(md),
                "learning_rate": float(lr),
                "n_estimators": int(ne),
                "subsample": float(ss),
                "colsample_bytree": float(cs),
            }
        )
    return candidates
