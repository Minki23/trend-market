from typing import Generator, List, Optional, Sequence

import pandas as pd
from sqlalchemy import text

from src.config.settings import Settings, load_settings, logger
from src.data.database import DatabaseManager


class DataLoader:
    """Loads historical indicator and OHLCV price data from PostgreSQL in memory-controlled chunks."""

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        self.settings = settings or load_settings()
        self.db = db_manager or DatabaseManager(self.settings.database)
        self._schema_info = None

    @property
    def schema_info(self) -> dict:
        if self._schema_info is None:
            self._schema_info = self.db.resolve_schema_info()
        return self._schema_info

    def get_available_stock_ids(
        self,
        start_date: Optional[str] = None,
        min_rows: int = 250,
        limit: Optional[int] = None,
    ) -> List[int]:
        """Fetch stock_ids that have at least `min_rows` records since `start_date`."""
        ind_table = self.schema_info["indicator_table"]
        where_clauses = []
        params: dict = {"min_rows": min_rows}
        if start_date:
            where_clauses.append("i.datetime >= :start_date")
            params["start_date"] = start_date

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        limit_sql = "LIMIT :limit" if limit else ""
        if limit:
            params["limit"] = int(limit)

        query = text(
            f"""
            SELECT i.stock_id
            FROM {ind_table} i
            {where_sql}
            GROUP BY i.stock_id
            HAVING COUNT(*) >= :min_rows
            ORDER BY i.stock_id ASC
            {limit_sql}
            """
        )
        with self.db.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        stock_ids = [int(r[0]) for r in rows]
        return stock_ids

    def load_stock_metadata(self, stock_ids: Optional[Sequence[int]] = None) -> pd.DataFrame:
        """Load stock descriptive attributes (sector, industry, market, ticker) from stocks table."""
        where_sql = ""
        params: dict = {}
        if stock_ids:
            where_sql = "WHERE s.stock_id = ANY(:stock_ids)"
            params["stock_ids"] = list(stock_ids)

        query = text(
            f"""
            SELECT
                s.stock_id,
                s.ticker,
                COALESCE(s.sector, 'UNKNOWN') AS sector,
                COALESCE(s.market, 'UNKNOWN') AS market
            FROM stocks s
            {where_sql}
            ORDER BY s.stock_id ASC
            """
        )
        with self.db.connection() as conn:
            df = pd.read_sql(query, conn, params=params)
        return df

    def build_select_query(
        self,
        filter_by_stock_ids: bool = False,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> str:
        """Construct the SQL query joining indicators and stock_prices on stock_id + datetime."""
        ind_table = self.schema_info["indicator_table"]
        price_table = self.schema_info["price_table"]
        price_date_col = self.schema_info["price_date_col"]

        conditions = []
        if filter_by_stock_ids:
            conditions.append("i.stock_id = ANY(:stock_ids)")
        if start_date:
            conditions.append("i.datetime >= :start_date")
            conditions.append(f"p.{price_date_col} >= :start_date")
        if end_date:
            conditions.append("i.datetime <= :end_date")
            conditions.append(f"p.{price_date_col} <= :end_date")

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        return f"""
            SELECT
                i.indicator_id,
                i.stock_id,
                i.datetime,
                i.atr,
                i.bollinger_lower,
                i.bollinger_upper,
                i.bollinger_width,
                i.date_continuity,
                i.ema_12,
                i.ema_26,
                i.macd,
                i.macd_hist,
                i.macd_signal,
                i.obv,
                i.rsi,
                i.sma_20,
                i.two_crows,
                p.open,
                p.high,
                p.low,
                p.close,
                p.volume
            FROM {ind_table} i
            JOIN {price_table} p
                ON i.stock_id = p.stock_id
                AND i.datetime = p.{price_date_col}
            {where_clause}
            ORDER BY i.stock_id ASC, i.datetime ASC
        """

    def iter_chunks_by_stock_batches(
        self,
        stock_ids: Sequence[int],
        batch_size: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Generator[pd.DataFrame, None, None]:
        """Yield DataFrames chunk by chunk, grouped by batches of stock_id."""
        b_size = batch_size or self.settings.database.stock_batch_size
        sql = text(
            self.build_select_query(
                filter_by_stock_ids=True,
                start_date=start_date,
                end_date=end_date,
            )
        )
        stock_list = [int(s) for s in stock_ids]
        for idx in range(0, len(stock_list), b_size):
            batch_ids = stock_list[idx : idx + b_size]
            params: dict = {"stock_ids": batch_ids}
            if start_date:
                params["start_date"] = start_date
            if end_date:
                params["end_date"] = end_date

            with self.db.connection() as conn:
                chunk_df = pd.read_sql(sql, conn, params=params)

            if not chunk_df.empty:
                chunk_df["datetime"] = pd.to_datetime(chunk_df["datetime"])
                yield chunk_df

    def iter_chunks_by_date_range(
        self,
        date_ranges: Sequence[tuple[str, str]],
        stock_ids: Optional[Sequence[int]] = None,
    ) -> Generator[pd.DataFrame, None, None]:
        """Yield DataFrames chunk by chunk for specified (start_date, end_date) intervals."""
        has_stocks = stock_ids is not None and len(stock_ids) > 0
        sql = text(
            self.build_select_query(
                filter_by_stock_ids=has_stocks,
                start_date="placeholder",
                end_date="placeholder",
            )
        )
        for start_dt, end_dt in date_ranges:
            params: dict = {"start_date": start_dt, "end_date": end_dt}
            if has_stocks:
                params["stock_ids"] = [int(s) for s in stock_ids]  # type: ignore[arg-type]
            with self.db.connection() as conn:
                chunk_df = pd.read_sql(sql, conn, params=params)
            if not chunk_df.empty:
                chunk_df["datetime"] = pd.to_datetime(chunk_df["datetime"])
                yield chunk_df

    def load_data(
        self,
        stock_ids: Optional[Sequence[int]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        max_stocks: Optional[int] = None,
        batch_size: Optional[int] = None,
    ) -> pd.DataFrame:
        """Load dataset in controlled chunks and log summary statistics."""
        eff_start = start_date if start_date is not None else self.settings.data.start_date
        eff_end = end_date if end_date is not None else self.settings.data.end_date
        eff_max_stocks = max_stocks if max_stocks is not None else self.settings.data.max_stocks

        if stock_ids is None:
            stock_ids = self.get_available_stock_ids(
                start_date=eff_start,
                min_rows=self.settings.data.min_history_rows,
                limit=eff_max_stocks,
            )

        if not stock_ids:
            logger.warning("No stocks matched the query criteria.")
            return pd.DataFrame()

        chunks: List[pd.DataFrame] = []
        total_rows = 0
        for chunk in self.iter_chunks_by_stock_batches(
            stock_ids=stock_ids,
            batch_size=batch_size,
            start_date=eff_start,
            end_date=eff_end,
        ):
            total_rows += len(chunk)
            chunks.append(chunk)

        if not chunks:
            logger.warning("Loaded 0 records from PostgreSQL.")
            return pd.DataFrame()

        df = pd.concat(chunks, ignore_index=True)
        min_dt = df["datetime"].min().strftime("%Y-%m-%d")
        max_dt = df["datetime"].max().strftime("%Y-%m-%d")
        n_stocks = df["stock_id"].nunique()

        logger.info("Loaded %s records", f"{len(df):,}")
        logger.info("Stocks: %s", f"{n_stocks:,}")
        logger.info("Date range: %s - %s", min_dt, max_dt)
        return df

    def load_latest_stock_history(
        self,
        stock_ids: Optional[Sequence[int]] = None,
        lookback_days: int = 90,
        batch_size: Optional[int] = None,
    ) -> pd.DataFrame:
        """Load recent history for one or many stocks to run inference/prediction."""
        ind_table = self.schema_info["indicator_table"]
        with self.db.connection() as conn:
            if stock_ids is not None and len(stock_ids) > 0:
                max_dt_row = conn.execute(
                    text(f"SELECT MAX(datetime) FROM {ind_table} WHERE stock_id = ANY(:sids)"),
                    {"sids": [int(s) for s in stock_ids]},
                ).fetchone()
            else:
                max_dt_row = conn.execute(text(f"SELECT MAX(datetime) FROM {ind_table}")).fetchone()
        if not max_dt_row or max_dt_row[0] is None:
            return pd.DataFrame()

        max_dt = pd.Timestamp(max_dt_row[0])
        cutoff_dt = (max_dt - pd.Timedelta(days=lookback_days)).strftime("%Y-%m-%d")

        if stock_ids is None:
            with self.db.connection() as conn:
                rows = conn.execute(
                    text(
                        f"SELECT DISTINCT stock_id FROM {ind_table} "
                        f"WHERE datetime >= :cutoff ORDER BY stock_id ASC"
                    ),
                    {"cutoff": cutoff_dt},
                ).fetchall()
            stock_ids = [int(r[0]) for r in rows]

        return self.load_data(
            stock_ids=stock_ids,
            start_date=cutoff_dt,
            end_date=max_dt.strftime("%Y-%m-%d"),
            batch_size=batch_size,
        )
