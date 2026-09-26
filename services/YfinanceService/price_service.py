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

        index = 0
        # process remaining tickers in a loop so we can pause/resume on rate limits
        while index < total:
            sublist = tickers[index:]
            rate_limited = False
            try:
                async for ticker, history in self.fetcher.fetch_all(sublist):
                    # detect rate-limit when history is an exception or when fetch_all raised
                    if isinstance(history, Exception):
                        # detect explicit YFRateLimitError or messages mentioning rate limit
                        is_rate_limit = isinstance(history, YFRateLimitError) or "rate limit" in str(history).lower()
                        if is_rate_limit:
                            logger.warning("Rate limit detected while fetching %s: %s", ticker, str(history))
                            # do not advance index; retry this ticker after sleeping
                            rate_limited = True
                            break
                        failed += 1
                        # Try to fetch basic info to help diagnose (may be rate-limited)
                        try:
                            info = self.yfinance_client.get_info(ticker)
                        except Exception as info_exc:
                            info = None
                            logger.debug("Failed to fetch ticker info for %s: %s", ticker, info_exc)

                        logger.error("Error fetching price history for %s: %s; info=%s", ticker, history, self._summarize_info(info), exc_info=history)
                        index += 1
                        continue
                    if history is None or history.empty:
                        skipped += 1
                        # Log a short summary to know whether the ticker exists/has metadata
                        try:
                            info = self.yfinance_client.get_info(ticker)
                        except Exception as info_exc:
                            info = None
                            logger.debug("Failed to fetch ticker info for %s: %s", ticker, info_exc)

                        logger.warning("Skipping %s: no history data; info=%s", ticker, self._summarize_info(info))
                        index += 1
                        continue

                    prices = self._build_payload(ticker, history)
                    await self.sender.send_message("price", json.dumps(prices, ensure_ascii=False))
                    sent += 1
                    index += 1
            except YFRateLimitError:
                logger.warning("RateLimit exception propagated from fetcher; sleeping %.1f seconds", self.rate_limit_wait_seconds)
                try:
                    await asyncio.sleep(self.rate_limit_wait_seconds)
                except asyncio.CancelledError:
                    logger.info("Price pull cancelled during rate limit sleep")
                    break
                # continue outer while to resume
                continue
            except Exception:
                failed += 1
                logger.exception("Error processing price task")
                break

            if rate_limited:
                # Sleep before retrying the same ticker
                rate_limited = False
                logger.warning("Pausing due to detected rate limit for %.1f seconds", self.rate_limit_wait_seconds)
                try:
                    await asyncio.sleep(self.rate_limit_wait_seconds)
                except asyncio.CancelledError:
                    logger.info("Price pull cancelled during rate limit sleep")
                    break
                continue

        logger.info("Price pull finished: sent=%d skipped=%d failed=%d total=%d", sent, skipped, failed, len(tickers))