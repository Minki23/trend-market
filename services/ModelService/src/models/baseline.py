from sklearn.dummy import DummyRegressor
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


def build_zero_baseline() -> Pipeline:
    """Build baseline predicting 0.0 return (assumption that stock price remains unchanged, Point 36)."""
    return Pipeline(
        [
            ("model", DummyRegressor(strategy="constant", constant=0.0)),
        ]
    )


def build_linear_regression() -> Pipeline:
    """Build LinearRegression wrapped with StandardScaler fitted only on training data."""
    return Pipeline(
        [
            ("scaler", StandardScaler()),
            ("model", LinearRegression()),
        ]
    )
