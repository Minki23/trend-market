import asyncio
import logging

from config import configure_logging, load_settings
from database_client import DatabaseClient
from price_service import PriceService
from sender import YfinanceSender
from stock_service import StockService
from subscriber import YfinanceSubscriber
from ticker_exclusion_store import TickerExclusionStore
from ticker_loader import TickerLoader
from yfinance_client import YfinanceClient

configure_logging()
logger = logging.getLogger(__name__)


class Application:
    def __init__(self):
        settings = load_settings()
        sender = YfinanceSender(settings.mqtt_host, settings.mqtt_port)
        self.tickers = TickerLoader(settings.ticker_csv_path).load()
        exclusion_store = TickerExclusionStore(settings.excluded_tickers_path)
        self.database = DatabaseClient(
            settings.database_tickers_url,
            settings.database_api_timeout,
            exclusion_store,
        )
        yfinance_client = YfinanceClient()
        self.stock_service = StockService(
            yfinance_client,
            sender,
            exclusion_store,
            settings.batch_size,
        )
        self.price_service = PriceService(
            yfinance_client,
            sender,
            settings.max_workers,
        )
        self.subscriber = YfinanceSubscriber(
            settings.mqtt_host,
            settings.mqtt_port,
        )

    def on_message(self, client, userdata, message):
        logger.info(
            "Received MQTT message on topic %s (%d bytes)",
            message.topic,
            len(message.payload),
        )
        try:
            if message.topic == "fetch_stocks":
                asyncio.run(self.pull_missing_stocks())
            elif message.topic == "fetch_prices":
                asyncio.run(self.price_service.pull(message.payload))
            else:
                logger.warning("Ignoring unsupported MQTT topic: %s", message.topic)
        except Exception:
            logger.exception(
                "Unhandled error while processing MQTT topic %s",
                message.topic,
            )

    async def pull_missing_stocks(self):
        missing = await self.database.get_missing_tickers(self.tickers)
        if not missing:
            logger.info("No missing tickers found; skipping stock pull")
            return
        await self.stock_service.pull_missing(missing)

    def run(self):
        logger.info("Starting MQTT subscriber loop")
        self.subscriber.subscribe(
            ["fetch_stocks", "fetch_prices"],
            self.on_message,
        )


if __name__ == "__main__":
    Application().run()
