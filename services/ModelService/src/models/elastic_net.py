from typing import Any, Dict, List, Sequence

from sklearn.linear_model import ElasticNet
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

DEFAULT_ELASTICNET_ALPHAS: tuple[float, ...] = (0.0005, 0.001, 0.005, 0.01)
DEFAULT_ELASTICNET_L1_RATIOS: tuple[float, ...] = (0.1, 0.5, 0.9)


def build_elastic_net_pipeline(
    alpha: float = 0.001,
    l1_ratio: float = 0.5,
    random_state: int = 42,
    max_iter: int = 200,
) -> Pipeline:
    """Build StandardScaler + ElasticNet pipeline."""
    return Pipeline(
        [
            ("scaler", StandardScaler()),
            (
                "model",
                ElasticNet(
                    alpha=float(alpha),
                    l1_ratio=float(l1_ratio),
                    max_iter=max_iter,
                    tol=1e-2,
                    random_state=random_state,
                ),
            ),
        ]
    )


def get_elastic_net_param_candidates(
    alphas: Sequence[float] = DEFAULT_ELASTICNET_ALPHAS,
    l1_ratios: Sequence[float] = DEFAULT_ELASTICNET_L1_RATIOS,
) -> List[Dict[str, Any]]:
    """Return hyperparameter grid for ElasticNet tuning (Point 33)."""
    return [{"alpha": float(a), "l1_ratio": float(l1)} for a in alphas for l1 in l1_ratios]
