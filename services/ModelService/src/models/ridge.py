from typing import Any, Dict, List, Sequence

from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

DEFAULT_RIDGE_ALPHAS: tuple[float, ...] = (0.01, 0.1, 1.0, 10.0, 100.0)


def build_ridge_pipeline(alpha: float = 1.0, random_state: int = 42) -> Pipeline:
    """Build primary reference model: StandardScaler + Ridge regression (Points 31-32)."""
    return Pipeline(
        [
            ("scaler", StandardScaler()),
            ("model", Ridge(alpha=float(alpha), solver="lsqr", random_state=random_state)),
        ]
    )


def get_ridge_param_candidates(alphas: Sequence[float] = DEFAULT_RIDGE_ALPHAS) -> List[Dict[str, Any]]:
    """Return hyperparameter candidates for Ridge tuning (Point 33)."""
    return [{"alpha": float(a)} for a in alphas]
