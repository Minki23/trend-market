import logging

import pandas as pd

logger = logging.getLogger(__name__)


class TickerLoader:
    def __init__(self, csv_path):
        self.csv_path = csv_path

    def load(self):
        logger.info("Loading tickers from CSV: %s", self.csv_path)
        try:
            dataframe = pd.read_csv(self.csv_path)
            if "ticker" not in dataframe.columns:
                raise KeyError(
                    f"'ticker' column not found. Available columns: {list(dataframe.columns)}"
                )

            tickers = dataframe["ticker"].dropna().astype(str).str.strip()
            tickers = tickers[tickers != ""].unique().tolist()
            logger.info("Loaded %d tickers from CSV", len(tickers))
            return tickers
        except Exception:
            logger.exception("Failed to load tickers from CSV: %s", self.csv_path)
            return []