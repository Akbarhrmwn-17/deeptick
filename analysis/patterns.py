"""analysis/patterns.py — Deteksi pola candlestick & level Support/Resistance otomatis (versi profesional)"""

import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional


# ─────────────────────────────────────────────────────────────
# CANDLESTICK PATTERN DETECTION
# ─────────────────────────────────────────────────────────────

def detect_patterns(df: pd.DataFrame) -> List[Dict]:
    """
    Deteksi pola candlestick signifikan dari DataFrame OHLCV.
    Pola yang didukung:
    - Bullish: Hammer, Bullish Engulfing, Morning Star, Dragonfly Doji, Piercing Line, Bullish Harami
    - Bearish: Shooting Star, Bearish Engulfing, Evening Star, Hanging Man, Dark Cloud Cover
    - Netral: Doji, Spinning Top
    Returns: List of dict {date, pattern, type (bullish/bearish/neutral), reliability}
    """
    if df.empty or len(df) < 5:
        return []

    df = df.copy().reset_index(drop=True)
    o = df["open"]
    h = df["high"]
    l = df["low"]
    c = df["close"]

    body     = c - o                            # Positif = bullish candle
    body_abs = body.abs()
    rng      = h - l                            # Total range
    safe_rng = rng.replace(0, 0.0001)
    body_pct = body_abs / safe_rng             # Rasio badan terhadap total range

    lower_wick = pd.Series([
        min(o.iloc[i], c.iloc[i]) - l.iloc[i] for i in range(len(df))
    ])
    upper_wick = pd.Series([
        h.iloc[i] - max(o.iloc[i], c.iloc[i]) for i in range(len(df))
    ])

    results = []

    def add(idx, pattern_name, ptype, reliability):
        if idx < len(df):
            results.append({
                "date":        df["date"].iloc[idx] if "date" in df.columns else str(idx),
                "pattern":     pattern_name,
                "type":        ptype,
                "reliability": reliability,   # "High" / "Medium" / "Low"
                "close":       float(c.iloc[idx]),
            })

    # ── Scan pola ────────────────────────────────────────────
    for i in range(2, len(df)):
        # ── Hammer (Bullish Reversal) ───────────────────────
        # Badan kecil di bagian atas, ekor bawah panjang (≥ 2x badan)
        is_hammer = (
            body_pct.iloc[i] < 0.35 and
            lower_wick.iloc[i] >= 2.0 * body_abs.iloc[i] and
            upper_wick.iloc[i] < body_abs.iloc[i] * 0.5 and
            lower_wick.iloc[i] > 0
        )
        # Perlu konteks downtrend sebelumnya
        prev_trend_down = c.iloc[i-2] > c.iloc[i-1] > c.iloc[i] * 0.99
        if is_hammer and prev_trend_down:
            add(i, "Hammer 🔨", "bullish", "High")

        # ── Shooting Star (Bearish Reversal) ──────────────
        # Badan kecil di bawah, ekor atas panjang
        is_shooting_star = (
            body_pct.iloc[i] < 0.35 and
            upper_wick.iloc[i] >= 2.0 * body_abs.iloc[i] and
            lower_wick.iloc[i] < body_abs.iloc[i] * 0.5 and
            upper_wick.iloc[i] > 0
        )
        prev_trend_up = c.iloc[i-2] < c.iloc[i-1] < c.iloc[i] * 1.01
        if is_shooting_star and prev_trend_up:
            add(i, "Shooting Star 💫", "bearish", "High")

        # ── Doji (Netral / Pembalikan Potensial) ──────────
        is_doji = body_pct.iloc[i] < 0.08
        if is_doji:
            # Dragonfly Doji (Bullish)
            if lower_wick.iloc[i] > 3 * upper_wick.iloc[i]:
                add(i, "Dragonfly Doji 🪁", "bullish", "Medium")
            # Gravestone Doji (Bearish)
            elif upper_wick.iloc[i] > 3 * lower_wick.iloc[i]:
                add(i, "Gravestone Doji 🪦", "bearish", "Medium")
            else:
                add(i, "Doji ✚", "neutral", "Low")

        # ── Bullish Engulfing ──────────────────────────────
        # Candle hari ini bullish besar menelan seluruh badan candle bearish kemarin
        if (
            body.iloc[i] > 0 and body.iloc[i-1] < 0 and
            o.iloc[i] < c.iloc[i-1] and c.iloc[i] > o.iloc[i-1] and
            body_abs.iloc[i] > body_abs.iloc[i-1] * 1.1
        ):
            add(i, "Bullish Engulfing 🟢📦", "bullish", "High")

        # ── Bearish Engulfing ──────────────────────────────
        if (
            body.iloc[i] < 0 and body.iloc[i-1] > 0 and
            o.iloc[i] > c.iloc[i-1] and c.iloc[i] < o.iloc[i-1] and
            body_abs.iloc[i] > body_abs.iloc[i-1] * 1.1
        ):
            add(i, "Bearish Engulfing 🔴📦", "bearish", "High")

        # ── Morning Star (3 candle bullish reversal) ──────
        if i >= 2:
            is_ms = (
                body.iloc[i-2] < 0 and                 # Candle besar merah
                body_abs.iloc[i-1] < body_abs.iloc[i-2] * 0.4 and  # Bintang (kecil)
                body.iloc[i] > 0 and                    # Candle besar hijau
                c.iloc[i] > (o.iloc[i-2] + c.iloc[i-2]) / 2  # Menutup lebih dari setengah candle pertama
            )
            if is_ms:
                add(i, "Morning Star ⭐", "bullish", "High")

        # ── Evening Star (3 candle bearish reversal) ──────
        if i >= 2:
            is_es = (
                body.iloc[i-2] > 0 and
                body_abs.iloc[i-1] < body_abs.iloc[i-2] * 0.4 and
                body.iloc[i] < 0 and
                c.iloc[i] < (o.iloc[i-2] + c.iloc[i-2]) / 2
            )
            if is_es:
                add(i, "Evening Star 🌟", "bearish", "High")

        # ── Bullish Harami ─────────────────────────────────
        if (
            body.iloc[i-1] < 0 and body.iloc[i] > 0 and
            body_abs.iloc[i] < body_abs.iloc[i-1] * 0.6 and
            o.iloc[i] > c.iloc[i-1] and c.iloc[i] < o.iloc[i-1]
        ):
            add(i, "Bullish Harami 🤰", "bullish", "Medium")

        # ── Bearish Harami ─────────────────────────────────
        if (
            body.iloc[i-1] > 0 and body.iloc[i] < 0 and
            body_abs.iloc[i] < body_abs.iloc[i-1] * 0.6 and
            o.iloc[i] < c.iloc[i-1] and c.iloc[i] > o.iloc[i-1]
        ):
            add(i, "Bearish Harami 🤰", "bearish", "Medium")

    # Urutkan dari yang terbaru, ambil 10 pola terakhir yang bermakna
    results.sort(key=lambda x: str(x["date"]), reverse=True)
    return results[:15]


# ─────────────────────────────────────────────────────────────
# SUPPORT & RESISTANCE LEVELS
# ─────────────────────────────────────────────────────────────

def find_support_resistance(df: pd.DataFrame, lookback: int = 20, n_levels: int = 5) -> Dict:
    """
    Hitung level Support dan Resistance otomatis menggunakan metode:
    1. Pivot Point Klasik (dari High, Low, Close hari terakhir)
    2. Swing High & Swing Low (puncak/lembah lokal dalam window lookback)
    """
    if df.empty or len(df) < lookback + 5:
        return {}

    c = df["close"]
    h = df["high"]
    l = df["low"]
    current = float(c.iloc[-1])

    # ── 1. Pivot Point Klasik (Daily) ─────────────────────
    last_h = float(h.iloc[-2])
    last_l = float(l.iloc[-2])
    last_c = float(c.iloc[-2])

    pivot = (last_h + last_l + last_c) / 3
    r1 = 2 * pivot - last_l
    r2 = pivot + (last_h - last_l)
    r3 = last_h + 2 * (pivot - last_l)
    s1 = 2 * pivot - last_h
    s2 = pivot - (last_h - last_l)
    s3 = last_l - 2 * (last_h - pivot)

    # ── 2. Swing High & Swing Low dari data historis ──────
    swing_highs = []
    swing_lows  = []
    win = 5  # Window untuk swing local

    for i in range(win, len(df) - win):
        if all(h.iloc[i] >= h.iloc[j] for j in range(i-win, i+win+1) if j != i):
            swing_highs.append(float(h.iloc[i]))
        if all(l.iloc[i] <= l.iloc[j] for j in range(i-win, i+win+1) if j != i):
            swing_lows.append(float(l.iloc[i]))

    # Cluster level yang berdekatan (dalam 1% dari satu sama lain)
    def cluster(levels: list, threshold_pct: float = 0.015) -> list:
        if not levels:
            return []
        sorted_lvl = sorted(set(levels))
        clusters = [[sorted_lvl[0]]]
        for lvl in sorted_lvl[1:]:
            if abs(lvl - clusters[-1][-1]) / max(clusters[-1][-1], 0.001) < threshold_pct:
                clusters[-1].append(lvl)
            else:
                clusters.append([lvl])
        return [round(sum(c)/len(c), 0) for c in clusters]

    key_resistances = sorted([l for l in cluster(swing_highs) if l > current], reverse=False)[:n_levels]
    key_supports    = sorted([l for l in cluster(swing_lows)  if l < current], reverse=True)[:n_levels]

    nearest_resistance = key_resistances[0] if key_resistances else r1
    nearest_support    = key_supports[0]    if key_supports    else s1
    upside_pct   = ((nearest_resistance - current) / current * 100) if current > 0 else 0
    downside_pct = ((current - nearest_support)    / current * 100) if current > 0 else 0

    return {
        "current":              current,
        "pivot":                round(pivot, 0),
        "r1": round(r1, 0), "r2": round(r2, 0), "r3": round(r3, 0),
        "s1": round(s1, 0), "s2": round(s2, 0), "s3": round(s3, 0),
        "swing_resistances":    key_resistances,
        "swing_supports":       key_supports,
        "nearest_resistance":   nearest_resistance,
        "nearest_support":      nearest_support,
        "upside_to_resistance": round(upside_pct, 1),
        "downside_to_support":  round(downside_pct, 1),
    }


# ─────────────────────────────────────────────────────────────
# STOCHASTIC RSI
# ─────────────────────────────────────────────────────────────

def get_stochrsi_signal(df: pd.DataFrame) -> Dict:
    """
    Hitung Stochastic RSI (StochRSI-K & StochRSI-D) dan hasilkan sinyal.
    StochRSI lebih sensitif dari RSI biasa — cocok untuk timing entry yang lebih akurat.
    """
    try:
        from ta.momentum import StochRSIIndicator
        indicator = StochRSIIndicator(df["close"], window=14, smooth1=3, smooth2=3)
        k = indicator.stochrsi_k()
        d = indicator.stochrsi_d()
        k_last = float(k.iloc[-1]) if not pd.isna(k.iloc[-1]) else None
        d_last = float(d.iloc[-1]) if not pd.isna(d.iloc[-1]) else None

        if k_last is None or d_last is None:
            return {"signal": "UNKNOWN", "detail": "Data tidak cukup", "k": None, "d": None}

        k_pct = round(k_last * 100, 1)
        d_pct = round(d_last * 100, 1)

        # Sinyal crossover: K memotong ke atas D di area oversold = BUY
        k_prev = float(k.iloc[-2]) if len(k) > 1 and not pd.isna(k.iloc[-2]) else k_last
        d_prev = float(d.iloc[-2]) if len(d) > 1 and not pd.isna(d.iloc[-2]) else d_last
        golden_cross = k_prev < d_prev and k_last > d_last
        death_cross  = k_prev > d_prev and k_last < d_last

        if k_pct < 20 and d_pct < 20 and golden_cross:
            signal = "BUY"
            detail = f"StochRSI Golden Cross di zona Oversold (K={k_pct}%, D={d_pct}%) — Sinyal masuk terkuat!"
        elif k_pct < 20 and d_pct < 20:
            signal = "BUY"
            detail = f"StochRSI Oversold zona rendah (K={k_pct}%, D={d_pct}%) — Area akumulasi"
        elif k_pct > 80 and d_pct > 80 and death_cross:
            signal = "SELL"
            detail = f"StochRSI Death Cross di zona Overbought (K={k_pct}%, D={d_pct}%) — Sinyal keluar kuat!"
        elif k_pct > 80 and d_pct > 80:
            signal = "SELL"
            detail = f"StochRSI Overbought (K={k_pct}%, D={d_pct}%) — Rawan profit taking"
        elif golden_cross:
            signal = "BUY"
            detail = f"StochRSI K memotong ke atas D (K={k_pct}%, D={d_pct}%) — Momentum membaik"
        elif death_cross:
            signal = "SELL"
            detail = f"StochRSI K memotong ke bawah D (K={k_pct}%, D={d_pct}%) — Momentum melemah"
        else:
            signal = "HOLD"
            detail = f"StochRSI Netral (K={k_pct}%, D={d_pct}%)"

        return {"signal": signal, "detail": detail, "k": k_pct, "d": d_pct}
    except Exception as e:
        return {"signal": "UNKNOWN", "detail": f"Error: {e}", "k": None, "d": None}
