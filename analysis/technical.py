"""analysis/technical.py — Kalkulasi indikator teknikal menggunakan library 'ta' (pure Python)"""

import pandas as pd
import ta
from ta.momentum import RSIIndicator
from ta.trend import SMAIndicator, EMAIndicator, MACD
from ta.volatility import BollingerBands, AverageTrueRange
from ta.volume import OnBalanceVolumeIndicator, ChaikinMoneyFlowIndicator

from config import (
    RSI_PERIOD, RSI_OVERSOLD, RSI_OVERBOUGHT,
    MA_SHORT, MA_MID, MA_LONG,
    BB_PERIOD, BB_STD,
    MACD_FAST, MACD_SLOW, MACD_SIGNAL,
)


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Tambahkan semua indikator teknikal ke DataFrame OHLCV.
    Input: DataFrame dengan kolom date, open, high, low, close, volume
    Output: DataFrame yang sama dengan kolom tambahan indikator.
    """
    if df.empty or len(df) < 30:
        return df

    df = df.copy()
    close = df["close"]
    high  = df["high"]
    low   = df["low"]
    vol   = df["volume"]

    # ── Moving Averages ───────────────────────────────────
    df[f"MA{MA_SHORT}"]  = SMAIndicator(close, window=MA_SHORT).sma_indicator()
    df[f"MA{MA_MID}"]    = SMAIndicator(close, window=MA_MID).sma_indicator()
    df[f"MA{MA_LONG}"]   = SMAIndicator(close, window=MA_LONG).sma_indicator()
    df["EMA20"]          = EMAIndicator(close, window=20).ema_indicator()

    # ── RSI ───────────────────────────────────────────────
    df["RSI"] = RSIIndicator(close, window=RSI_PERIOD).rsi()

    # ── MACD ─────────────────────────────────────────────
    macd_obj = MACD(close, window_fast=MACD_FAST, window_slow=MACD_SLOW, window_sign=MACD_SIGNAL)
    df["MACD"]        = macd_obj.macd()
    df["MACD_Signal"] = macd_obj.macd_signal()
    df["MACD_Hist"]   = macd_obj.macd_diff()

    # ── Bollinger Bands ───────────────────────────────────
    bb_obj = BollingerBands(close, window=BB_PERIOD, window_dev=BB_STD)
    df["BB_Upper"] = bb_obj.bollinger_hband()
    df["BB_Mid"]   = bb_obj.bollinger_mavg()
    df["BB_Lower"] = bb_obj.bollinger_lband()

    # ── Volume MA ─────────────────────────────────────────
    df["Vol_MA20"] = SMAIndicator(vol, window=20).sma_indicator()

    # ── ATR ───────────────────────────────────────────────
    df["ATR"] = AverageTrueRange(high, low, close, window=14).average_true_range()

    # ── Smart Money / Volume Flow (OBV & CMF) ─────────────
    df["OBV"] = OnBalanceVolumeIndicator(close, vol).on_balance_volume()
    df["OBV_EMA20"] = EMAIndicator(df["OBV"], window=20).ema_indicator()
    df["CMF"] = ChaikinMoneyFlowIndicator(high, low, close, vol, window=20).chaikin_money_flow()

    return df


def get_latest_indicator_snapshot(df: pd.DataFrame) -> dict:
    """
    Return dict berisi nilai terbaru semua indikator.
    """
    if df.empty:
        return {}

    df_ind = add_indicators(df)
    last = df_ind.iloc[-1]

    def _safe(val):
        try:
            v = float(val)
            return round(v, 4) if not pd.isna(v) else None
        except Exception:
            return None

    snap = {
        "close":         _safe(last.get("close")),
        "volume":        _safe(last.get("volume")),
        f"MA{MA_SHORT}": _safe(last.get(f"MA{MA_SHORT}")),
        f"MA{MA_MID}":   _safe(last.get(f"MA{MA_MID}")),
        f"MA{MA_LONG}":  _safe(last.get(f"MA{MA_LONG}")),
        "RSI":           _safe(last.get("RSI")),
        "MACD":          _safe(last.get("MACD")),
        "MACD_Signal":   _safe(last.get("MACD_Signal")),
        "MACD_Hist":     _safe(last.get("MACD_Hist")),
        "BB_Upper":      _safe(last.get("BB_Upper")),
        "BB_Mid":        _safe(last.get("BB_Mid")),
        "BB_Lower":      _safe(last.get("BB_Lower")),
        "Vol_MA20":      _safe(last.get("Vol_MA20")),
        "ATR":           _safe(last.get("ATR")),
        "OBV":           _safe(last.get("OBV")),
        "OBV_EMA20":     _safe(last.get("OBV_EMA20")),
        "CMF":           _safe(last.get("CMF")),
    }
    return snap


def get_smart_money_flow(df: pd.DataFrame) -> dict:
    """
    Analisis arus dana institusi / Smart Money (Chaikin Money Flow & OBV).
    """
    if df.empty or len(df) < 25:
        return {"status": "UNKNOWN", "cmf": 0, "obv_trend": "Netral", "detail": "Data tidak cukup"}

    df_ind = add_indicators(df)
    last = df_ind.iloc[-1]
    prev = df_ind.iloc[-2] if len(df_ind) > 1 else last

    cmf = float(last.get("CMF", 0)) if not pd.isna(last.get("CMF")) else 0.0
    obv = float(last.get("OBV", 0)) if not pd.isna(last.get("OBV")) else 0.0
    obv_ema = float(last.get("OBV_EMA20", 0)) if not pd.isna(last.get("OBV_EMA20")) else 0.0

    # CMF interpretation: > 0.05 Accumulation, < -0.05 Distribution
    if cmf >= 0.15:
        cmf_status = "AKUMULASI MASIF (Smart Money Masuk)"
        cmf_color = "#00C853"
        cmf_emoji = "🟢🟢"
    elif cmf >= 0.05:
        cmf_status = "Akumulasi Moderat"
        cmf_color = "#69F0AE"
        cmf_emoji = "🟢"
    elif cmf <= -0.15:
        cmf_status = "DISTRIBUSI MASIF (Smart Money Keluar)"
        cmf_color = "#D50000"
        cmf_emoji = "🔴🔴"
    elif cmf <= -0.05:
        cmf_status = "Distribusi Moderat"
        cmf_color = "#FF6D00"
        cmf_emoji = "🔴"
    else:
        cmf_status = "Netral / Seimbang"
        cmf_color = "#FFD740"
        cmf_emoji = "⚪"

    # OBV trend vs EMA20
    obv_above_ema = obv > obv_ema
    obv_trend = "Bullish (OBV > EMA20)" if obv_above_ema else "Bearish (OBV < EMA20)"

    # Divergence check (15 bar)
    recent = df_ind.tail(15)
    price_change = (recent["close"].iloc[-1] - recent["close"].iloc[0]) / recent["close"].iloc[0]
    obv_change = (recent["OBV"].iloc[-1] - recent["OBV"].iloc[0])

    divergence = "Tidak ada"
    if price_change < -0.02 and obv_change > 0:
        divergence = "🔥 BULLISH DIVERGENCE (Harga Turun tapi Akumulasi Volume Naik — Potensi Rebound Kuat!)"
    elif price_change > 0.02 and obv_change < 0:
        divergence = "⚠️ BEARISH DIVERGENCE (Harga Naik tapi Volume Turun — Waspada Jebakan Pucuk!)"

    detail = (
        f"Chaikin Money Flow (CMF): {cmf:+.2f} ({cmf_status}). "
        f"Tren Volume OBV: {obv_trend}. {divergence}"
    )

    return {
        "cmf": round(cmf, 3),
        "cmf_status": cmf_status,
        "cmf_color": cmf_color,
        "cmf_emoji": cmf_emoji,
        "obv": round(obv, 0),
        "obv_ema": round(obv_ema, 0),
        "obv_trend": obv_trend,
        "divergence": divergence,
        "detail": detail,
    }


def get_ma_signal(snap: dict) -> dict:
    ma20  = snap.get(f"MA{MA_SHORT}")
    ma50  = snap.get(f"MA{MA_MID}")
    close = snap.get("close")

    if not all([ma20, ma50, close]):
        return {"signal": "UNKNOWN", "detail": "Data tidak cukup"}

    if ma20 > ma50 and close > ma50:
        return {"signal": "BUY", "detail": f"Golden Cross: MA{MA_SHORT}({ma20:.0f}) > MA{MA_MID}({ma50:.0f})"}
    elif ma20 < ma50 and close < ma50:
        return {"signal": "SELL", "detail": f"Death Cross: MA{MA_SHORT}({ma20:.0f}) < MA{MA_MID}({ma50:.0f})"}
    else:
        return {"signal": "HOLD", "detail": f"MA{MA_SHORT}={ma20:.0f}, MA{MA_MID}={ma50:.0f}"}


def get_rsi_signal(snap: dict) -> dict:
    rsi = snap.get("RSI")
    if rsi is None:
        return {"signal": "UNKNOWN", "detail": "RSI tidak tersedia"}

    if rsi <= RSI_OVERSOLD:
        return {"signal": "BUY", "detail": f"RSI={rsi:.1f} — Oversold (bawah {RSI_OVERSOLD})"}
    elif rsi >= RSI_OVERBOUGHT:
        return {"signal": "SELL", "detail": f"RSI={rsi:.1f} — Overbought (atas {RSI_OVERBOUGHT})"}
    else:
        return {"signal": "HOLD", "detail": f"RSI={rsi:.1f} — Netral"}


def get_macd_signal(snap: dict) -> dict:
    macd   = snap.get("MACD")
    signal = snap.get("MACD_Signal")
    hist   = snap.get("MACD_Hist")

    if macd is None or signal is None:
        return {"signal": "UNKNOWN", "detail": "MACD tidak tersedia"}

    if macd > signal and hist and hist > 0:
        return {"signal": "BUY", "detail": f"MACD({macd:.2f}) > Signal({signal:.2f}), histogram positif"}
    elif macd < signal and hist and hist < 0:
        return {"signal": "SELL", "detail": f"MACD({macd:.2f}) < Signal({signal:.2f}), histogram negatif"}
    else:
        return {"signal": "HOLD", "detail": f"MACD={macd:.2f}, Signal={signal:.2f}"}


def get_bb_signal(snap: dict) -> dict:
    close = snap.get("close")
    lower = snap.get("BB_Lower")
    upper = snap.get("BB_Upper")

    if not all([close, lower, upper]):
        return {"signal": "UNKNOWN", "detail": "Bollinger Bands tidak tersedia"}

    if close <= lower:
        return {"signal": "BUY", "detail": f"Harga ({close:.0f}) menyentuh/di bawah Lower Band ({lower:.0f})"}
    elif close >= upper:
        return {"signal": "SELL", "detail": f"Harga ({close:.0f}) menyentuh/di atas Upper Band ({upper:.0f})"}
    else:
        return {"signal": "HOLD", "detail": f"Harga dalam Bollinger Bands ({lower:.0f} - {upper:.0f})"}


def get_volume_signal(snap: dict) -> dict:
    vol    = snap.get("volume")
    vol_ma = snap.get("Vol_MA20")

    if not vol or not vol_ma or vol_ma == 0:
        return {"signal": "UNKNOWN", "detail": "Data volume tidak cukup"}

    ratio = vol / vol_ma
    if ratio > 2.0:
        return {"signal": "WATCH", "detail": f"Volume spike! {ratio:.1f}x rata-rata ({vol:,.0f} vs avg {vol_ma:,.0f})"}
    else:
        return {"signal": "NORMAL", "detail": f"Volume normal ({ratio:.1f}x rata-rata)"}


def get_technical_scorecard(df: pd.DataFrame) -> dict:
    """
    Buat scorecard lengkap semua indikator.
    Returns dict dengan semua signal per indikator.
    """
    snap = get_latest_indicator_snapshot(df)
    if not snap:
        return {}

    return {
        "snapshot": snap,
        "ma":     get_ma_signal(snap),
        "rsi":    get_rsi_signal(snap),
        "macd":   get_macd_signal(snap),
        "bb":     get_bb_signal(snap),
        "volume": get_volume_signal(snap),
    }
