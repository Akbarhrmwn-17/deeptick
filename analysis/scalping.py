"""analysis/scalping.py — Engine Scalping Profesional untuk day trading IDX

Scalping = Teknik trading ultra-cepat yang memanfaatkan pergerakan harga
kecil dalam waktu singkat (menit - jam). Tujuan: akumulasi profit kecil
tapi konsisten, bukan menunggu trend besar.

Indikator yang digunakan (standar trader institusional):
- EMA(5/13/21): Triple EMA untuk deteksi trend cepat & area pullback
- RSI(5): RSI ultra-cepat untuk overbought/oversold intraday
- Stochastic(5,3,3): Fast oscillator untuk timing entry presisi
- Bollinger Band Squeeze: Deteksi momen explosive breakout
- Volume Spike Detection: Konfirmasi kekuatan gerakan harga
- ATR(5): Volatilitas ultra-cepat untuk risk management ketat
- ADX(14): Filter kekuatan tren (hindari scalp di pasar sideways lemah)
- Williams %R(14): Zona overbought/oversold alternatif
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional

from ta.momentum import (
    RSIIndicator, StochasticOscillator,
    StochRSIIndicator, WilliamsRIndicator,
)
from ta.trend import EMAIndicator, SMAIndicator, MACD, ADXIndicator
from ta.volatility import BollingerBands, AverageTrueRange


# ─────────────────────────────────────────────────────────────
# SCALPING INDICATOR ENGINE
# ─────────────────────────────────────────────────────────────

def compute_scalping_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Tambahkan semua indikator scalping ke DataFrame OHLCV harian."""
    if df.empty or len(df) < 25:
        return df

    df = df.copy()
    c, h, l, v = df["close"], df["high"], df["low"], df["volume"]

    # ── Triple EMA (Scalper Standard) ────────────────────
    df["EMA5"]  = EMAIndicator(c, window=5).ema_indicator()
    df["EMA13"] = EMAIndicator(c, window=13).ema_indicator()
    df["EMA21"] = EMAIndicator(c, window=21).ema_indicator()

    # ── RSI Ultra-Fast (5 periode) ────────────────────────
    df["RSI5"] = RSIIndicator(c, window=5).rsi()
    df["RSI14"] = RSIIndicator(c, window=14).rsi()

    # ── Stochastic Fast (5,3,3) ───────────────────────────
    stoch = StochasticOscillator(h, l, c, window=5, smooth_window=3)
    df["Stoch_K"] = stoch.stoch()
    df["Stoch_D"] = stoch.stoch_signal()

    # ── Williams %R ───────────────────────────────────────
    df["WilliamsR"] = WilliamsRIndicator(h, l, c, lbp=14).williams_r()

    # ── ADX (Trend Strength) ──────────────────────────────
    adx = ADXIndicator(h, l, c, window=14)
    df["ADX"]    = adx.adx()
    df["DI_Pos"] = adx.adx_pos()
    df["DI_Neg"] = adx.adx_neg()

    # ── MACD Fast (5,13,4) — Scalping MACD ────────────────
    macd_sc = MACD(c, window_fast=5, window_slow=13, window_sign=4)
    df["MACD_Scalp"]      = macd_sc.macd()
    df["MACD_Scalp_Sig"]  = macd_sc.macd_signal()
    df["MACD_Scalp_Hist"] = macd_sc.macd_diff()

    # ── Bollinger Bands + Squeeze Detection ───────────────
    bb = BollingerBands(c, window=20, window_dev=2)
    df["BB_Upper"] = bb.bollinger_hband()
    df["BB_Mid"]   = bb.bollinger_mavg()
    df["BB_Lower"] = bb.bollinger_lband()
    df["BB_Width"] = (df["BB_Upper"] - df["BB_Lower"]) / df["BB_Mid"].replace(0, 0.0001) * 100

    # Squeeze = BB Width di bawah rata-rata 20 hari (volatilitas menyempit)
    df["BB_Width_MA"] = SMAIndicator(df["BB_Width"], window=20).sma_indicator()
    df["Is_Squeeze"] = df["BB_Width"] < df["BB_Width_MA"]

    # ── ATR Fast (5 periode) ──────────────────────────────
    df["ATR5"] = AverageTrueRange(h, l, c, window=5).average_true_range()
    df["ATR14"] = AverageTrueRange(h, l, c, window=14).average_true_range()

    # ── Volume Analysis ───────────────────────────────────
    df["Vol_MA5"]  = SMAIndicator(v, window=5).sma_indicator()
    df["Vol_MA20"] = SMAIndicator(v, window=20).sma_indicator()
    df["Vol_Ratio"] = v / df["Vol_MA20"].replace(0, 1)
    df["Vol_Spike"] = df["Vol_Ratio"] >= 2.0

    return df


# ─────────────────────────────────────────────────────────────
# SCALPING SIGNAL GENERATION
# ─────────────────────────────────────────────────────────────

def generate_scalping_signals(df: pd.DataFrame) -> Dict:
    """
    Hasilkan analisis scalping komprehensif dari data harian.
    Return dict berisi sinyal, skor, setup yang terdeteksi, dan risk management.
    """
    if df.empty or len(df) < 25:
        return {}

    df = compute_scalping_indicators(df)
    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else last
    prev2 = df.iloc[-3] if len(df) > 2 else prev

    current_price = float(last["close"])
    ema5  = float(last["EMA5"])  if not pd.isna(last.get("EMA5"))  else None
    ema13 = float(last["EMA13"]) if not pd.isna(last.get("EMA13")) else None
    ema21 = float(last["EMA21"]) if not pd.isna(last.get("EMA21")) else None
    rsi5  = float(last["RSI5"])  if not pd.isna(last.get("RSI5"))  else None
    rsi14 = float(last["RSI14"]) if not pd.isna(last.get("RSI14")) else None
    stoch_k = float(last["Stoch_K"]) if not pd.isna(last.get("Stoch_K")) else None
    stoch_d = float(last["Stoch_D"]) if not pd.isna(last.get("Stoch_D")) else None
    stoch_k_prev = float(prev["Stoch_K"]) if not pd.isna(prev.get("Stoch_K")) else None
    stoch_d_prev = float(prev["Stoch_D"]) if not pd.isna(prev.get("Stoch_D")) else None
    williams_r = float(last["WilliamsR"]) if not pd.isna(last.get("WilliamsR")) else None
    adx = float(last["ADX"]) if not pd.isna(last.get("ADX")) else None
    di_pos = float(last["DI_Pos"]) if not pd.isna(last.get("DI_Pos")) else None
    di_neg = float(last["DI_Neg"]) if not pd.isna(last.get("DI_Neg")) else None
    macd_hist = float(last["MACD_Scalp_Hist"]) if not pd.isna(last.get("MACD_Scalp_Hist")) else None
    macd_hist_prev = float(prev["MACD_Scalp_Hist"]) if not pd.isna(prev.get("MACD_Scalp_Hist")) else None
    atr5 = float(last["ATR5"]) if not pd.isna(last.get("ATR5")) else None
    atr14 = float(last["ATR14"]) if not pd.isna(last.get("ATR14")) else None
    bb_width = float(last["BB_Width"]) if not pd.isna(last.get("BB_Width")) else None
    is_squeeze = bool(last.get("Is_Squeeze", False))
    vol_ratio = float(last["Vol_Ratio"]) if not pd.isna(last.get("Vol_Ratio")) else 1.0
    vol_spike = bool(last.get("Vol_Spike", False))

    score = 0.0  # -5 to +5
    signals = []     # Detail sinyal
    setups = []      # Setup scalping terdeteksi
    warnings = []    # Peringatan risiko

    # ═══════════════════════════════════════════════════════
    # 1. TREND ANALYSIS (Triple EMA)
    # ═══════════════════════════════════════════════════════
    if ema5 and ema13 and ema21:
        if ema5 > ema13 > ema21:
            score += 1.5
            trend_status = "BULLISH KUAT"
            trend_detail = f"EMA5({ema5:.0f}) > EMA13({ema13:.0f}) > EMA21({ema21:.0f}) — Perfect Uptrend"
            signals.append(("Triple EMA", "BUY", trend_detail))
        elif ema5 > ema13 and ema13 <= ema21:
            score += 0.5
            trend_status = "BULLISH AWAL"
            trend_detail = f"EMA5({ema5:.0f}) > EMA13({ema13:.0f}), tapi EMA13 masih di bawah EMA21({ema21:.0f})"
            signals.append(("Triple EMA", "BUY", trend_detail))
        elif ema5 < ema13 < ema21:
            score -= 1.5
            trend_status = "BEARISH KUAT"
            trend_detail = f"EMA5({ema5:.0f}) < EMA13({ema13:.0f}) < EMA21({ema21:.0f}) — Perfect Downtrend"
            signals.append(("Triple EMA", "SELL", trend_detail))
        elif ema5 < ema13 and ema13 >= ema21:
            score -= 0.5
            trend_status = "BEARISH AWAL"
            trend_detail = f"EMA5({ema5:.0f}) < EMA13({ema13:.0f}), EMA13 masih di atas EMA21({ema21:.0f})"
            signals.append(("Triple EMA", "SELL", trend_detail))
        else:
            trend_status = "SIDEWAYS / TRANSISI"
            trend_detail = f"EMA saling bersilangan — Pasar tidak memiliki arah yang jelas"
            signals.append(("Triple EMA", "NETRAL", trend_detail))

        # Pullback ke EMA detection
        price_vs_ema5_pct = ((current_price - ema5) / ema5 * 100)
        if ema5 > ema13 > ema21 and -1.5 < price_vs_ema5_pct < 0:
            setups.append({
                "name": "📌 Pullback to EMA5 (Bullish)",
                "type": "bullish",
                "reliability": "High",
                "detail": f"Harga koreksi ringan mendekati EMA5 ({ema5:.0f}) dalam uptrend sempurna. "
                          f"Entry ideal saat harga pantulan dari EMA5, Target ke high sebelumnya.",
                "entry": f"Entry di area Rp {ema5:.0f} ± Rp {(atr5 or current_price*0.01)*0.3:.0f}",
                "exit": f"Target: Rp {float(last['high']):,.0f} (high hari ini) | SL: Rp {ema13:.0f}",
            })
        elif ema5 < ema13 < ema21 and 0 < price_vs_ema5_pct < 1.5:
            setups.append({
                "name": "📌 Pullback to EMA5 (Bearish)",
                "type": "bearish",
                "reliability": "High",
                "detail": f"Harga memantul naik sementara mendekati EMA5 ({ema5:.0f}) dalam downtrend. "
                          f"Peluang short / jual saat gagal tembus EMA5.",
                "entry": f"Jual di area Rp {ema5:.0f} ± Rp {(atr5 or current_price*0.01)*0.3:.0f}",
                "exit": f"Target: Rp {float(last['low']):,.0f} (low hari ini) | SL: Rp {ema13:.0f}",
            })
    else:
        trend_status = "N/A"
        trend_detail = "Data tidak cukup"

    # ═══════════════════════════════════════════════════════
    # 2. MOMENTUM — RSI(5) Ultra Fast
    # ═══════════════════════════════════════════════════════
    if rsi5 is not None:
        if rsi5 < 20:
            score += 1.0
            signals.append(("RSI(5)", "BUY", f"RSI(5) = {rsi5:.1f} — EXTREME Oversold! Area rebound scalping."))
        elif rsi5 < 35:
            score += 0.5
            signals.append(("RSI(5)", "BUY", f"RSI(5) = {rsi5:.1f} — Mulai masuk area oversold."))
        elif rsi5 > 80:
            score -= 1.0
            signals.append(("RSI(5)", "SELL", f"RSI(5) = {rsi5:.1f} — EXTREME Overbought! Profit taking zone."))
        elif rsi5 > 65:
            score -= 0.5
            signals.append(("RSI(5)", "SELL", f"RSI(5) = {rsi5:.1f} — Mendekati overbought."))
        else:
            signals.append(("RSI(5)", "NETRAL", f"RSI(5) = {rsi5:.1f} — Zona netral, tunggu konfirmasi."))

    # ═══════════════════════════════════════════════════════
    # 3. TIMING — Stochastic Fast (5,3,3)
    # ═══════════════════════════════════════════════════════
    if stoch_k is not None and stoch_d is not None:
        golden_cross = (stoch_k_prev and stoch_d_prev and
                        stoch_k_prev < stoch_d_prev and stoch_k > stoch_d)
        death_cross = (stoch_k_prev and stoch_d_prev and
                       stoch_k_prev > stoch_d_prev and stoch_k < stoch_d)

        if golden_cross and stoch_k < 30:
            score += 1.0
            signals.append(("Stoch(5,3,3)", "BUY",
                f"Golden Cross di zona oversold (K={stoch_k:.1f}, D={stoch_d:.1f}) — Timing ENTRY IDEAL!"))
            setups.append({
                "name": "⚡ Stochastic Golden Cross Oversold",
                "type": "bullish", "reliability": "High",
                "detail": "Stochastic K memotong naik D di zona oversold (<30). Sinyal timing masuk paling kuat untuk scalper.",
                "entry": f"Entry SEGERA di Rp {current_price:,.0f}",
                "exit": f"Target: +{((atr5 or 1) * 1.0):.0f} poin | SL: -{((atr5 or 1) * 0.75):.0f} poin",
            })
        elif death_cross and stoch_k > 70:
            score -= 1.0
            signals.append(("Stoch(5,3,3)", "SELL",
                f"Death Cross di zona overbought (K={stoch_k:.1f}, D={stoch_d:.1f}) — Timing EXIT / SHORT!"))
            setups.append({
                "name": "⚡ Stochastic Death Cross Overbought",
                "type": "bearish", "reliability": "High",
                "detail": "Stochastic K memotong turun D di zona overbought (>70). Sinyal keluar atau short sell.",
                "entry": f"EXIT / Jual di Rp {current_price:,.0f}",
                "exit": f"Target: -{((atr5 or 1) * 1.0):.0f} poin | SL: +{((atr5 or 1) * 0.75):.0f} poin",
            })
        elif golden_cross:
            score += 0.5
            signals.append(("Stoch(5,3,3)", "BUY",
                f"Golden Cross (K={stoch_k:.1f}, D={stoch_d:.1f}) — Momentum mulai membaik"))
        elif death_cross:
            score -= 0.5
            signals.append(("Stoch(5,3,3)", "SELL",
                f"Death Cross (K={stoch_k:.1f}, D={stoch_d:.1f}) — Momentum melemah"))
        else:
            zone = "Overbought" if stoch_k > 80 else ("Oversold" if stoch_k < 20 else "Netral")
            signals.append(("Stoch(5,3,3)", "NETRAL",
                f"K={stoch_k:.1f}, D={stoch_d:.1f} — Zona {zone}, tunggu crossover"))

    # ═══════════════════════════════════════════════════════
    # 4. VOLATILITY — Bollinger Band Squeeze
    # ═══════════════════════════════════════════════════════
    if bb_width is not None:
        if is_squeeze:
            setups.append({
                "name": "🔥 Bollinger Squeeze (Siap Breakout!)",
                "type": "neutral_explosive", "reliability": "High",
                "detail": f"BB Width ({bb_width:.1f}%) menyempit di bawah rata-rata — Volatilitas terkompresi, "
                          f"ledakan harga besar akan segera terjadi. Scalper menunggu arah breakout.",
                "entry": f"Beli jika breakout ke atas BB Upper | Jual jika breakdown ke bawah BB Lower",
                "exit": f"Target: ±{((atr5 or 1) * 2.0):.0f} poin dari titik breakout | SL: kembali ke BB Mid",
            })
            signals.append(("BB Squeeze", "ALERT",
                f"⚠️ SQUEEZE AKTIF! BB Width={bb_width:.1f}% < Rata-rata — Breakout imminent!"))
        elif bb_width > 8 and vol_spike:
            signals.append(("BB Expansion", "ALERT",
                f"BB melebar ({bb_width:.1f}%) + Volume spike ({vol_ratio:.1f}x) — Momentum besar sedang terjadi"))

    # ═══════════════════════════════════════════════════════
    # 5. TREND STRENGTH — ADX
    # ═══════════════════════════════════════════════════════
    if adx is not None:
        if adx < 20:
            warnings.append(f"⚠️ ADX Rendah ({adx:.1f}) — Pasar SIDEWAYS lemah, scalping berisiko tinggi (whipsaw)")
            signals.append(("ADX", "WARNING", f"ADX={adx:.1f} — Tren LEMAH. Hindari entry agresif."))
        elif adx > 25 and di_pos and di_neg:
            if di_pos > di_neg:
                score += 0.5
                signals.append(("ADX", "BUY", f"ADX={adx:.1f}, +DI({di_pos:.1f}) > -DI({di_neg:.1f}) — Trend NAIK kuat"))
            else:
                score -= 0.5
                signals.append(("ADX", "SELL", f"ADX={adx:.1f}, -DI({di_neg:.1f}) > +DI({di_pos:.1f}) — Trend TURUN kuat"))
        else:
            signals.append(("ADX", "NETRAL", f"ADX={adx:.1f} — Tren moderat"))

    # ═══════════════════════════════════════════════════════
    # 6. VOLUME CONFIRMATION
    # ═══════════════════════════════════════════════════════
    if vol_spike and score > 0:
        score += 0.5
        signals.append(("Volume", "CONFIRM",
            f"Volume {vol_ratio:.1f}x di atas rata-rata — KONFIRMASI pergerakan kuat!"))
    elif vol_spike and score < 0:
        score -= 0.5
        signals.append(("Volume", "CONFIRM",
            f"Volume {vol_ratio:.1f}x di atas rata-rata — TEKANAN JUAL kuat!"))
    elif vol_ratio < 0.5:
        warnings.append(f"⚠️ Volume sangat tipis ({vol_ratio:.1f}x rata-rata) — Gerakan harga tidak bisa dipercaya")

    # ═══════════════════════════════════════════════════════
    # 7. MACD SCALPING (5,13,4) — Momentum Divergence
    # ═══════════════════════════════════════════════════════
    if macd_hist is not None and macd_hist_prev is not None:
        if macd_hist > 0 and macd_hist > macd_hist_prev:
            score += 0.5
            signals.append(("MACD Scalp", "BUY",
                f"Histogram MACD(5,13,4) positif & menguat ({macd_hist:.2f}) — Momentum naik akseleratif"))
        elif macd_hist < 0 and macd_hist < macd_hist_prev:
            score -= 0.5
            signals.append(("MACD Scalp", "SELL",
                f"Histogram MACD(5,13,4) negatif & memburuk ({macd_hist:.2f}) — Momentum turun akseleratif"))
        elif macd_hist > 0 and macd_hist < macd_hist_prev:
            signals.append(("MACD Scalp", "CAUTION",
                f"MACD positif tapi melemah ({macd_hist:.2f}) — Momentum naik mulai kehilangan tenaga"))
        elif macd_hist < 0 and macd_hist > macd_hist_prev:
            signals.append(("MACD Scalp", "CAUTION",
                f"MACD negatif tapi membaik ({macd_hist:.2f}) — Tekanan jual mulai berkurang"))

    # ═══════════════════════════════════════════════════════
    # FINAL CLASSIFICATION
    # ═══════════════════════════════════════════════════════
    max_score = 5.5
    ratio = score / max_score

    if ratio >= 0.55:
        final_signal = "SCALP BUY"
        final_color = "#00C853"
        final_emoji = "🟢🟢"
    elif ratio >= 0.2:
        final_signal = "SCALP BUY (Lemah)"
        final_color = "#69F0AE"
        final_emoji = "🟢"
    elif ratio <= -0.55:
        final_signal = "SCALP SELL"
        final_color = "#D50000"
        final_emoji = "🔴🔴"
    elif ratio <= -0.2:
        final_signal = "SCALP SELL (Lemah)"
        final_color = "#FF6D00"
        final_emoji = "🔴"
    else:
        final_signal = "WAIT / TIDAK ADA SETUP"
        final_color = "#FFD740"
        final_emoji = "⏸️"

    strength = max(5, min(95, int((ratio + 1) / 2 * 100)))

    # ═══════════════════════════════════════════════════════
    # RISK MANAGEMENT CALCULATION (Kusus Pasar Saham Indonesia / Long-Only)
    # ═══════════════════════════════════════════════════════
    # Di BEI tidak ada short-selling reguler bagi ritel. Semua entry scalping adalah BELI (Buy Low Sell High).
    # Jika sinyal BEARISH/SELL, maknanya adalah JUAL barang yang sudah ada / JANGAN BELI (Wait).
    
    # Toleransi risiko per lembar (0.75x ATR5, minimum Rp 1)
    risk_per_share = max(1.0, round((atr5 or current_price * 0.02) * 0.75, 0))
    reward_per_share = round(risk_per_share * 1.5, 0)  # TP minimal 1:1.5

    is_buy_bias = score >= 0

    if is_buy_bias:
        # Rencana jika ingin BUY (Membeli saham)
        plan_action = "BUY / LONG"
        entry_price = current_price
        stop_loss = max(1.0, round(current_price - risk_per_share, 0))
        take_profit = round(current_price + reward_per_share, 0)
        sl_pct = round((current_price - stop_loss) / current_price * 100, 2)
        tp_pct = round((take_profit - current_price) / current_price * 100, 2)
        action_guide = f"Beli di Rp {entry_price:,.0f} | Pasang Cut Loss di Rp {stop_loss:,.0f} (-{sl_pct}%) | Ambil Untung di Rp {take_profit:,.0f} (+{tp_pct}%)"
    else:
        # Sinyal SELL / BEARISH: Bagi scalper di BEI ini adalah waktu EXIT / JANGAN BELI
        plan_action = "SELL / EXIT (Jangan Masuk)"
        entry_price = current_price
        stop_loss = round(current_price + risk_per_share, 0)  # Batas toleransi jika masih nekat hold
        take_profit = max(1.0, round(current_price - reward_per_share, 0))  # Area harga berpotensi turun ke sini
        sl_pct = round(risk_per_share / current_price * 100, 2)
        tp_pct = round(reward_per_share / current_price * 100, 2)
        action_guide = f"Tekanan jual tinggi! Yang punya saham segera JUAL di Rp {current_price:,.0f}. Yang belum punya JANGAN BELI, potensi turun ke Rp {take_profit:,.0f} (-{tp_pct}%)."

    # Perhitungan ukuran lot berdasarkan aturan risiko max Rp 50.000 per trade
    suggested_lot = max(1, int(50_000 / (risk_per_share * 100))) if risk_per_share > 0 else 1

    risk_mgmt = {
        "plan_action": plan_action,
        "is_buy_bias": is_buy_bias,
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "risk_per_share": risk_per_share,
        "reward_per_share": reward_per_share,
        "risk_pct": sl_pct,
        "reward_pct": tp_pct,
        "risk_reward_ratio": f"1 : {reward_per_share / max(risk_per_share, 0.01):.1f}",
        "suggested_lot": suggested_lot,
        "max_daily_loss": f"Rp {risk_per_share * suggested_lot * 100:,.0f}",
        "action_guide": action_guide,
        "atr5": round(atr5, 2) if atr5 else None,
    }

    # ═══════════════════════════════════════════════════════
    # INDICATOR SNAPSHOT
    # ═══════════════════════════════════════════════════════
    snapshot = {
        "price": current_price,
        "ema5": round(ema5, 2) if ema5 else None,
        "ema13": round(ema13, 2) if ema13 else None,
        "ema21": round(ema21, 2) if ema21 else None,
        "rsi5": round(rsi5, 1) if rsi5 else None,
        "rsi14": round(rsi14, 1) if rsi14 else None,
        "stoch_k": round(stoch_k, 1) if stoch_k else None,
        "stoch_d": round(stoch_d, 1) if stoch_d else None,
        "williams_r": round(williams_r, 1) if williams_r else None,
        "adx": round(adx, 1) if adx else None,
        "di_pos": round(di_pos, 1) if di_pos else None,
        "di_neg": round(di_neg, 1) if di_neg else None,
        "bb_width": round(bb_width, 2) if bb_width else None,
        "is_squeeze": is_squeeze,
        "vol_ratio": round(vol_ratio, 2),
        "vol_spike": vol_spike,
        "macd_hist": round(macd_hist, 4) if macd_hist else None,
        "atr5": round(atr5, 2) if atr5 else None,
        "atr14": round(atr14, 2) if atr14 else None,
        "trend_status": trend_status,
        "trend_detail": trend_detail,
    }

    return {
        "signal": final_signal,
        "color": final_color,
        "emoji": final_emoji,
        "strength": strength,
        "score": round(score, 2),
        "max_score": max_score,
        "signals": signals,
        "setups": setups,
        "warnings": warnings,
        "risk_mgmt": risk_mgmt,
        "snapshot": snapshot,
        "df": df,
    }
