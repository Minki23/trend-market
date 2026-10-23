import json
import logging

import pandas as pd
import asyncio

from concurrent_fetcher import ConcurrentFetcher
from yfinance.exceptions import YFRateLimitError

logger = logging.getLogger(__name__)


def optional_float(value):
    return None if pd.isna(value) else float(value)


def optional_int(value):
    return None if pd.isna(value) else int(value)


def local_datetime_string(value):
    timestamp = pd.to_datetime(value, errors="coerce")
    if pd.isna(timestamp):
        return None
    if getattr(timestamp, "tzinfo", None) is not None:
        timestamp = timestamp.tz_localize(None)
    return timestamp.isoformat(timespec="seconds")


class PriceService:
    def __init__(self, yfinance_client, sender, max_workers, rate_limit_wait_seconds=120):
        self.yfinance_client = yfinance_client
        self.sender = sender
        self.fetcher = ConcurrentFetcher(
            self.yfinance_client.get_price_history,
            max_workers,
        )
        self.rate_limit_wait_seconds = float(rate_limit_wait_seconds)

    def _build_payload(self, ticker, history):
        prices = []
        for _, row in history.copy().reset_index().iterrows():
            prices.append({
                "ticker": ticker,
                "datetime": local_datetime_string(row.get("Date")),
                "open": optional_float(row.get("Open")),
                "high": optional_float(row.get("High")),
                "low": optional_float(row.get("Low")),
                "close": optional_float(row.get("Close")),
                "volume": optional_int(row.get("Volume")),
                "adjustedClose": optional_float(row.get("Adj Close", row.get("Close"))),
                "timestamp": local_datetime_string(row.get("Date")),
            })
        return prices

    def _summarize_info(self, info):
        if not info or not isinstance(info, dict):
            return None
        keys = [
            "symbol",
            "shortName",
            "longName",
            "exchangeTimezoneName",
            "exchange",
        ]
        summary = {k: info.get(k) for k in keys if info.get(k) is not None}
        return summary

    async def pull(self, payload):
        tickers = sorted(json.loads(payload.decode("utf-8")))
        total = len(tickers)
        logger.info("Starting price pull for %d tickers", total)
        sent = skipped = failed = 0

        try:
            async for ticker, history in self.fetcher.fetch_all(tickers):
                if isinstance(history, Exception):
                    failed += 1
                    logger.error("Error fetching price history for %s", ticker, exc_info=history)
                    continue
                if history is None or history.empty:
                    skipped += 1
                    logger.warning("Skipping %s: no history data", ticker)
                    continue
                prices = self._build_payload(ticker, history)
                await self.sender.send_message("price", json.dumps(prices, ensure_ascii=False))
                logger.info("Sent %d price records for %s", len(prices), ticker)
                sent += 1
        except Exception:
            failed += 1
            logger.exception("Error processing price task")

        logger.info("Price pull finished: sent=%d skipped=%d failed=%d total=%d", sent, skipped, failed, len(tickers))