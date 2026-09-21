import asyncio
import json
import logging
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)


class DatabaseClient:
    def __init__(self, tickers_url, timeout, exclusion_store):
        self.tickers_url = tickers_url
        self.timeout = timeout
        self.exclusion_store = exclusion_store

    def _fetch_tickers_sync(self):
        logger.info("Fetching existing tickers from %s", self.tickers_url)
        request = urllib.request.Request(
            self.tickers_url,
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            tickers = json.loads(response.read().decode("utf-8"))

        if not isinstance(tickers, list):
            raise ValueError("Database ticker endpoint must return a JSON list")

        normalized = {
            str(ticker).strip().upper()
            for ticker in tickers
            if ticker is not None and str(ticker).strip()
        }
        logger.info("Database returned %d existing tickers", len(normalized))
        return normalized

    async def get_missing_tickers(self, candidates):
        if not candidates:
            logger.warning("No candidate tickers available for database filtering")
            return []

        try:
            existing = await asyncio.to_thread(self._fetch_tickers_sync)
        except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError):
            logger.exception("Could not fetch database tickers; aborting stock pull")
            return []

        excluded = self.exclusion_store.load()
        known_tickers = existing | excluded
        logger.info(
            "Filtering against %d database tickers and %d excluded tickers",
            len(existing),
            len(excluded),
        )
        missing = [
            ticker
            for ticker in candidates
            if str(ticker).strip().upper() not in known_tickers
        ]
        logger.info(
            "Ticker filter finished: candidates=%d existing=%d missing=%d",
            len(candidates), len(existing), len(missing),
        )
        return missing