import contextlib
import io
import logging

import yfinance as yf
from yfinance.exceptions import YFRateLimitError

logger = logging.getLogger(__name__)


class YfinanceClient:
    def get_info(self, ticker):
        logger.debug("Fetching stock info for %s", ticker)
        try:
            stock = yf.Ticker(ticker)
            with contextlib.redirect_stderr(io.StringIO()):
                info = stock.info
            logger.debug(
                "Fetched stock info for %s with %d fields",
                ticker,
                len(info) if isinstance(info, dict) else 0,
            )
            return info
        except YFRateLimitError:
            logger.warning("Rate limit exceeded while fetching stock info for %s", ticker)
            raise
        
        except YFRateLimitError:
            logger.warning("Rate limit exceeded while fetching price history for %s", ticker)
            raise
        except Exception:
            logger.exception("Failed to fetch stock info for %s", ticker)
            return None

    def get_price_history(self, ticker):
        logger.debug("Fetching price history for %s", ticker)
        try:
            history = yf.Ticker(ticker).history(period="max")
            logger.debug(
                "Fetched price history for %s: %d rows, %d columns",
                ticker, len(history), len(history.columns),
            )
            return history
        except Exception:
            logger.exception("Failed to fetch price history for %s", ticker)
            return None