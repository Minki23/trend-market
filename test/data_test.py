import pandas as pd
import json
import yfinance as yf

class ListingsBrowser:
    def __init__(self, csv_path: str):
        self.df = pd.read_csv(csv_path)

    # -------------------------
    # General information
    # -------------------------
    def info(self):
        print("\n=== Dataset Info ===")
        print(f"Rows: {len(self.df):,}")
        print(f"Columns: {len(self.df.columns)}")
        print("\nColumns:")
        print(list(self.df.columns))

        print("\nMemory usage:")
        print(f"{self.df.memory_usage(deep=True).sum() / 1024**2:.2f} MB")

    def statistics(self):
        print("\n=== Statistics ===")

        print("\nMissing values:")
        print(self.df.isna().sum().sort_values(ascending=False))

        print("\nUnique values:")
        print(self.df.nunique().sort_values(ascending=False))

        print("\nDuplicate rows:")
        print(self.df.duplicated().sum())

    # -------------------------
    # Browse data
    # -------------------------
    def head(self, n=5):
        return self.df.head(n)

    def tail(self, n=5):
        return self.df.tail(n)

    def sample(self, n=5):
        return self.df.sample(n)

    # -------------------------
    # Searching
    # -------------------------
    def search_name(self, text):
        return self.df[
            self.df["name"].str.contains(text, case=False, na=False)
        ]

    def search_ticker(self, ticker):
        return self.df[
            self.df["ticker"].str.upper() == ticker.upper()
        ]

    def filter_exchange(self, exchange):
        return self.df[
            self.df["exchange"] == exchange
        ]

    def filter_country(self, country):
        return self.df[
            self.df["country"] == country
        ]

    def filter_asset_type(self, asset_type):
        return self.df[
            self.df["asset_type"] == asset_type
        ]

    # -------------------------
    # Column statistics
    # -------------------------
    def value_counts(self, column, top=20):
        return self.df[column].value_counts().head(top)

    # -------------------------
    # Yahoo Finance lookup
    # -------------------------
    def yfinance_info(self, ticker):
        symbol = ticker if ticker.endswith(".WA") else f"{ticker}.WA"
        stock = yf.Ticker(symbol)
        info = stock.info or {}

        fields = [
            "shortName",
            "longName",
            "symbol",
            "currency",
            "exchange",
            "marketCap",
            "sector",
            "industry",
            "website",
        ]

        print(f"\n=== {symbol} ===")
        for field in fields:
            if field in info and info[field] is not None:
                print(f"{field}: {info[field]}")

        return info

    # -------------------------
    # Quick summary
    # -------------------------
    def summary(self):
        print("\n========== DATASET SUMMARY ==========")
        print(f"Rows: {len(self.df):,}")
        print(f"Columns: {len(self.df.columns)}")
        print()

        for col in self.df.columns:
            missing = self.df[col].isna().sum()
            unique = self.df[col].nunique(dropna=True)

            print(
                f"{col:25} "
                f"Unique: {unique:8} "
                f"Missing: {missing:8}"
            )

        print("\nTop Exchanges:")
        print(self.df["exchange"].value_counts().head(10))

        print("\nTop Countries:")
        print(self.df["country"].value_counts().head(10))

        print("\nAsset Types:")
        print(self.df["asset_type"].value_counts())

        if "stock_sector" in self.df.columns:
            print("\nStock Sectors:")
            print(self.df["stock_sector"].value_counts().head(20))

        if "etf_category" in self.df.columns:
            print("\nETF Categories:")
            print(self.df["etf_category"].value_counts().head(20))

        print("====================================")

browser = ListingsBrowser("core_listings.csv")

browser.info()
browser.statistics()
browser.summary()


browser.head()

browser.sample(10)

browser.search_ticker("DNP")

browser.search_name("Apple")

browser.filter_exchange("NASDAQ")

results = []
for ticker in browser.filter_country("Poland").ticker.dropna().unique():
    info = browser.yfinance_info(ticker)
    results.append(info)

with open("poland_yfinance_info.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

browser.filter_asset_type("Stock")

browser.value_counts("exchange")

browser.value_counts("country")