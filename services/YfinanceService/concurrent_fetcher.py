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
        """
        Fetch tickers in chunks of size `max_workers` to avoid scheduling all requests
        at once. If a rate-limit is detected within a chunk, cancel remaining tasks
        in that chunk and propagate the YFRateLimitError so caller can back off.
        """
        loop = asyncio.get_running_loop()
        # iterate in chunks to limit how many tasks are started at once
        for i in range(0, len(tickers), self.max_workers):
            chunk = tickers[i : i + self.max_workers]
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                tasks = [loop.run_in_executor(executor, self._fetch_one, t) for t in chunk]
                try:
                    for task in asyncio.as_completed(tasks):
                        yield await task
                except YFRateLimitError:
                    # cancel remaining tasks in this chunk
                    for task in tasks:
                        if not task.done():
                            task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
                    raise