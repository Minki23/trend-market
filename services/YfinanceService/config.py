import logging
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    batch_size: int
    database_tickers_url: str
    database_api_timeout: float
    mqtt_host: str
    mqtt_port: int
    ticker_csv_path: str
    excluded_tickers_path: str
    max_workers: int


def load_settings():
    batch_size = int(os.getenv("BATCH_SIZE", "100"))
    if batch_size <= 0:
        raise ValueError("BATCH_SIZE must be greater than zero")

    database_api_url = os.getenv("DATABASE_API_URL", "http://localhost:8080").rstrip("/")
    return Settings(
        batch_size=batch_size,
        database_tickers_url=f"{database_api_url}/stocks/tickers",
        database_api_timeout=float(os.getenv("DATABASE_API_TIMEOUT", "10")),
        mqtt_host=os.getenv("MQTT_HOST", "mosquitto"),
        mqtt_port=int(os.getenv("MQTT_PORT", "1883")),
        ticker_csv_path=os.getenv("TICKER_CSV_PATH", "data/core_listings.csv"),
        excluded_tickers_path=os.getenv(
            "EXCLUDED_TICKERS_PATH",
            "data/excluded_tickers.txt",
        ),
        max_workers=int(os.getenv("MAX_WORKERS", "15")),
    )


def configure_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s:%(name)s:%(message)s",
    )