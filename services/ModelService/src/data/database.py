from contextlib import contextmanager
from typing import Dict, Generator, List, Optional

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import QueuePool

from src.config.settings import DatabaseConfig, load_settings, logger


class DatabaseConnectionError(RuntimeError):
    """Raised when connection to PostgreSQL fails or schema is invalid."""


class DatabaseManager:
    """Manages SQLAlchemy engine, connection pooling, schema inspection, and indexes."""

    def __init__(self, config: Optional[DatabaseConfig] = None) -> None:
        self.config = config or load_settings().database
        self._engine: Optional[Engine] = None

    @property
    def engine(self) -> Engine:
        if self._engine is None:
            self._engine = self._create_engine()
        return self._engine

    def _create_engine(self) -> Engine:
        logger.info("Connecting to PostgreSQL (%s:%s/%s)...", self.config.host, self.config.port, self.config.name)
        try:
            engine = create_engine(
                self.config.sqlalchemy_url,
                poolclass=QueuePool,
                pool_size=self.config.pool_size,
                max_overflow=self.config.max_overflow,
                pool_pre_ping=True,
            )
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return engine
        except SQLAlchemyError as exc:
            logger.error("Failed to connect to PostgreSQL: %s", exc)
            raise DatabaseConnectionError(f"Could not connect to PostgreSQL: {exc}") from exc

    @contextmanager
    def connection(self) -> Generator[Connection, None, None]:
        try:
            with self.engine.connect() as conn:
                yield conn
        except SQLAlchemyError as exc:
            logger.error("Database operation failed: %s", exc)
            raise DatabaseConnectionError(f"Database operation failed: {exc}") from exc

    def resolve_schema_info(self) -> Dict[str, str]:
        """Inspect PostgreSQL schema to resolve indicator table, price table, and date column names."""
        try:
            inspector = inspect(self.engine)
            tables = set(inspector.get_table_names())
        except SQLAlchemyError as exc:
            logger.error("Failed to inspect database tables: %s", exc)
            raise DatabaseConnectionError(f"Failed to inspect database tables: {exc}") from exc

        if "technical_indicators" in tables:
            indicator_table = "technical_indicators"
        elif "indicators" in tables:
            indicator_table = "indicators"
        else:
            msg = f"Missing indicator table (expected 'technical_indicators' or 'indicators', found: {sorted(tables)})"
            logger.error(msg)
            raise DatabaseConnectionError(msg)

        if "stock_prices" in tables:
            price_table = "stock_prices"
        elif "stock_price" in tables:
            price_table = "stock_price"
        else:
            msg = f"Missing stock prices table (expected 'stock_prices', found: {sorted(tables)})"
            logger.error(msg)
            raise DatabaseConnectionError(msg)

        price_cols = {col["name"] for col in inspector.get_columns(price_table)}
        if "date_time" in price_cols:
            price_date_col = "date_time"
        elif "datetime" in price_cols:
            price_date_col = "datetime"
        else:
            msg = f"Table '{price_table}' is missing 'date_time' / 'datetime' column."
            logger.error(msg)
            raise DatabaseConnectionError(msg)

        ind_cols = {col["name"] for col in inspector.get_columns(indicator_table)}
        required_ind_cols = {
            "stock_id",
            "datetime",
            "atr",
            "bollinger_lower",
            "bollinger_upper",
            "bollinger_width",
            "ema_12",
            "ema_26",
            "macd",
            "macd_hist",
            "macd_signal",
            "obv",
            "rsi",
            "sma_20",
        }
        missing_ind = required_ind_cols - ind_cols
        if missing_ind:
            msg = f"Table '{indicator_table}' is missing required columns: {sorted(missing_ind)}"
            logger.error(msg)
            raise DatabaseConnectionError(msg)

        return {
            "indicator_table": indicator_table,
            "price_table": price_table,
            "price_date_col": price_date_col,
        }

    def check_and_ensure_indexes(self, create_if_missing: bool = True) -> Dict[str, List[str]]:
        """Check existing indexes on indicator and price tables and create (stock_id, datetime) indexes if missing."""
        schema_info = self.resolve_schema_info()
        ind_table = schema_info["indicator_table"]
        price_table = schema_info["price_table"]
        price_date_col = schema_info["price_date_col"]

        existing: Dict[str, List[str]] = {ind_table: [], price_table: []}
        with self.connection() as conn:
            for tbl in (ind_table, price_table):
                rows = conn.execute(
                    text("SELECT indexname, indexdef FROM pg_indexes WHERE tablename = :tbl"),
                    {"tbl": tbl},
                ).fetchall()
                existing[tbl] = [f"{r[0]}: {r[1]}" for r in rows]

            has_ind_idx = any("stock_id" in idx_def and "datetime" in idx_def for idx_def in existing[ind_table])
            has_price_idx = any("stock_id" in idx_def for idx_def in existing[price_table])

            if create_if_missing and not has_ind_idx:
                logger.info("Creating index idx_indicators_stock_datetime on %s(stock_id, datetime)...", ind_table)
                conn.execute(
                    text(
                        f"CREATE INDEX IF NOT EXISTS idx_indicators_stock_datetime "
                        f"ON {ind_table}(stock_id, datetime);"
                    )
                )
                conn.commit()

            if create_if_missing and not has_price_idx:
                logger.info(
                    "Creating index idx_stock_prices_stock_datetime on %s(stock_id, %s)...",
                    price_table,
                    price_date_col,
                )
                conn.execute(
                    text(
                        f"CREATE INDEX IF NOT EXISTS idx_stock_prices_stock_datetime "
                        f"ON {price_table}(stock_id, {price_date_col});"
                    )
                )
                conn.commit()

        logger.info(
            "Verified PostgreSQL indexes: %d on %s, %d on %s",
            len(existing[ind_table]),
            ind_table,
            len(existing[price_table]),
            price_table,
        )
        return existing

    def close(self) -> None:
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None
