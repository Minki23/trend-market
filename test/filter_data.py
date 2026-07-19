"""Filter Polish stock data from poland_yfinance_info.json.

Outputs:
- poland_yfinance_info_clean.csv
- poland_yfinance_info_detailed.csv
- poland_yfinance_info_removed.csv
- poland_yfinance_info_summary.pdf
"""

from __future__ import annotations

import json
import math
import textwrap
from collections import Counter
from datetime import datetime
from pathlib import Path
from statistics import mean, median
from typing import Any, Dict, Iterable, List, Optional


BASE_DIR = Path(__file__).resolve().parent
INPUT_JSON = BASE_DIR / "poland_yfinance_info.json"
OUTPUT_CSV = BASE_DIR / "poland_yfinance_info_clean.csv"
OUTPUT_DETAILED_CSV = BASE_DIR / "poland_yfinance_info_detailed.csv"
OUTPUT_REMOVED_CSV = BASE_DIR / "poland_yfinance_info_removed.csv"
OUTPUT_PDF = BASE_DIR / "poland_yfinance_info_summary.pdf"
OUTPUT_CHAPTER_PDF = BASE_DIR / "poland_yfinance_info_chapters.pdf"
HISTORY_DIR = BASE_DIR / "stock_history_csv"


def _first_present(data: Dict[str, Any], keys: Iterable[str]) -> Any:
	for key in keys:
		value = data.get(key)
		if value not in (None, "", [], {}):
			return value
	return None


def _to_float(value: Any) -> Optional[float]:
	if value is None or isinstance(value, bool):
		return None
	try:
		if isinstance(value, (int, float)):
			if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
				return None
			return float(value)
		text = str(value).strip().replace(",", "")
		if not text:
			return None
		num = float(text)
		if math.isnan(num) or math.isinf(num):
			return None
		return num
	except Exception:
		return None


def _to_bool(value: Any) -> Optional[bool]:
	if isinstance(value, bool):
		return value
	if value is None:
		return None
	text = str(value).strip().lower()
	if text in {"true", "1", "yes", "y"}:
		return True
	if text in {"false", "0", "no", "n"}:
		return False
	return None


def evaluate_record(item: Dict[str, Any]) -> Dict[str, Any]:
	raw_symbol = _first_present(item, ["symbol", "ticker", "code", "name"])
	if not raw_symbol:
		return {
			"symbol": "",
			"name": "",
			"current_price": None,
			"previous_close": None,
			"market_cap": None,
			"currency": "",
			"exchange": "",
			"sector": "",
			"industry": "",
			"quote_type": "",
			"tradeable": None,
			"status": "removed",
			"reason": "missing symbol",
			"normalized": None,
		}

	symbol = str(raw_symbol).strip().upper()
	if not symbol:
		return {
			"symbol": "",
			"name": "",
			"current_price": None,
			"previous_close": None,
			"market_cap": None,
			"currency": "",
			"exchange": "",
			"sector": "",
			"industry": "",
			"quote_type": "",
			"tradeable": None,
			"status": "removed",
			"reason": "blank symbol",
			"normalized": None,
		}

	current_price = _to_float(_first_present(item, ["currentPrice", "regularMarketPrice", "lastPrice", "price"]))
	previous_close = _to_float(_first_present(item, ["previousClose", "prevClose", "close", "lastClose"]))
	market_cap = _to_float(_first_present(item, ["marketCap", "market_cap"]))
	currency = _first_present(item, ["currency", "financialCurrency"])
	exchange = _first_present(item, ["exchange", "fullExchangeName", "market"])
	sector = _first_present(item, ["sector"])
	industry = _first_present(item, ["industry"])
	long_name = _first_present(item, ["longName", "shortName", "title", "companyName", "displayName"])
	is_tradeable = _to_bool(_first_present(item, ["tradeable", "isTradeable", "tradable"]))
	quote_type = _first_present(item, ["quoteType", "type"])

	name = str(long_name).strip() if long_name else symbol
	currency_s = str(currency).strip() if currency else ""
	exchange_s = str(exchange).strip() if exchange else ""
	sector_s = str(sector).strip() if sector else ""
	industry_s = str(industry).strip() if industry else ""
	quote_type_s = str(quote_type).strip() if quote_type else ""

	if current_price is None or current_price <= 0:
		reason = "missing/invalid current price"
		return {
			"symbol": symbol,
			"name": name,
			"current_price": current_price,
			"previous_close": previous_close,
			"market_cap": market_cap,
			"currency": currency_s,
			"exchange": exchange_s,
			"sector": sector_s,
			"industry": industry_s,
			"quote_type": quote_type_s,
			"tradeable": is_tradeable,
			"status": "removed",
			"reason": reason,
			"normalized": None,
		}

	if previous_close is not None and previous_close <= 0:
		previous_close = None

	if market_cap is not None and market_cap < 0:
		return {
			"symbol": symbol,
			"name": name,
			"current_price": current_price,
			"previous_close": previous_close,
			"market_cap": market_cap,
			"currency": currency_s,
			"exchange": exchange_s,
			"sector": sector_s,
			"industry": industry_s,
			"quote_type": quote_type_s,
			"tradeable": is_tradeable,
			"status": "removed",
			"reason": "negative market cap",
			"normalized": None,
		}

	bad_types = {"CURRENCY", "ETF", "MUTUALFUND", "INDEX", "BOND", "CRYPTOCURRENCY", "OPTION", "FUTURE"}
	if quote_type and str(quote_type).strip().upper() in bad_types:
		return {
			"symbol": symbol,
			"name": name,
			"current_price": current_price,
			"previous_close": previous_close,
			"market_cap": market_cap,
			"currency": currency_s,
			"exchange": exchange_s,
			"sector": sector_s,
			"industry": industry_s,
			"quote_type": quote_type_s,
			"tradeable": is_tradeable,
			"status": "removed",
			"reason": f"filtered quote_type={quote_type_s}",
			"normalized": None,
		}

	price_change = None
	change_pct = None
	if previous_close is not None:
		price_change = current_price - previous_close
		if previous_close != 0:
			change_pct = (price_change / previous_close) * 100.0

	normalized = {
		"symbol": symbol,
		"name": name,
		"current_price": current_price,
		"previous_close": previous_close,
		"price_change": price_change,
		"change_pct": change_pct,
		"market_cap": market_cap,
		"market_cap_billion": (market_cap / 1_000_000_000.0) if isinstance(market_cap, (int, float)) else None,
		"currency": currency_s,
		"exchange": exchange_s,
		"sector": sector_s,
		"industry": industry_s,
		"quote_type": quote_type_s,
		"tradeable": True if is_tradeable is None else is_tradeable,
	}

	return {
		**normalized,
		"status": "kept",
		"reason": "ok",
		"normalized": normalized,
	}


def normalize_record(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
	return evaluate_record(item)["normalized"]


def load_input() -> List[Dict[str, Any]]:
	with INPUT_JSON.open("r", encoding="utf-8") as fh:
		data = json.load(fh)

	if isinstance(data, list):
		return [x for x in data if isinstance(x, dict)]

	if isinstance(data, dict):
		for key in ("data", "stocks", "items", "results"):
			if isinstance(data.get(key), list):
				return [x for x in data[key] if isinstance(x, dict)]

		# Important fix: support {"PKN.WA": {...}, "CDR.WA": {...}} shape.
		dict_values = [v for v in data.values() if isinstance(v, dict)]
		if dict_values and len(dict_values) == len(data):
			records: List[Dict[str, Any]] = []
			for k, v in data.items():
				rec = dict(v)
				rec.setdefault("symbol", str(k))
				records.append(rec)
			return records

		# Single-record fallback.
		return [data]

	return []


def save_csv(rows: List[Dict[str, Any]]) -> None:
	import csv

	fieldnames = [
		"symbol",
		"name",
		"current_price",
		"previous_close",
		"price_change",
		"change_pct",
		"market_cap",
		"market_cap_billion",
		"currency",
		"exchange",
		"sector",
		"industry",
		"quote_type",
		"tradeable",
	]
	with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as fh:
		writer = csv.DictWriter(fh, fieldnames=fieldnames)
		writer.writeheader()
		writer.writerows(rows)


def save_detailed_csv(rows: List[Dict[str, Any]]) -> None:
	import csv

	fieldnames = [
		"symbol",
		"name",
		"status",
		"reason",
		"current_price",
		"previous_close",
		"price_change",
		"change_pct",
		"market_cap",
		"market_cap_billion",
		"currency",
		"exchange",
		"sector",
		"industry",
		"quote_type",
		"tradeable",
	]
	with OUTPUT_DETAILED_CSV.open("w", newline="", encoding="utf-8") as fh:
		writer = csv.DictWriter(fh, fieldnames=fieldnames)
		writer.writeheader()
		for row in rows:
			writer.writerow({k: row.get(k) for k in fieldnames})


def save_removed_csv(rows: List[Dict[str, Any]]) -> None:
	import csv

	fieldnames = [
		"symbol",
		"name",
		"status",
		"reason",
		"current_price",
		"previous_close",
		"price_change",
		"change_pct",
		"market_cap",
		"market_cap_billion",
		"currency",
		"exchange",
		"sector",
		"industry",
		"quote_type",
		"tradeable",
	]
	with OUTPUT_REMOVED_CSV.open("w", newline="", encoding="utf-8") as fh:
		writer = csv.DictWriter(fh, fieldnames=fieldnames)
		writer.writeheader()
		for row in rows:
			writer.writerow({k: row.get(k) for k in fieldnames})


def _fmt_num(value: Any, digits: int = 2) -> str:
	if isinstance(value, (int, float)):
		return f"{value:,.{digits}f}"
	return "N/A"


def _safe_filename(symbol: str) -> str:
	cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in symbol)
	return cleaned or "unknown_symbol"


def _history_stats_from_df(hist_df: Any) -> Dict[str, Any]:
	close_s = hist_df["Close"].dropna()
	if close_s.empty:
		return {
			"history_rows": 0,
			"start_date": None,
			"end_date": None,
			"latest_close": None,
			"min_close": None,
			"max_close": None,
			"avg_close": None,
			"median_close": None,
			"total_return_pct": None,
			"volatility_pct": None,
			"max_drawdown_pct": None,
		}

	returns = close_s.pct_change().dropna()
	volatility = float(returns.std() * (252.0 ** 0.5) * 100.0) if not returns.empty else None
	cummax = close_s.cummax()
	dd = ((close_s / cummax) - 1.0).min()

	start_close = float(close_s.iloc[0])
	end_close = float(close_s.iloc[-1])
	total_return_pct = ((end_close - start_close) / start_close * 100.0) if start_close else None

	date_col = "Date" if "Date" in hist_df.columns else hist_df.columns[0]
	start_date = str(hist_df[date_col].iloc[0])
	end_date = str(hist_df[date_col].iloc[-1])

	return {
		"history_rows": int(len(close_s)),
		"start_date": start_date,
		"end_date": end_date,
		"latest_close": end_close,
		"min_close": float(close_s.min()),
		"max_close": float(close_s.max()),
		"avg_close": float(close_s.mean()),
		"median_close": float(close_s.median()),
		"total_return_pct": float(total_return_pct) if total_return_pct is not None else None,
		"volatility_pct": volatility,
		"max_drawdown_pct": float(dd * 100.0) if dd is not None else None,
	}


def download_history_csvs(stock_rows: List[Dict[str, Any]], period: str = "5y", interval: str = "1d") -> Dict[str, Dict[str, Any]]:
	import pandas as pd
	import yfinance as yf

	HISTORY_DIR.mkdir(parents=True, exist_ok=True)
	print(f"[history] output folder: {HISTORY_DIR}")
	print(f"[history] requesting period={period}, interval={interval}")
	results: Dict[str, Dict[str, Any]] = {}

	for idx, row in enumerate(stock_rows, start=1):
		symbol = str(row.get("symbol") or "").strip().upper()
		if not symbol or symbol in results:
			continue

		result: Dict[str, Any] = {
			"downloaded": False,
			"csv_path": None,
			"error": None,
		}
		results[symbol] = result

		try:
			hist = yf.Ticker(symbol).history(period=period, interval=interval, auto_adjust=False)
			if hist is None or hist.empty:
				result["error"] = "no historical data returned"
				continue

			hist = hist.reset_index()
			if "Date" in hist.columns:
				hist["Date"] = pd.to_datetime(hist["Date"], errors="coerce").dt.tz_localize(None)

			csv_name = f"{_safe_filename(symbol)}.csv"
			csv_path = HISTORY_DIR / csv_name
			hist.to_csv(csv_path, index=False, encoding="utf-8")

			result.update(_history_stats_from_df(hist))
			result["downloaded"] = True
			result["csv_path"] = str(csv_path)
		except Exception as exc:
			result["error"] = str(exc)

		if idx % 25 == 0:
			done = sum(1 for r in results.values() if r.get("downloaded"))
			failed = len(results) - done
			print(f"[history] progress: {idx}/{len(stock_rows)} processed | downloaded={done} | failed={failed}")

	done = sum(1 for r in results.values() if r.get("downloaded"))
	failed = len(results) - done
	print(f"[history] completed: requested={len(results)} | downloaded={done} | failed={failed}")

	return results


def _build_text_summary(row: Dict[str, Any], history: Dict[str, Any]) -> str:
	parts = [
		f"{row.get('symbol')} is classified as {row.get('quote_type') or 'UNKNOWN'} on {row.get('exchange') or 'N/A'}.",
		f"Sector/Industry: {row.get('sector') or 'N/A'} / {row.get('industry') or 'N/A'}.",
		f"Latest snapshot price is {_fmt_num(row.get('current_price'), 4)} {row.get('currency') or ''} with day change {(_fmt_num(row.get('change_pct'), 2) + '%') if isinstance(row.get('change_pct'), (int, float)) else 'N/A'}.",
		f"Market cap is {_fmt_num(row.get('market_cap'), 0)} and tradeable flag is {row.get('tradeable')}.",
	]
	if history.get("downloaded"):
		parts.append(
			"Historical series spans "
			f"{history.get('start_date')} to {history.get('end_date')} ({history.get('history_rows')} sessions), "
			f"with total return {(_fmt_num(history.get('total_return_pct'), 2) + '%') if isinstance(history.get('total_return_pct'), (int, float)) else 'N/A'} "
			f"and max drawdown {(_fmt_num(history.get('max_drawdown_pct'), 2) + '%') if isinstance(history.get('max_drawdown_pct'), (int, float)) else 'N/A'}."
		)
	else:
		parts.append(f"Historical download was unavailable: {history.get('error') or 'unknown error'}.")
	return " ".join(parts)


def save_chapter_pdf(stock_rows: List[Dict[str, Any]], history_map: Dict[str, Dict[str, Any]]) -> None:
	import matplotlib.pyplot as plt
	import pandas as pd
	from matplotlib.backends.backend_pdf import PdfPages

	stock_rows = sorted(stock_rows, key=lambda r: (r.get("symbol") or "", r.get("name") or ""))

	with PdfPages(OUTPUT_CHAPTER_PDF) as pdf:
		fig = plt.figure(figsize=(11.69, 8.27), dpi=150)
		ax = fig.add_axes([0, 0, 1, 1])
		ax.axis("off")

		downloaded = sum(1 for s in stock_rows if history_map.get(str(s.get("symbol") or ""), {}).get("downloaded"))
		fig.text(0.05, 0.92, "Polish Stocks - Chapter Report", fontsize=24, fontweight="bold", color="#0f172a")
		fig.text(0.05, 0.87, "Detailed statistics and historical context per stock", fontsize=12, color="#334155")
		fig.text(0.05, 0.80, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", fontsize=10, color="#475569")
		fig.text(0.05, 0.76, f"Stocks covered: {len(stock_rows)}", fontsize=12)
		fig.text(0.05, 0.72, f"Historical CSVs downloaded: {downloaded}", fontsize=12)
		fig.text(0.05, 0.68, f"CSV folder: {HISTORY_DIR}", fontsize=10, color="#475569")

		pdf.savefig(fig, bbox_inches="tight")
		plt.close(fig)

		for idx, row in enumerate(stock_rows, start=1):
			symbol = str(row.get("symbol") or "").strip().upper()
			history = history_map.get(symbol, {"downloaded": False, "error": "no attempt"})

			fig = plt.figure(figsize=(11.69, 8.27), dpi=150)
			gs = fig.add_gridspec(2, 2, width_ratios=[1.05, 1.35], height_ratios=[1.0, 0.8])
			ax_text = fig.add_subplot(gs[:, 0])
			ax_price = fig.add_subplot(gs[0, 1])
			ax_vol = fig.add_subplot(gs[1, 1])

			ax_text.axis("off")
			ax_text.text(0.0, 0.98, f"Chapter {idx}: {symbol}", fontsize=15, fontweight="bold", color="#0b3d91", va="top")
			ax_text.text(0.0, 0.92, (row.get("name") or symbol), fontsize=11, color="#1e293b", va="top")

			text_lines = [
				f"Status: {row.get('status')} ({row.get('reason')})",
				f"Quote Type: {row.get('quote_type') or 'N/A'}",
				f"Exchange: {row.get('exchange') or 'N/A'}",
				f"Sector: {row.get('sector') or 'N/A'}",
				f"Industry: {row.get('industry') or 'N/A'}",
				f"Tradeable: {row.get('tradeable')}",
				f"Current Price: {_fmt_num(row.get('current_price'), 4)} {row.get('currency') or ''}",
				f"Previous Close: {_fmt_num(row.get('previous_close'), 4)}",
				f"Price Change: {_fmt_num(row.get('price_change'), 4)}",
				f"Change %: {_fmt_num(row.get('change_pct'), 2)}%" if isinstance(row.get("change_pct"), (int, float)) else "Change %: N/A",
				f"Market Cap: {_fmt_num(row.get('market_cap'), 0)}",
				f"Market Cap (B): {_fmt_num(row.get('market_cap_billion'), 2)}",
			]

			if history.get("downloaded"):
				text_lines.extend([
					"",
					"Historical statistics",
					f"Rows: {history.get('history_rows')}",
					f"Start: {history.get('start_date')}",
					f"End: {history.get('end_date')}",
					f"Latest Close: {_fmt_num(history.get('latest_close'), 4)}",
					f"Min/Max Close: {_fmt_num(history.get('min_close'), 4)} / {_fmt_num(history.get('max_close'), 4)}",
					f"Average/Median Close: {_fmt_num(history.get('avg_close'), 4)} / {_fmt_num(history.get('median_close'), 4)}",
					f"Total Return: {_fmt_num(history.get('total_return_pct'), 2)}%" if isinstance(history.get("total_return_pct"), (int, float)) else "Total Return: N/A",
					f"Annualized Volatility: {_fmt_num(history.get('volatility_pct'), 2)}%" if isinstance(history.get("volatility_pct"), (int, float)) else "Annualized Volatility: N/A",
					f"Max Drawdown: {_fmt_num(history.get('max_drawdown_pct'), 2)}%" if isinstance(history.get("max_drawdown_pct"), (int, float)) else "Max Drawdown: N/A",
					f"CSV Source: {history.get('csv_path')}",
				])
			else:
				text_lines.extend(["", f"Historical data unavailable: {history.get('error') or 'unknown error'}"])

			summary_text = _build_text_summary(row, history)
			wrapped_summary = "\n".join(textwrap.wrap(summary_text, width=62))
			text_lines.extend(["", "Executive summary", wrapped_summary])

			ax_text.text(0.0, 0.88, "\n".join(text_lines), fontsize=8.6, color="#0f172a", va="top")

			if history.get("downloaded") and history.get("csv_path"):
				try:
					df = pd.read_csv(history["csv_path"])
					if "Date" in df.columns:
						df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
						plot_df = df.dropna(subset=["Date", "Close"]).copy()
					else:
						plot_df = df

					if not plot_df.empty and "Close" in plot_df.columns:
						ax_price.plot(plot_df["Date"], plot_df["Close"], color="#1570ef", linewidth=1.6)
						ax_price.set_title("Close Price History", fontsize=10)
						ax_price.grid(alpha=0.25)
					else:
						ax_price.text(0.1, 0.5, "No close price data", fontsize=10)

					if not plot_df.empty and "Volume" in plot_df.columns:
						ax_vol.bar(plot_df["Date"], plot_df["Volume"], color="#12b76a", width=3)
						ax_vol.set_title("Volume", fontsize=10)
						ax_vol.grid(alpha=0.25)
					else:
						ax_vol.text(0.1, 0.5, "No volume data", fontsize=10)
				except Exception as exc:
					ax_price.text(0.05, 0.5, f"Chart generation failed: {exc}", fontsize=9)
					ax_vol.text(0.05, 0.5, "Volume chart unavailable", fontsize=9)
			else:
				ax_price.text(0.1, 0.5, "Historical data unavailable", fontsize=10)
				ax_vol.text(0.1, 0.5, "Historical data unavailable", fontsize=10)

			fig.tight_layout(rect=[0.02, 0.02, 0.98, 0.98])
			pdf.savefig(fig, bbox_inches="tight")
			plt.close(fig)


def save_pdf(cleaned_rows: List[Dict[str, Any]], removed_rows: List[Dict[str, Any]], total_records: int) -> None:
	import matplotlib.pyplot as plt
	from matplotlib.backends.backend_pdf import PdfPages

	cleaned_rows = sorted(cleaned_rows, key=lambda r: r.get("symbol") or "")
	removed_rows = sorted(removed_rows, key=lambda r: r.get("symbol") or "")

	with PdfPages(OUTPUT_PDF) as pdf:
		# Cover / summary page
		fig = plt.figure(figsize=(11.69, 8.27), dpi=150)
		ax = fig.add_axes([0, 0, 1, 1])
		ax.axis("off")

		fig.text(0.04, 0.94, "Poland YFinance Stock Summary", fontsize=20, fontweight="bold", color="#0b3d91")
		fig.text(0.04, 0.905, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", fontsize=10, color="#444")

		fig.text(0.04, 0.84, f"Total records: {total_records}", fontsize=12)
		fig.text(0.04, 0.80, f"Kept (clean): {len(cleaned_rows)}", fontsize=12, color="#1b7f3b")
		fig.text(0.04, 0.76, f"Removed: {len(removed_rows)}", fontsize=12, color="#b42318")

		reason_counts = Counter(r.get("reason", "unknown") for r in removed_rows)
		top_reasons = reason_counts.most_common(8)

		if top_reasons:
			ax_bar = fig.add_axes([0.38, 0.58, 0.58, 0.30])
			labels = [r[0] for r in top_reasons]
			values = [r[1] for r in top_reasons]
			ax_bar.barh(labels, values, color="#f04438")
			ax_bar.set_title("Top removal reasons", fontsize=12, pad=10)
			ax_bar.invert_yaxis()
			ax_bar.grid(axis="x", linestyle="--", alpha=0.3)

		if cleaned_rows:
			prices = [r["current_price"] for r in cleaned_rows if isinstance(r.get("current_price"), (int, float))]
			caps = [r["market_cap"] for r in cleaned_rows if isinstance(r.get("market_cap"), (int, float))]
			changes = [r["change_pct"] for r in cleaned_rows if isinstance(r.get("change_pct"), (int, float))]
			best = max(cleaned_rows, key=lambda r: r.get("current_price", -1))

			fig.text(0.04, 0.69, "Management KPIs", fontsize=12, fontweight="bold")
			fig.text(0.04, 0.655, f"Top price: {best.get('symbol')} ({_fmt_num(best.get('current_price'), 4)} {best.get('currency') or ''})", fontsize=10)
			if prices:
				fig.text(0.04, 0.625, f"Average price: {_fmt_num(mean(prices), 4)}", fontsize=10)
				fig.text(0.04, 0.595, f"Median price: {_fmt_num(median(prices), 4)}", fontsize=10)
			if caps:
				fig.text(0.04, 0.565, f"Total market cap: {_fmt_num(sum(caps), 0)}", fontsize=10)
			if changes:
				fig.text(0.04, 0.535, f"Average change %: {_fmt_num(mean(changes), 2)}%", fontsize=10)

			sector_counts = Counter((r.get("sector") or "Unknown") for r in cleaned_rows)
			top_sectors = sector_counts.most_common(8)
			if top_sectors:
				ax_sector = fig.add_axes([0.38, 0.14, 0.58, 0.34])
				s_labels = [s for s, _ in top_sectors]
				s_values = [v for _, v in top_sectors]
				ax_sector.barh(s_labels, s_values, color="#1570ef")
				ax_sector.set_title("Top sectors by stock count", fontsize=12, pad=10)
				ax_sector.invert_yaxis()
				ax_sector.grid(axis="x", linestyle="--", alpha=0.3)
		else:
			fig.text(0.04, 0.67, "No valid stock records after filtering.", fontsize=11, color="#b42318")

		pdf.savefig(fig, bbox_inches="tight")
		plt.close(fig)

		# Top movers page
		if cleaned_rows:
			fig, ax = plt.subplots(figsize=(11.69, 8.27), dpi=150)
			ax.axis("off")
			fig.text(0.03, 0.95, "Top Movers (by % change)", fontsize=14, fontweight="bold", color="#0b3d91")

			movers = [r for r in cleaned_rows if isinstance(r.get("change_pct"), (int, float))]
			gainers = sorted(movers, key=lambda r: r["change_pct"], reverse=True)[:15]
			losers = sorted(movers, key=lambda r: r["change_pct"])[:15]

			headers = ["Type", "Symbol", "Name", "Change %", "Price", "Market Cap", "Sector"]
			rows: List[List[str]] = []
			for r in gainers:
				rows.append([
					"Gainer",
					r.get("symbol") or "",
					(r.get("name") or "")[:34],
					f"{r.get('change_pct', 0):+.2f}%",
					_fmt_num(r.get("current_price"), 4),
					_fmt_num(r.get("market_cap"), 0),
					(r.get("sector") or "")[:22],
				])
			for r in losers:
				rows.append([
					"Loser",
					r.get("symbol") or "",
					(r.get("name") or "")[:34],
					f"{r.get('change_pct', 0):+.2f}%",
					_fmt_num(r.get("current_price"), 4),
					_fmt_num(r.get("market_cap"), 0),
					(r.get("sector") or "")[:22],
				])

			table = ax.table(cellText=rows, colLabels=headers, loc="center", cellLoc="left", colLoc="left")
			table.auto_set_font_size(False)
			table.set_fontsize(8)
			table.scale(1, 1.2)
			for col_i in range(len(headers)):
				head_cell = table[(0, col_i)]
				head_cell.set_facecolor("#0b3d91")
				head_cell.get_text().set_color("white")
				head_cell.get_text().set_weight("bold")
			for row_i in range(1, len(rows) + 1):
				row_type = rows[row_i - 1][0]
				bg = "#ecfdf3" if row_type == "Gainer" else "#fef3f2"
				for col_i in range(len(headers)):
					table[(row_i, col_i)].set_facecolor(bg)
			pdf.savefig(fig, bbox_inches="tight")
			plt.close(fig)

		# Detailed pages for all included stocks
		rows_per_page = 28
		headers = ["Symbol", "Name", "Price", "Prev Close", "Change %", "Mkt Cap", "Sector", "Tradeable"]

		for page_start in range(0, len(cleaned_rows), rows_per_page):
			chunk = cleaned_rows[page_start: page_start + rows_per_page]
			fig, ax = plt.subplots(figsize=(11.69, 8.27), dpi=150)
			ax.axis("off")
			fig.text(0.03, 0.95, "Detailed Stock Statistics", fontsize=14, fontweight="bold", color="#0b3d91")
			fig.text(0.03, 0.92, f"Rows {page_start + 1}-{page_start + len(chunk)} of {len(cleaned_rows)}", fontsize=10, color="#555")

			table_rows: List[List[str]] = []
			for r in chunk:
				chg = r.get("change_pct")

				table_rows.append([
					r.get("symbol") or "",
					(r.get("name") or "")[:34],
					_fmt_num(r.get("current_price"), 4),
					_fmt_num(r.get("previous_close"), 4),
					(f"{chg:+.2f}%" if chg is not None else "N/A"),
					_fmt_num(r.get("market_cap"), 0),
					(r.get("sector") or "")[:20],
					str(r.get("tradeable")),
				])

			table = ax.table(
				cellText=table_rows,
				colLabels=headers,
				loc="center",
				cellLoc="left",
				colLoc="left",
			)
			table.auto_set_font_size(False)
			table.set_fontsize(8)
			table.scale(1, 1.35)

			for col_i in range(len(headers)):
				head_cell = table[(0, col_i)]
				head_cell.set_facecolor("#0b3d91")
				head_cell.get_text().set_color("white")
				head_cell.get_text().set_weight("bold")

			for row_i in range(1, len(table_rows) + 1):
				shade = "#f8fbff" if row_i % 2 == 0 else "#eef4ff"
				for col_i in range(len(headers)):
					table[(row_i, col_i)].set_facecolor(shade)

			pdf.savefig(fig, bbox_inches="tight")
			plt.close(fig)


def main() -> None:
	if not INPUT_JSON.exists():
		raise FileNotFoundError(f"Input file not found: {INPUT_JSON}")

	print("=" * 72)
	print("Poland stock pipeline started")
	print(f"Input JSON: {INPUT_JSON}")
	print("=" * 72)

	records = load_input()
	print(f"[load] raw records loaded: {len(records)}")

	evaluated = [evaluate_record(item) for item in records]
	evaluated.sort(key=lambda x: x.get("symbol") or "")

	stock_rows = [row for row in evaluated if row.get("symbol")]
	kept_rows = [row for row in stock_rows if row.get("status") == "kept"]
	removed_rows = [row for row in evaluated if row.get("status") == "removed" and row.get("symbol")]
	cleaned = [row["normalized"] for row in kept_rows if row["normalized"] is not None]

	print(f"[filter] rows with symbol: {len(stock_rows)}")
	print(f"[filter] kept rows: {len(kept_rows)}")
	print(f"[filter] removed rows: {len(removed_rows)}")
	if removed_rows:
		reason_counts = Counter(r.get("reason", "unknown") for r in removed_rows)
		print("[filter] top removal reasons:")
		for reason, count in reason_counts.most_common(8):
			print(f"  - {reason}: {count}")

	print("[history] starting per-stock historical downloads...")
	history_map = download_history_csvs(stock_rows, period="5y", interval="1d")

	history_downloaded = sum(1 for r in history_map.values() if r.get("downloaded"))
	history_failed = len(history_map) - history_downloaded
	print(f"[history] summary: downloaded={history_downloaded} | failed={history_failed}")

	print("[write] writing CSV outputs...")
	save_csv(cleaned)
	save_detailed_csv(stock_rows)
	save_removed_csv(removed_rows)
	print("[write] CSV outputs saved")

	print("[write] generating management PDF...")
	save_pdf(cleaned, removed_rows, len(records))
	print("[write] generating chapter PDF...")
	save_chapter_pdf(stock_rows, history_map)

	print("-" * 72)
	print(f"Loaded records: {len(records)}")
	print(f"Saved {len(cleaned)} cleaned rows to {OUTPUT_CSV}")
	print(f"Saved {len(stock_rows)} detailed stock rows to {OUTPUT_DETAILED_CSV}")
	print(f"Saved {len(removed_rows)} removed rows to {OUTPUT_REMOVED_CSV}")
	print(f"Saved historical per-stock CSVs under {HISTORY_DIR}")
	print(f"Saved PDF summary to {OUTPUT_PDF}")
	print(f"Saved chapter PDF to {OUTPUT_CHAPTER_PDF}")
	print("Pipeline completed successfully")
	print("=" * 72)


if __name__ == "__main__":
	main()
