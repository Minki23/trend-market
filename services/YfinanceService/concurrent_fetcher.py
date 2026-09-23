import asyncio
from concurrent.futures import ThreadPoolExecutor

from yfinance.exceptions import YFRateLimitError


class ConcurrentFetcher:
    def __init__(self, fetch, max_workers):
        self.fetch = fetch
        self.max_workers = max_workers

    def _fetch_one(self, ticker):
        try:
            return ticker, self.fetch(ticker)
        except YFRateLimitError:
            raise
        except Exception as error:
            return ticker, error

    async def fetch_all(self, tickers):
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            tasks = [
                loop.run_in_executor(executor, self._fetch_one, ticker)
                for ticker in tickers
            ]
            try:
                for task in asyncio.as_completed(tasks):
                    yield await task
            except YFRateLimitError:
                for task in tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                raise