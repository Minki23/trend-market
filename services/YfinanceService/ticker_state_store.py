import csv
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class TickerStateStore:
    def __init__(self, path):
        self.path = Path(path)
        self._data = {}  # ticker -> {has_data: bool, has_prices: bool}
        self._load()

    def _load(self):
        if not self.path.exists():
            logger.info("Ticker state file does not exist yet: %s", self.path)
            return
        try:
            with self.path.open("r", encoding="utf-8", newline="") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    t = (row.get("ticker") or "").strip().upper()
                    if not t:
                        continue
                    has_data = (row.get("has_data") or "").strip().lower() in ("1", "true", "yes")
                    has_prices = (row.get("has_prices") or "").strip().lower() in ("1", "true", "yes")
                    self._data[t] = {"has_data": has_data, "has_prices": has_prices}
            logger.info("Loaded %d ticker states from %s", len(self._data), self.path)
        except OSError:
            logger.exception("Failed to read ticker state file: %s", self.path)

    def _save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("w", encoding="utf-8", newline="") as fh:
                writer = csv.DictWriter(fh, fieldnames=["ticker", "has_data", "has_prices"])
                writer.writeheader()
                for ticker, vals in sorted(self._data.items()):
                    writer.writerow({
                        "ticker": ticker,
                        "has_data": "1" if vals.get("has_data") else "0",
                        "has_prices": "1" if vals.get("has_prices") else "0",
                    })
            logger.info("Saved %d ticker states to %s", len(self._data), self.path)
        except OSError:
            logger.exception("Failed to save ticker state file: %s", self.path)

    def get(self, ticker):
        return self._data.get(str(ticker).strip().upper(), {"has_data": False, "has_prices": False})

    def set_has_data(self, ticker, value=True):
        t = str(ticker).strip().upper()
        if not t:
            return
        entry = self._data.setdefault(t, {"has_data": False, "has_prices": False})
        entry["has_data"] = bool(value)
        self._save()

    def set_has_prices(self, ticker, value=True):
        t = str(ticker).strip().upper()
        if not t:
            return
        entry = self._data.setdefault(t, {"has_data": False, "has_prices": False})
        entry["has_prices"] = bool(value)
        self._save()

    def should_pull_stock(self, ticker):
        return not self.get(ticker)["has_data"]

    def should_pull_prices(self, ticker):
        return not self.get(ticker)["has_prices"]
