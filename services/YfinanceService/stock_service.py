import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor

from yfinance.exceptions import YFRateLimitError

logger = logging.getLogger(__name__)

STOCK_FIELDS = [
    "ticker", "name", "longName", "shortName", "tradeable", "displayName",
    "symbol", "sector", "sectorKey", "industry", "industryKey", "market",
    "quoteType", "address1", "city", "state", "zip", "country", "region",
    "currency", "financialCurrency", "exchange", "fullExchangeName",
    "exchangeTimezoneName", "exchangeTimezoneShortName", "website", "irWebsite",
    "phone", "fullTimeEmployees", "longBusinessSummary", "messageBoardId",
    "language", "typeDisp", "quoteSourceName",
]


def build_stock_payload(ticker, info):
    payload = {field: info.get(field) for field in STOCK_FIELDS}
    payload["ticker"] = payload.get("ticker") or ticker
    payload["name"] = payload.get("longName") or payload.get("shortName") or ticker
    return payload


class StockService:
    def __init__(
        self,
        yfinance_client,
        sender,
        exclusion_store,
        batch_size,
        max_workers,
        rate_limit_wait_seconds=120,
    ):
        self.yfinance_client = yfinance_client
        self.sender = sender
        self.exclusion_store = exclusion_store
        self.batch_size = batch_size
        self.max_workers = max_workers
        self.rate_limit_wait_seconds = rate_limit_wait_seconds

    def _get_info(self, ticker):
        return self.yfinance_client.get_info(ticker)

    async def pull_missing(self, tickers):
        total = len(tickers)
        batches = (total + self.batch_size - 1) // self.batch_size
        logger.info("Starting stock pull for %d tickers in %d batches", total, batches)
        loop = asyncio.get_running_loop()
        sent = 0
        skipped = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            for start in range(0, total, self.batch_size):
                batch_number = start // self.batch_size + 1
                batch = tickers[start:start + self.batch_size]
                logger.info(
                    "Starting stock batch %d/%d with %d tickers using %d workers",
                    batch_number,
                    batches,
                    len(batch),
                    self.max_workers,
                )
                while True:
                    tasks = [
                        loop.run_in_executor(executor, self._get_info, ticker)
                        for ticker in batch
                    ]

                    try:
                        results = await asyncio.gather(*tasks)
                        break
                    except YFRateLimitError:
                        for task in tasks:
                            if not task.done():
                                task.cancel()
                        await asyncio.gather(*tasks, return_exceptions=True)
                        logger.warning(
                            "Rate limit reached in stock batch %d/%d; "
                            "retrying in %.0f seconds",
                            batch_number,
                            batches,
                            self.rate_limit_wait_seconds,
                        )
                        await asyncio.sleep(self.rate_limit_wait_seconds)

                payloads = []
                for ticker, info in zip(batch, results):
                    if not info or not isinstance(info, dict):
                        skipped += 1
                        self.exclusion_store.add(ticker)
                        logger.warning("Skipping %s: no usable stock info", ticker)
                        continue
                    payloads.append(build_stock_payload(ticker, info))

                if payloads:
                    await self.sender.send_message(
                        "stock",
                        json.dumps(payloads, ensure_ascii=False),
                    )
                    sent += len(payloads)
                    logger.info(
                        "Pushed stock batch %d/%d: %d stocks",
                        batch_number,
                        batches,
                        len(payloads),
                    )

        logger.info("Stock pull finished: sent=%d skipped=%d total=%d", sent, skipped, total)