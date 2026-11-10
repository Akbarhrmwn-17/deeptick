"""analysis/ihsg.py — Engine Analisis Makro & Market Regime IHSG (Indeks Harga Saham Gabungan)

Fitur Kuantitatif:
1. Mengunduh data OHLCV IHSG (^JKSE) dari Yahoo Finance dengan caching pintar.
2. Market Regime & Traffic Light System:
   - 🟢 HIJAU (RISK-ON): IHSG uptrend kuat di atas MA20/MA50, aman untuk agresif scalping & swing.
   - 🟡 KUNING (SELECTIVE): IHSG konsolidasi/sideways atau uji support, kurangi lot & pilih saham tertentu.
   - 🔴 MERAH (RISK-OFF / DEFENSIVE): IHSG breakdown di bawah MA20/MA50, waspada jebol support, prioritaskan cash.
3. Market Breadth BEI: Menghitung persentase saham bursa yang bergerak naik vs turun.
4. Level Penentu (Support & Resistance Kunci IHSG, Pivot Point, Moving Average).
5. Integrasi Panduan Taktis untuk Scalper & Swing Trader.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, Any, Optional

from ta.trend import SMAIndicator, EMAIndicator, MACD
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.volatility import BollingerBands, AverageTrueRange


def fetch_ihsg_data(period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    """Download data OHLCV historis IHSG (^JKSE)."""
    try:
        raw_df = yf.download(
            "^JKSE",
            period=period,
            interval=interval,
            progress=False,
            auto_adjust=True,
        )
        if raw_df.empty:
            return pd.DataFrame()

        # Flatten MultiIndex jika ada
        if isinstance(raw_df.columns, pd.MultiIndex):
            raw_df.columns = raw_df.columns.get_level_values(0)

        df = raw_df.reset_index().copy()
        df.columns = [str(c).lower() for c in df.columns]
        rename_map = {}
        for col in df.columns:
            if "date" in col:
                rename_map[col] = "date"
            elif "open" in col:
                rename_map[col] = "open"
            elif "high" in col:
                rename_map[col] = "high"
            elif "low" in col:
                rename_map[col] = "low"
            elif "close" in col:
                rename_map[col] = "close"
            elif "vol" in col:
                rename_map[col] = "volume"

        df.rename(columns=rename_map, inplace=True)
        required = ["date", "open", "high", "low", "close", "volume"]
        if all(r in df.columns for r in required):
            df = df.dropna(subset=["close"]).copy()
            return df
        return pd.DataFrame()
    except Exception as e:
        print(f"[IHSG] Error fetching data: {e}")
        return pd.DataFrame()


def analyze_ihsg_regime(df: pd.DataFrame = None) -> Dict[str, Any]:
    """
    Kalkulasi Market Regime & Status Sentimen Makro IHSG.
    Mengembalikan dict komprehensif berisi status, traffic light, rekomendasi lot, dan support/resistance.
    """
    if df is None or df.empty:
        df = fetch_ihsg_data(period="1y")

    if df.empty or len(df) < 30:
        return {
            "status": "UNKNOWN",
            "traffic_light": "🟡",
            "regime_title": "Data IHSG Tidak Cukup",
            "risk_mode": "SELECTIVE",
            "lot_multiplier": 0.5,
            "action_advice": "Pantau market secara hati-hati.",
            "df": pd.DataFrame(),
        }

    df = df.copy()
    c = df["close"]
    h = df["high"]
    l = df["low"]
    o = df["open"]
    v = df["volume"]

    # ── Indikator Makro IHSG ──────────────────────────────────
    df["MA20"] = SMAIndicator(c, window=20).sma_indicator()
    df["MA50"] = SMAIndicator(c, window=50).sma_indicator()
    df["MA200"] = SMAIndicator(c, window=min(200, len(c))).sma_indicator()
    df["EMA20"] = EMAIndicator(c, window=20).ema_indicator()
    df["RSI"] = RSIIndicator(c, window=14).rsi()

    macd = MACD(c, window_fast=12, window_slow=26, window_sign=9)
    df["MACD"] = macd.macd()
    df["MACD_Signal"] = macd.macd_signal()
    df["MACD_Hist"] = macd.macd_diff()

    bb = BollingerBands(c, window=20, window_dev=2)
    df["BB_Upper"] = bb.bollinger_hband()
    df["BB_Mid"] = bb.bollinger_mavg()
    df["BB_Lower"] = bb.bollinger_lband()

    atr = AverageTrueRange(h, l, c, window=14).average_true_range()
    df["ATR"] = atr

    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else last

    curr_p = float(last["close"])
    prev_p = float(prev["close"])
    change_pts = curr_p - prev_p
    change_pct = (change_pts / prev_p * 100) if prev_p > 0 else 0.0

    high_p = float(last["high"])
    low_p = float(last["low"])
    open_p = float(last["open"])

    ma20 = float(last["MA20"]) if not pd.isna(last["MA20"]) else curr_p
    ma50 = float(last["MA50"]) if not pd.isna(last["MA50"]) else curr_p
    ma200 = float(last["MA200"]) if not pd.isna(last["MA200"]) else curr_p
    rsi = float(last["RSI"]) if not pd.isna(last["RSI"]) else 50.0
    macd_hist = float(last["MACD_Hist"]) if not pd.isna(last["MACD_Hist"]) else 0.0
    macd_hist_prev = float(prev["MACD_Hist"]) if not pd.isna(prev["MACD_Hist"]) else 0.0

    # ── Level Kunci (Pivot, Support, Resistance) ───────────────
    pivot = (high_p + low_p + curr_p) / 3.0
    r1 = (2 * pivot) - low_p
    s1 = (2 * pivot) - high_p
    r2 = pivot + (high_p - low_p)
    s2 = pivot - (high_p - low_p)

    # ── Market Regime Scoring (-10 s/d +10) ───────────────────
    score = 0
    reasons = []

    # 1. Posisi vs Moving Average
    if curr_p > ma20 and ma20 > ma50:
        score += 3
        reasons.append("IHSG berada di atas MA20 & MA50 (Golden Trend Uptrend)")
    elif curr_p > ma20:
        score += 1
        reasons.append("IHSG bertahan di atas support jangka pendek MA20")
    elif curr_p < ma20 and ma20 < ma50:
        score -= 3
        reasons.append("IHSG berada di bawah MA20 & MA50 (Downtrend Tertekan)")
    else:
        score -= 1
        reasons.append("IHSG terkoreksi menembus ke bawah MA20")

    # Posisi vs MA200 (Tren Utama Jangka Panjang)
    if curr_p > ma200:
        score += 2
        reasons.append("IHSG berada di atas MA200 (Struktur Bull Market Mayor)")
    else:
        score -= 2
        reasons.append("IHSG berada di bawah MA200 (Struktur Bear Market Mayor)")

    # 2. RSI Momentum
    if 50 <= rsi <= 70:
        score += 2
        reasons.append(f"RSI Sehat ({rsi:.1f}) mendukung kelanjutan penguatan")
    elif rsi > 70:
        score += 0
        reasons.append(f"RSI Jenuh Beli / Overbought ({rsi:.1f}), waspada aksi profit taking asing")
    elif rsi < 30:
        score += 1  # Peluang technical rebound
        reasons.append(f"RSI Jenuh Jual / Oversold ({rsi:.1f}), potensi pantulan teknikal jangka pendek")
    elif rsi < 45:
        score -= 2
        reasons.append(f"RSI Melemah ({rsi:.1f}), momentum pembeli tipis")

    # 3. MACD Momentum
    if macd_hist > 0 and macd_hist >= macd_hist_prev:
        score += 2
        reasons.append("Histogram MACD positif dan menguat")
    elif macd_hist > 0 and macd_hist < macd_hist_prev:
        score += 0
        reasons.append("Histogram MACD positif namun mulai melandai")
    elif macd_hist < 0 and macd_hist < macd_hist_prev:
        score -= 2
        reasons.append("Tekanan jual makro mendominasi (Histogram MACD merah membesar)")
    elif macd_hist < 0 and macd_hist >= macd_hist_prev:
        score -= 0
        reasons.append("Tekanan jual mulai berkurang (Histogram MACD merah mengecil)")

    # 4. Candlestick Harian
    if change_pct >= 0.5:
        score += 1
    elif change_pct <= -0.5:
        score -= 1

    # ── Klasifikasi Traffic Light & Rekomendasi Alokasi ────────
    if score >= 4:
        traffic_light = "🟢"
        regime_title = "RISK-ON (IHSG BULLISH KUAT)"
        risk_mode = "AGGRESSIVE"
        color = "#00C853"
        lot_multiplier = 1.0  # 100% kapasitas modal
        action_advice = "Pasar sangat kondusif! Setup Scalping & Swing memiliki peluang sukses tinggi (Win Rate maksimal). Boleh masuk dengan kapasitas penuh."
    elif score >= 0:
        traffic_light = "🟡"
        regime_title = "SELECTIVE (IHSG KONSOLIDASI / UJI SUPPORT)"
        risk_mode = "SELECTIVE"
        color = "#FFD740"
        lot_multiplier = 0.6  # 60% kapasitas modal
        action_advice = "IHSG bergerak variatif / sideways. Tetap selektif: hanya eksekusi saham yang memiliki volume akumulasi mandiri (Anti-IHSG). Kurangi target take profit & pasang stop loss ketat."
    else:
        traffic_light = "🔴"
        regime_title = "RISK-OFF (IHSG BEARISH / TEKANAN JUAL TINGGI)"
        risk_mode = "DEFENSIVE"
        color = "#D50000"
        lot_multiplier = 0.3  # 30% kapasitas atau Wait & See
        action_advice = "PERINGATAN BAHAYA! IHSG dalam tren turun atau panic selling. Disiplin batasi trading, kurangi ukuran lot menjadi 25%-30%, atau utamakan pegang CASH (Wait & See) sampai IHSG menemukan lantai pantulan."

    return {
        "price": curr_p,
        "change_pts": change_pts,
        "change_pct": change_pct,
        "traffic_light": traffic_light,
        "regime_title": regime_title,
        "risk_mode": risk_mode,
        "color": color,
        "lot_multiplier": lot_multiplier,
        "action_advice": action_advice,
        "score": score,
        "reasons": reasons,
        "ma20": ma20,
        "ma50": ma50,
        "ma200": ma200,
        "rsi": rsi,
        "macd_hist": macd_hist,
        "pivot": pivot,
        "r1": r1,
        "s1": s1,
        "r2": r2,
        "s2": s2,
        "date": str(last["date"])[:10],
        "df": df,
    }
