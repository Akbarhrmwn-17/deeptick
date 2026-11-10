"""data/running_trade.py — Engine simulasi dan live feed Running Trade ala Stockbit"""

import yfinance as yf
import pandas as pd
from datetime import datetime
import random
import pytz
from typing import List, Dict

TZ_JKT = pytz.timezone("Asia/Jakarta")


def fetch_live_market_ticks(watchlist_tickers: List[str]) -> List[Dict]:
    """
    Mengambil data tick / transaksi terkini dari saham-saham di bursa.
    Menghasilkan data running trade dengan format persis seperti di Stockbit:
    Time, Code, Price, Change %, Action (Buy/Sell), Lot, Val (Value).
    """
    if not watchlist_tickers:
        watchlist_tickers = ["BBCA", "BBRI", "BMRI", "TLKM", "GOTO", "MEJA", "BTEK", "MIKA", "RANS", "TAYS"]

    results = []
    now = datetime.now(TZ_JKT)

    # Bersihkan ticker
    clean_tickers = [t.upper().replace(".JK", "").strip() for t in watchlist_tickers]
    yf_symbols = [f"{t}.JK" for t in clean_tickers]

    try:
        # Download data 1 hari dengan interval 1 menit
        df = yf.download(
            " ".join(yf_symbols),
            period="1d",
            interval="1m",
            progress=False,
            auto_adjust=False
        )

        if not df.empty:
            # Iterasi per ticker untuk membangun tick log
            for ticker in clean_tickers:
                sym = f"{ticker}.JK"
                try:
                    if ("Close", sym) in df.columns:
                        sub = df[[("Close", sym), ("Open", sym), ("High", sym), ("Low", sym), ("Volume", sym)]].dropna()
                        if not sub.empty:
                            last_few = sub.tail(5)
                            for dt, row in last_few.iterrows():
                                close_p = float(row[("Close", sym)])
                                open_p = float(row[("Open", sym)])
                                vol_shares = float(row[("Volume", sym)])
                                lot_val = max(1, int(vol_shares // 100))

                                chg = ((close_p - open_p) / open_p * 100) if open_p > 0 else 0.0
                                action = "Buy" if close_p >= open_p else "Sell"
                                trade_val = lot_val * 100 * close_p

                                if trade_val >= 1e9:
                                    val_str = f"{trade_val / 1e9:.1f}B"
                                elif trade_val >= 1e6:
                                    val_str = f"{trade_val / 1e6:.1f}M"
                                elif trade_val >= 1e3:
                                    val_str = f"{trade_val / 1e3:.1f}K"
                                else:
                                    val_str = f"{trade_val:,.0f}"

                                t_str = dt.astimezone(TZ_JKT).strftime("%H:%M:%S")

                                results.append({
                                    "time": t_str,
                                    "timestamp": dt,
                                    "code": ticker,
                                    "price": close_p,
                                    "change": round(chg, 2),
                                    "action": action,
                                    "lot": lot_val,
                                    "val": val_str,
                                    "val_num": trade_val,
                                    "market": "RG"
                                })
                except Exception:
                    continue
    except Exception as e:
        print(f"[Running Trade] download error: {e}")

    # Urutkan berdasarkan waktu transaksi terbaru
    results.sort(key=lambda x: x.get("timestamp", now), reverse=True)
    return results[:100]
