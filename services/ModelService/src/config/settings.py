import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_PATH = BASE_DIR / ".env"
DEFAULT_CONFIG_PATH = BASE_DIR / "config.yaml"

load_dotenv(dotenv_path=ENV_PATH, override=False)


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure standardized pipeline logger."""
    logger = logging.getLogger("stock_prediction")
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("[%(levelname)s] %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger


logger = setup_logging()


@dataclass
class DatabaseConfig:
    host: str = "localhost"
    port: int = 5432
    name: str = "stocks"
    user: str = "admin"
    password: str = "admin"
    pool_size: int = 5
    max_overflow: int = 10
    stock_batch_size: int = 100
    sql_chunk_size: int = 100000

    @property
    def sqlalchemy_url(self) -> str:
        return f"postgresql+psycopg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


@dataclass
class DataConfig:
    start_date: Optional[str] = "2019-01-01"
    end_date: Optional[str] = None
    max_stocks: Optional[int] = None
    min_history_rows: int = 250
    raw_dir: Path = field(default_factory=lambda: BASE_DIR / "data" / "raw")
    processed_dir: Path = field(default_factory=lambda: BASE_DIR / "data" / "processed")


@dataclass
class TargetConfig:
    horizon: int = 7
    allowed_horizons: List[int] = field(default_factory=lambda: [1, 3, 5, 7, 10])

    @property
    def target_col(self) -> str:
        return f"target_{self.horizon}d"


@dataclass
class FeaturesConfig:
    lookback: int = 20
    lags: List[int] = field(default_factory=lambda: [1, 2, 3, 5, 10, 20])
    lag_columns: List[str] = field(
        default_factory=lambda: [
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
        ]
    )


@dataclass
class TrainingConfig:
    target_horizon: int = 7
    lookback: int = 20
    training_years: int = 3
    years: int = 3
    allowed_training_years: List[int] = field(default_factory=lambda: [1, 2, 3, 5])
    random_seed: int = 42
    train_end: str = "2023-12-31"
    val_end: str = "2024-12-31"


@dataclass
class ValidationConfig:
    method: str = "walk_forward"
    folds: List[Dict[str, str]] = field(default_factory=list)
    test_period: Dict[str, str] = field(default_factory=dict)


@dataclass
class Settings:
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    data: DataConfig = field(default_factory=DataConfig)
    target: TargetConfig = field(default_factory=TargetConfig)
    features: FeaturesConfig = field(default_factory=FeaturesConfig)
    training: TrainingConfig = field(default_factory=TrainingConfig)
    validation: ValidationConfig = field(default_factory=ValidationConfig)
    model: Dict[str, Any] = field(default_factory=lambda: {"type": "ridge", "alpha": 1.0})
    models: List[str] = field(
        default_factory=lambda: ["dummy", "linear_regression", "ridge", "elastic_net", "xgboost", "lightgbm"]
    )
    tuning: Dict[str, Dict[str, List[Any]]] = field(default_factory=dict)
    metrics: List[str] = field(
        default_factory=lambda: ["mae", "rmse", "r2", "direction_accuracy", "pearson", "spearman"]
    )
    models_dir: Path = field(default_factory=lambda: BASE_DIR / "models")
    experiments_dir: Path = field(default_factory=lambda: BASE_DIR / "experiments")


def _expand_env_vars(obj: Any) -> Any:
    """Recursively expand ${VAR} placeholders using environment variables."""
    if isinstance(obj, str):
        pattern = re.compile(r"\$\{([^}]+)\}")

        def replacer(match: re.Match) -> str:
            var_name = match.group(1)
            return os.environ.get(var_name, "")

        return pattern.sub(replacer, obj)
    if isinstance(obj, dict):
        return {k: _expand_env_vars(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_expand_env_vars(item) for item in obj]
    return obj


def load_settings(config_path: Optional[Path] = None) -> Settings:
    """Load settings from config.yaml and environment variables."""
    load_dotenv(dotenv_path=ENV_PATH, override=False)
    path = config_path or DEFAULT_CONFIG_PATH
    raw_cfg: Dict[str, Any] = {}
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            raw_cfg = yaml.safe_load(f) or {}
    expanded = _expand_env_vars(raw_cfg)

    db_raw = expanded.get("database", {})
    db_cfg = DatabaseConfig(
        host=db_raw.get("host") or os.environ.get("DB_HOST", "localhost"),
        port=int(db_raw.get("port") or os.environ.get("DB_PORT", 5432)),
        name=db_raw.get("name") or os.environ.get("DB_NAME", "stocks"),
        user=db_raw.get("user") or os.environ.get("DB_USER", "admin"),
        password=db_raw.get("password") or os.environ.get("DB_PASSWORD", "admin"),
        pool_size=int(db_raw.get("pool_size", 5)),
        max_overflow=int(db_raw.get("max_overflow", 10)),
        stock_batch_size=int(db_raw.get("stock_batch_size", 100)),
        sql_chunk_size=int(db_raw.get("sql_chunk_size", 100000)),
    )

    data_raw = expanded.get("data", {})
    data_cfg = DataConfig(
        start_date=data_raw.get("start_date", "2019-01-01"),
        end_date=data_raw.get("end_date"),
        max_stocks=data_raw.get("max_stocks", None),
        min_history_rows=int(data_raw.get("min_history_rows", 250)),
        raw_dir=BASE_DIR / data_raw.get("raw_dir", "data/raw"),
        processed_dir=BASE_DIR / data_raw.get("processed_dir", "data/processed"),
    )

    target_raw = expanded.get("target", {})
    training_raw = expanded.get("training", {})
    horizon = int(target_raw.get("horizon", training_raw.get("target_horizon", 7)))
    target_cfg = TargetConfig(
        horizon=horizon,
        allowed_horizons=target_raw.get("allowed_horizons", [1, 3, 5, 7, 10]),
    )

    features_raw = expanded.get("features", {})
    lookback = int(features_raw.get("lookback", training_raw.get("lookback", 20)))
    features_cfg = FeaturesConfig(
        lookback=lookback,
        lags=features_raw.get("lags", [1, 2, 3, 5, 10, 20]),
        lag_columns=features_raw.get(
            "lag_columns",
            [
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
            ],
        ),
    )

    years = int(training_raw.get("years", training_raw.get("training_years", 3)))
    training_cfg = TrainingConfig(
        target_horizon=horizon,
        lookback=lookback,
        training_years=years,
        years=years,
        allowed_training_years=training_raw.get("allowed_training_years", [1, 2, 3, 5]),
        random_seed=int(training_raw.get("random_seed", 42)),
        train_end=training_raw.get("train_end", "2023-12-31"),
        val_end=training_raw.get("val_end", "2024-12-31"),
    )

    val_raw = expanded.get("validation", {})
    val_cfg = ValidationConfig(
        method=val_raw.get("method", "walk_forward"),
        folds=val_raw.get("folds", []),
        test_period=val_raw.get("test_period", {}),
    )

    return Settings(
        database=db_cfg,
        data=data_cfg,
        target=target_cfg,
        features=features_cfg,
        training=training_cfg,
        validation=val_cfg,
        model=expanded.get("model", {"type": "ridge", "alpha": 1.0}),
        models=expanded.get(
            "models", ["dummy", "linear_regression", "ridge", "elastic_net", "xgboost", "lightgbm"]
        ),
        tuning=expanded.get("tuning", {}),
        metrics=expanded.get(
            "metrics", ["mae", "rmse", "r2", "direction_accuracy", "pearson", "spearman"]
        ),
    )
