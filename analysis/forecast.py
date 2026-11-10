"""analysis/forecast.py — Model Proyeksi & Probabilitas Arah Harga Esok Hari (Next-Day Forecast)

Menggunakan kombinasi metode kuantitatif & teknikal standar Wall Street:
1. Multi-Factor Directional Probability (% Naik vs % Turun vs % Sideways)
2. Tom DeMark Next-Day Range Projection
3. ATR Volatility Expansion Range
4. Floor Pivot Point (Level Make-or-Break Penentu Esok Pagi)
5. Skenario Taktis (Bullish vs Bearish) & Panduan Jam 09:00 WIB
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional

from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import EMAIndicator, MACD
from ta.volatility import AverageTrueRange


def calculate_next_day_forecast(df: pd.DataFrame) -> Dict:
    """
    Hitung proyeksi arah pergerakan harga untuk esok hari (T+1).
    Input: DataFrame OHLCV harian dengan minimal 30 baris.
    Output: Dict berisi probabilitas arah, rentang estimasi harga besok, level penentu, dan skenario taktis.
    """
    if df.empty or len(df) < 25:
        return {}

    df = df.copy()
    c = df["close"]
    h = df["high"]
    l = df["low"]
    o = df["open"]
    v = df["volume"]

    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else last
    prev2 = df.iloc[-3] if len(df) > 2 else prev

    curr_p = float(last["close"])
    open_p = float(last["open"])
    high_p = float(last["high"])
    low_p = float(last["low"])
    vol_p = float(last["volume"])

    # ─────────────────────────────────────────────────────────
    # 1. HITUNG INDIKATOR PENDUKUNG PROYEKSI
    # ─────────────────────────────────────────────────────────
    ema5_s = EMAIndicator(c, window=5).ema_indicator()
    ema13_s = EMAIndicator(c, window=13).ema_indicator()
    ema20_s = EMAIndicator(c, window=20).ema_indicator()
    ema5 = float(ema5_s.iloc[-1]) if not pd.isna(ema5_s.iloc[-1]) else curr_p
    ema13 = float(ema13_s.iloc[-1]) if not pd.isna(ema13_s.iloc[-1]) else curr_p
    ema20 = float(ema20_s.iloc[-1]) if not pd.isna(ema20_s.iloc[-1]) else curr_p

    atr_s = AverageTrueRange(h, l, c, window=14).average_true_range()
    atr = float(atr_s.iloc[-1]) if not pd.isna(atr_s.iloc[-1]) else max(high_p - low_p, curr_p * 0.02)

    stoch = StochasticOscillator(h, l, c, window=5, smooth_window=3)
    stoch_k = float(stoch.stoch().iloc[-1]) if not pd.isna(stoch.stoch().iloc[-1]) else 50.0
    stoch_d = float(stoch.stoch_signal().iloc[-1]) if not pd.isna(stoch.stoch_signal().iloc[-1]) else 50.0
    stoch_k_prev = float(stoch.stoch().iloc[-2]) if len(stoch.stoch()) > 1 and not pd.isna(stoch.stoch().iloc[-2]) else stoch_k

    rsi_s = RSIIndicator(c, window=14).rsi()
    rsi = float(rsi_s.iloc[-1]) if not pd.isna(rsi_s.iloc[-1]) else 50.0
    rsi_prev = float(rsi_s.iloc[-2]) if len(rsi_s) > 1 and not pd.isna(rsi_s.iloc[-2]) else rsi

    macd_obj = MACD(c, window_fast=12, window_slow=26, window_sign=9)
    macd_hist = float(macd_obj.macd_diff().iloc[-1]) if not pd.isna(macd_obj.macd_diff().iloc[-1]) else 0.0
    macd_hist_prev = float(macd_obj.macd_diff().iloc[-2]) if len(macd_obj.macd_diff()) > 1 and not pd.isna(macd_obj.macd_diff().iloc[-2]) else macd_hist

    vol_ma20 = float(v.tail(20).mean()) if len(v) >= 20 else vol_p
    vol_ratio = vol_p / max(vol_ma20, 1.0)

    # ─────────────────────────────────────────────────────────
    # 2. MODEL PROBABILITAS ARAH BESOK (MULTI-FACTOR SCORING)
    # ─────────────────────────────────────────────────────────
    # Base netral 50:50
    score = 50.0
    reasons_bullish = []
    reasons_bearish = []

    # Faktor A: Posisi harga penutupan di dalam rentang harian (Closing Strength)
    # Jika tutup di 80%+ rentang hari ini = pembeli sangat dominan menjelang closing.
    day_range = max(high_p - low_p, 0.001)
    pos_in_range = (curr_p - low_p) / day_range
    if pos_in_range >= 0.70:
        score += 14.0
        reasons_bullish.append(f"Penutupan kuat di area atas rentang harian ({pos_in_range*100:.0f}% dari Low-High)")
    elif pos_in_range <= 0.30:
        score -= 14.0
        reasons_bearish.append(f"Penutupan lemah di area bawah rentang harian ({pos_in_range*100:.0f}% dari Low-High)")

    # Faktor B: Body Candle Hari Ini (Bullish vs Bearish candle)
    body_pct = (curr_p - open_p) / max(open_p, 1.0) * 100
    if body_pct >= 1.5:
        score += 8.0
        reasons_bullish.append(f"Candle harian hijau solid (+{body_pct:.1f}%)")
    elif body_pct <= -1.5:
        score -= 8.0
        reasons_bearish.append(f"Candle harian merah solid ({body_pct:.1f}%)")

    # Faktor C: Posisi vs EMA 5 dan EMA 20
    if curr_p > ema5 and ema5 > ema20:
        score += 10.0
        reasons_bullish.append(f"Harga berada di atas EMA5 (Rp {ema5:,.0f}) & EMA20 (Rp {ema20:,.0f})")
    elif curr_p < ema5 and ema5 < ema20:
        score -= 10.0
        reasons_bearish.append(f"Harga tertahan di bawah EMA5 (Rp {ema5:,.0f}) & EMA20 (Rp {ema20:,.0f})")
    elif curr_p > ema5:
        score += 4.0
    else:
        score -= 4.0

    # Faktor D: Fast Stochastic Slope & Cross
    if stoch_k > stoch_d and stoch_k > stoch_k_prev:
        score += 8.0
        reasons_bullish.append("Stochastic mengarah naik (momentum pembeli bertambah)")
    elif stoch_k < stoch_d and stoch_k < stoch_k_prev:
        score -= 8.0
        reasons_bearish.append("Stochastic mengarah turun (momentum penjual bertambah)")

    # Faktor E: MACD Histogram Delta
    if macd_hist > macd_hist_prev:
        score += 6.0
        reasons_bullish.append("Histogram MACD menguat ke atas")
    elif macd_hist < macd_hist_prev:
        score -= 6.0
        reasons_bearish.append("Histogram MACD melemah ke bawah")

    # Faktor F: Konfirmasi Volume
    if vol_ratio >= 1.5:
        if curr_p >= open_p:
            score += 6.0
            reasons_bullish.append(f"Volume akumulasi tebal ({vol_ratio:.1f}x rata-rata)")
        else:
            score -= 6.0
            reasons_bearish.append(f"Volume distribusi / tekanan jual tebal ({vol_ratio:.1f}x rata-rata)")

    # Batasi probabilitas antara 10% s/d 90% (tidak pernah ada kepastian mutlak di pasar)
    prob_up = max(10, min(90, int(round(score))))
    prob_down = 100 - prob_up

    if prob_up >= 60:
        bias_label = "CENDERUNG NAIK (BULLISH)"
        bias_color = "#00C853"
        bias_emoji = "📈"
        confidence = "Tinggi" if prob_up >= 70 else "Moderat"
    elif prob_up <= 40:
        bias_label = "CENDERUNG TURUN (BEARISH)"
        bias_color = "#D50000"
        bias_emoji = "📉"
        confidence = "Tinggi" if prob_down >= 70 else "Moderat"
    else:
        bias_label = "KONSOLIDASI / SIDEWAYS (WAIT & SEE)"
        bias_color = "#FFD740"
        bias_emoji = "⚖️"
        confidence = "Netral"

    # ─────────────────────────────────────────────────────────
    # 3. PROYEKSI RENTANG HARGA BESOK (TOM DEMARK & ATR)
    # ─────────────────────────────────────────────────────────
    # Rumus DeMark Projection T+1:
    if curr_p < open_p:
        x = high_p + (2 * low_p) + curr_p
    elif curr_p > open_p:
        x = (2 * high_p) + low_p + curr_p
    else:
        x = high_p + low_p + (2 * curr_p)

    demark_high = max(curr_p, round((x / 2.0) - low_p, 0))
    demark_low = min(curr_p, max(1.0, round((x / 2.0) - high_p, 0)))

    # Rentang Volatilitas ATR (0.8x ATR dari harga penutupan)
    atr_buffer = round(atr * 0.8, 0)
    expected_high = round(curr_p + atr_buffer, 0)
    expected_low = max(1.0, round(curr_p - atr_buffer, 0))

    # Gabungkan konsensus rentang harga esok hari
    proj_max = round(max(demark_high, expected_high), 0)
    proj_min = round(min(demark_low, expected_low), 0)
    upside_pct = round((proj_max - curr_p) / curr_p * 100, 1) if curr_p else 0
    downside_pct = round((curr_p - proj_min) / curr_p * 100, 1) if curr_p else 0

    # ─────────────────────────────────────────────────────────
    # 4. PIVOT POINT (LEVEL MAKE-OR-BREAK PENENTU BESOK PAGI)
    # ─────────────────────────────────────────────────────────
    pivot = round((high_p + low_p + curr_p) / 3.0, 0)
    r1 = round((2 * pivot) - low_p, 0)
    r2 = round(pivot + (high_p - low_p), 0)
    s1 = round((2 * pivot) - high_p, 0)
    s2 = round(pivot - (high_p - low_p), 0)

    # ─────────────────────────────────────────────────────────
    # 5. DUA SKENARIO TAKTIS (BULLISH VS BEARISH)
    # ─────────────────────────────────────────────────────────
    scenario_bullish = {
        "title": "🟢 Skenario Bullish (Jika Pasar Positif)",
        "trigger": f"Harga pembukaan / awal sesi bertahan di atas Pivot Rp {pivot:,.0f}",
        "target_1": f"Rp {r1:,.0f} (+{round((r1-curr_p)/curr_p*100, 1)}%)",
        "target_2": f"Rp {r2:,.0f} (+{round((r2-curr_p)/curr_p*100, 1)}%)",
        "action": f"Boleh follow buy / scalping buy jika pembukaan di atas Rp {pivot:,.0f} disertai antrean bid tebal. Pasang target profit di Rp {r1:,.0f} s/d Rp {r2:,.0f}.",
    }

    scenario_bearish = {
        "title": "🔴 Skenario Bearish (Jika Tekanan Jual Berlanjut)",
        "trigger": f"Harga pembukaan / awal sesi gagal menembus atau jebol di bawah Pivot Rp {pivot:,.0f}",
        "support_1": f"Rp {s1:,.0f} (-{round((curr_p-s1)/curr_p*100, 1)}%)",
        "support_2": f"Rp {s2:,.0f} (-{round((curr_p-s2)/curr_p*100, 1)}%)",
        "action": f"Waspada penurunan lanjutan! Jika harga jebol di bawah Rp {pivot:,.0f}, hindari beli. Yang sudah punya barang, pasang stop loss/exit di bawah Rp {s1:,.0f}.",
    }

    # ─────────────────────────────────────────────────────────
    # 6. REKOMENDASI PRE-OPENING & JAM 09:00 WIB BESOK
    # ─────────────────────────────────────────────────────────
    if prob_up >= 60:
        action_plan_tomorrow = (
            f"Bias besok pagi adalah BULLISH ({prob_up}%). "
            f"Perhatikan sesi Pre-Opening (08:45-09:00 WIB): Jika dibuka gap-up atau bertahan di atas Rp {pivot:,.0f}, "
            f"peluang kenaikan menuju Rp {r1:,.0f} terbuka lebar. Area aman akumulasi di rentang Rp {pivot:,.0f} - Rp {curr_p:,.0f}."
        )
    elif prob_up <= 40:
        action_plan_tomorrow = (
            f"Bias besok pagi adalah BEARISH / TEKANAN JUAL ({prob_down}%). "
            f"JANGAN BURU-BURU HAKA di jam 09:00 WIB. Pantau apakah ada bantalan di area Support Rp {s1:,.0f} s/d Rp {proj_min:,.0f}. "
            f"Jika kamu masih memegang saham ini dan harga gagal naik di atas Rp {pivot:,.0f}, siapkan exit."
        )
    else:
        action_plan_tomorrow = (
            f"Bias besok pagi adalah KONSOLIDASI / WAIT & SEE (50:50). "
            f"Biarkan pasar mencari arah di 15 menit pertama (09:00 - 09:15 WIB). "
            f"Jadikan level Pivot Rp {pivot:,.0f} sebagai kompas: Hanya beli jika harga kuat di atas Rp {pivot:,.0f} dengan volume tebal."
        )

    return {
        "current_price": curr_p,
        "prob_up": prob_up,
        "prob_down": prob_down,
        "bias_label": bias_label,
        "bias_color": bias_color,
        "bias_emoji": bias_emoji,
        "confidence": confidence,
        "reasons_bullish": reasons_bullish,
        "reasons_bearish": reasons_bearish,
        "demark_high": demark_high,
        "demark_low": demark_low,
        "expected_high": expected_high,
        "expected_low": expected_low,
        "proj_max": proj_max,
        "proj_min": proj_min,
        "upside_pct": upside_pct,
        "downside_pct": downside_pct,
        "pivot": pivot,
        "r1": r1,
        "r2": r2,
        "s1": s1,
        "s2": s2,
        "scenario_bullish": scenario_bullish,
        "scenario_bearish": scenario_bearish,
        "action_plan_tomorrow": action_plan_tomorrow,
        "atr": round(atr, 1),
    }


def get_watchlist_forecast_radar(watchlist: list) -> list:
    """
    Screening seluruh saham di watchlist untuk menghasilkan Leaderboard Radar Esok Hari.
    Return list of dict terurut dari probabilitas naik tertinggi ke terendah.
    """
    from data.fetcher import get_price_df_from_db
    from analysis.scalping import generate_scalping_signals
    from analysis.technical import get_smart_money_flow

    results = []
    for item in watchlist:
        ticker = item.get("ticker", "")
        name = item.get("name", "")
        sector = item.get("sector", "")
        if not ticker:
            continue

        df = get_price_df_from_db(ticker, limit=100)
        if df.empty or len(df) < 25:
            continue

        fc = calculate_next_day_forecast(df)
        if not fc:
            continue

        # Setup scalping jika ada
        sc = generate_scalping_signals(df)
        setups = sc.get("setups", [])
        setup_names = ", ".join([s["name"].split("(")[0].strip() for s in setups]) if setups else "Tidak ada"

        # Smart money flow (CMF & OBV)
        smf = get_smart_money_flow(df)

        curr = fc["current_price"]
        pivot = fc["pivot"]
        dist_pivot = round((curr - pivot) / max(pivot, 1) * 100, 1)

        results.append({
            "ticker": ticker,
            "name": name,
            "sector": sector,
            "price": curr,
            "prob_up": fc["prob_up"],
            "prob_down": fc["prob_down"],
            "bias_label": fc["bias_label"],
            "bias_color": fc["bias_color"],
            "bias_emoji": fc["bias_emoji"],
            "confidence": fc["confidence"],
            "pivot": pivot,
            "dist_pivot": dist_pivot,
            "proj_max": fc["proj_max"],
            "proj_min": fc["proj_min"],
            "upside_pct": fc["upside_pct"],
            "downside_pct": fc["downside_pct"],
            "scalp_signal": sc.get("signal", "—"),
            "scalp_setups": setup_names,
            "cmf_status": smf.get("cmf_status", "—"),
            "cmf_val": smf.get("cmf", 0),
            "cmf_color": smf.get("cmf_color", "#888"),
            "obv_trend": smf.get("obv_trend", "—"),
            "divergence": smf.get("divergence", "Tidak ada"),
            "action_plan_tomorrow": fc["action_plan_tomorrow"],
        })

    # Urutkan berdasarkan probabilitas naik tertinggi
    results.sort(key=lambda x: x["prob_up"], reverse=True)
    return results
