import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class TickerExclusionStore:
    def __init__(self, path):
        self.path = Path(path)

    def load(self):
        if not self.path.exists():
            logger.info("Ticker exclusion file does not exist yet: %s", self.path)
            return set()

        try:
            excluded = {
                line.strip().upper()
                for line in self.path.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.lstrip().startswith("#")
            }
            logger.info("Loaded %d excluded tickers from %s", len(excluded), self.path)
            return excluded
        except OSError:
            logger.exception("Failed to read ticker exclusion file: %s", self.path)
            return set()

    def add(self, ticker):
        normalized_ticker = str(ticker).strip().upper()
        if not normalized_ticker:
            return

        excluded = self.load()
        if normalized_ticker in excluded:
            return

        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as file:
                file.write(f"{normalized_ticker}\n")
            logger.info("Added ticker to exclusion file: %s", normalized_ticker)
        except OSError:
            logger.exception("Failed to save excluded ticker: %s", normalized_ticker)