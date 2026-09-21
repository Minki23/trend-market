import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
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
    def __init__(self, yfinance_client, sender, max_workers):
        self.yfinance_client = yfinance_client
        self.sender = sender
        self.max_workers = max_workers

    def _fetch(self, ticker):
        return ticker, self.yfinance_client.get_price_history(ticker)

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
            })
        return prices

    async def pull(self, payload):
        tickers = sorted(json.loads(payload.decode("utf-8")))
        logger.info("Starting price pull for %d tickers", len(tickers))
        loop = asyncio.get_running_loop()
        sent = skipped = failed = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            tasks = [loop.run_in_executor(executor, self._fetch, ticker) for ticker in tickers]
            for task in asyncio.as_completed(tasks):
                try:
                    ticker, history = await task
                    if history is None or history.empty:
                        skipped += 1
                        logger.warning("Skipping %s: no history data", ticker)
                        continue
                    prices = self._build_payload(ticker, history)
                    await self.sender.send_message("price", json.dumps(prices, ensure_ascii=False))
                    sent += 1
                except YFRateLimitError:
                    for pending_task in tasks:
                        if not pending_task.done():
                            pending_task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
                    logger.warning("Rate limit reached; stopping price pull")
                    return
                except Exception:
                    failed += 1
                    logger.exception("Error processing price task")

        logger.info("Price pull finished: sent=%d skipped=%d failed=%d total=%d", sent, skipped, failed, len(tickers))