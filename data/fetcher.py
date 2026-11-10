"""data/fetcher.py — Ambil data harga dari Yahoo Finance dan simpan ke DB"""

import yfinance as yf
import pandas as pd
from datetime import datetime, date
from typing import List, Optional

from config import YF_SUFFIX, TZ
from database.models import (
    get_watchlist,
    upsert_price_history,
    upsert_fundamental,
    get_latest_price,
)


def _ticker_yf(ticker: str) -> str:
    """Convert IDX ticker ke format Yahoo Finance (e.g. BBCA -> BBCA.JK)."""
    t = ticker.upper().strip()
    if not t.endswith(YF_SUFFIX):
        t += YF_SUFFIX
    return t


def fetch_price_history(
    ticker: str,
    period: str = "1y",
    interval: str = "1d",
    save_to_db: bool = True,
) -> pd.DataFrame:
    """
    Download OHLCV data dari Yahoo Finance.
    Returns DataFrame dengan kolom: date, open, high, low, close, volume.
    """
    yf_ticker = _ticker_yf(ticker)
    try:
        df = yf.download(
            yf_ticker,
            period=period,
            interval=interval,
            progress=False,
            auto_adjust=True,
        )
        if df.empty:
            print(f"[Fetcher] No data for {yf_ticker}")
            return pd.DataFrame()

        # Flatten MultiIndex columns jika ada
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = df.reset_index()
        df.rename(columns={
            "Date": "date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }, inplace=True)

        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
        df = df[["date", "open", "high", "low", "close", "volume"]].copy()
        df = df.dropna(subset=["close"])

        if save_to_db:
            records = df.to_dict("records")
            upsert_price_history(ticker, records)
            print(f"[Fetcher] Saved {len(records)} rows for {ticker}")

        return df

    except Exception as e:
        print(f"[Fetcher] Error fetching {ticker}: {e}")
        return pd.DataFrame()


def fetch_realtime_price(ticker: str) -> Optional[float]:
    """Get harga terakhir (closing price hari ini atau hari sebelumnya)."""
    yf_ticker = _ticker_yf(ticker)
    try:
        info = yf.Ticker(yf_ticker).fast_info
        price = getattr(info, "last_price", None)
        if price is None:
            df = fetch_price_history(ticker, period="5d", save_to_db=False)
            if not df.empty:
                price = float(df.iloc[-1]["close"])
        return price
    except Exception as e:
        print(f"[Fetcher] Realtime price error for {ticker}: {e}")
        return None


def fetch_fundamental_yf(ticker: str) -> dict:
    """
    Ambil data fundamental dari Yahoo Finance.
    Sebagai fallback untuk data fundamental.
    """
    yf_ticker = _ticker_yf(ticker)
    try:
        info = yf.Ticker(yf_ticker).info
        data = {
            "pe_ratio":       info.get("trailingPE"),
            "pb_ratio":       info.get("priceToBook"),
            "der":            info.get("debtToEquity"),
            "roe":            info.get("returnOnEquity"),
            "eps":            info.get("trailingEps"),
            "revenue":        info.get("totalRevenue"),
            "net_profit":     info.get("netIncomeToCommon"),
            "market_cap":     info.get("marketCap"),
            "dividend_yield": info.get("dividendYield"),
        }
        # Convert None to null-safe values
        return {k: (round(v, 4) if isinstance(v, float) else v)
                for k, v in data.items()}
    except Exception as e:
        print(f"[Fetcher] Fundamental error for {ticker}: {e}")
        return {}


def update_all_watchlist(period: str = "1y"):
    """Update harga dan fundamental untuk semua saham di watchlist."""
    stocks = get_watchlist()
    if not stocks:
        print("[Fetcher] Watchlist kosong.")
        return

    print(f"[Fetcher] Updating {len(stocks)} stocks...")
    for stock in stocks:
        ticker = stock["ticker"]
        # Price history
        fetch_price_history(ticker, period=period, save_to_db=True)
        # Fundamental
        fund_data = fetch_fundamental_yf(ticker)
        if fund_data:
            upsert_fundamental(ticker, fund_data)

    print("[Fetcher] Update selesai.")


def get_price_df_from_db(ticker: str, limit: int = 365) -> pd.DataFrame:
    """Load price history dari DB ke DataFrame."""
    from database.models import get_price_history
    rows = get_price_history(ticker, limit=limit)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    return df
