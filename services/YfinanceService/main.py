import asyncio
import contextlib
import io
import json
import logging
from concurrent.futures import ThreadPoolExecutor
import mlcroissant as mlc
import pandas as pd
import yfinance as yf

from decorator import checkStatus
import subscriber as subscriber
import sender as sender

logger = logging.getLogger(__name__)
croissant_dataset = None
try:
    croissant_dataset = mlc.Dataset('https://www.kaggle.com/datasets/nelgiriyewithana/world-stock-prices-daily-updating/croissant/download')
except Exception as e:
    logger.error("Failed to load croissant dataset: %s", e)
    croissant_dataset = None

logging.basicConfig(
    filename="yfinance_service.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

subscriber = subscriber.YfinanceSubscriber("mosquitto", 1883)
sender = sender.YfinanceSender("mosquitto", 1883)

logging.getLogger("yfinance").setLevel(logging.DEBUG)
logging.getLogger("urllib3").setLevel(logging.DEBUG)



STOCK_FIELDS = [
    "ticker",
    "name",
    "longName",
    "shortName",
    "displayName",
    "symbol",
    "sector",
    "sectorKey",
    "industry",
    "industryKey",
    "market",
    "quoteType",
    "address1",
    "city",
    "state",
    "zip",
    "country",
    "region",
    "currency",
    "financialCurrency",
    "exchange",
    "fullExchangeName",
    "exchangeTimezoneName",
    "exchangeTimezoneShortName",
    "website",
    "irWebsite",
    "phone",
    "fullTimeEmployees",
    "longBusinessSummary",
    "messageBoardId",
    "language",
    "typeDisp",
    "quoteSourceName",
]

data = []
if croissant_dataset is not None:
    csv_path = "data/core_listings.csv"
    try:
        df = pd.read_csv(csv_path)
        data = df["Ticker"].dropna().astype(str).str.strip().unique().tolist()
    except (FileNotFoundError, KeyError, pd.errors.ParserError):
        try:
            records = croissant_dataset.records()
            for record in records:
                if not isinstance(record, dict):
                    continue
                ticker = next(
                    (
                        value for key, value in record.items()
                        if str(key).lower().split("/")[-1]
                        in {"ticker", "symbol", "ticker_symbol"}
                    ),
                    None,
                )
                if ticker is not None:
                    data.append(str(ticker))
            data = list(dict.fromkeys(data))
        except Exception as exc:
            logger.warning("Failed to read Croissant records: %s", exc)

@checkStatus
def get_info_from_yfinance(ticker):

    try:
        stock = yf.Ticker(ticker)

        with contextlib.redirect_stderr(io.StringIO()):
            return stock.info

    except Exception:
        return None

def build_stock_payload(ticker, info):

    payload = {
        field: info.get(field)
        for field in STOCK_FIELDS
    }

    payload["ticker"] = (
        payload.get("ticker")
        or ticker
    )

    payload["name"] = (
        payload.get("longName")
        or payload.get("shortName")
        or ticker
    )

    return payload

async def pull_stocks():
    logger.info("Pulling stock info from yfinance...")
    max_workers = 15

    loop = asyncio.get_running_loop()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:

        tasks = [
            loop.run_in_executor(
                executor,
                get_info_from_yfinance,
                ticker
            )
            for ticker in data
        ]
        logger.info("Waiting for tasks to complete...")

        results = await asyncio.gather(*tasks)

    for ticker, info in zip(data, results):
        logger.info("Processing %s...", ticker)
        if not info or not isinstance(info, dict):
            continue

        payload = build_stock_payload(
            ticker,
            info
        )

        await sender.send_message(
            "stock",
            json.dumps(
                payload,
                ensure_ascii=False
            )
        )

        await asyncio.sleep(0.1)

def pull_ticker_prices(ticker):

    try:
        stock = yf.Ticker(ticker)
        return stock.history(period="max")

    except Exception:
        return None

async def process_ticker(executor, loop, ticker):
    history = await loop.run_in_executor(
        executor,
        pull_ticker_prices,
        ticker
    )

    return ticker, history


def _to_optional_float(value):
    if pd.isna(value):
        return None
    return float(value)


def _to_optional_int(value):
    if pd.isna(value):
        return None
    return int(value)


def _to_local_datetime_string(value):
    timestamp = pd.to_datetime(value, errors="coerce")

    if pd.isna(timestamp):
        return None

    if getattr(timestamp, "tzinfo", None) is not None:
        timestamp = timestamp.tz_localize(None)

    return timestamp.isoformat(timespec="seconds")
    
async def async_pull_prices(payload):
    logger.info("Starting price pull")

    tickers = sorted(json.loads(payload.decode("utf-8")))
    total_tickers = len(tickers)
    logger.info("Tickers to process: %s", total_tickers)
    loop = asyncio.get_running_loop()
    max_workers = 15
    sent_count = 0
    skipped_count = 0
    failed_count = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:

        tasks = [
            process_ticker(executor, loop, ticker)
            for ticker in tickers
        ]

        for task in asyncio.as_completed(tasks):
            try:
                ticker, history = await task

                if history is None or history.empty:
                    skipped_count += 1
                    logger.warning("Skipping %s: no history data", ticker)
                    continue

                logger.info("Processing %s", ticker)

                history_rows = history.copy().reset_index()

                prices_payload = []

                for _, row in history_rows.iterrows():
                    price = {
                        "ticker": ticker,
                        "datetime": _to_local_datetime_string(row.get("Date")),
                        "open": _to_optional_float(row.get("Open")),
                        "high": _to_optional_float(row.get("High")),
                        "low": _to_optional_float(row.get("Low")),
                        "close": _to_optional_float(row.get("Close")),
                        "volume": _to_optional_int(row.get("Volume")),
                        "adjustedClose": _to_optional_float(
                            row.get("Adj Close", row.get("Close"))
                        )
                    }
                    prices_payload.append(price)


                await sender.send_message(
                    "price",
                    json.dumps(
                        prices_payload,
                        ensure_ascii=False
                    )
                )

                sent_count += 1
                logger.info(
                    "Sent price payloads for %s (%s/%s)",
                    ticker,
                    sent_count,
                    total_tickers
                )
                prices_payload.clear()

                await asyncio.sleep(0.1)

            except Exception as e:
                failed_count += 1
                logger.exception(
                    "Error processing ticker task: %s",
                    e
                )

    logger.info(
        "Price pull finished. sent=%s skipped=%s failed=%s total=%s",
        sent_count,
        skipped_count,
        failed_count,
        total_tickers
    )



def on_message(client, userdata, message):

    if message.topic == "fetch_stocks":
        asyncio.run(pull_stocks())

    elif message.topic == "fetch_prices":
        asyncio.run(
            async_pull_prices(message.payload)
        )


logger.info("Subscribed to topics: fetch_stocks, fetch_prices")
subscriber.subscribe(
    ["fetch_stocks", "fetch_prices"],
    on_message
)