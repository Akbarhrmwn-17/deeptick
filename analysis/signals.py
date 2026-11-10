"""analysis/signals.py — Generate sinyal BUY/SELL berbasis analisis teknikal + fundamental (Engine V3)"""

from typing import Optional
from data.fetcher import get_price_df_from_db
from analysis.technical import get_technical_scorecard
from analysis.patterns import get_stochrsi_signal, detect_patterns, find_support_resistance
from database.models import (
    save_signal,
    get_fundamental,
    get_alert_rules,
    get_latest_price,
)


def generate_action_plan(
    signal_type: str,
    current_price: float,
    atr: Optional[float] = None,
    sr_levels: Optional[dict] = None,
) -> dict:
    """
    Menghasilkan Action Plan / Rencana Trading profesional untuk SEMUA jenis sinyal:
    - BUY / STRONG_BUY: Area akumulasi, Stop Loss ATR/Support, Target TP 1 & 2
    - SELL / STRONG_SELL: Strategi Exit/Cut loss untuk yang punya barang, area pantau Re-Entry untuk yang belum punya
    - HOLD: Level Trailing Stop untuk yang punya barang, level pantau Breakout/Pullback untuk yang belum punya
    - AVOID / HIGH_RISK: Panduan likuidasi FCA / larangan masuk proteksi modal
    - HOLD / ILLIQUID: Panduan antrian limit order lot kecil
    """
    if not current_price or current_price <= 0:
        return {}

    sr = sr_levels or {}
    sup = sr.get("nearest_support") or (current_price * 0.95)
    res = sr.get("nearest_resistance") or (current_price * 1.05)
    buffer = (atr * 1.5) if (atr and atr > 0) else (current_price * 0.04)

    sup_dist = round(((current_price - sup) / current_price * 100), 1) if current_price else 0
    res_dist = round(((res - current_price) / current_price * 100), 1) if current_price else 0

    if "BUY" in signal_type:
        stop_loss = max(1.0, min(sup, current_price - buffer))
        t1 = round(res, 0) if res > current_price else round(current_price + buffer, 0)
        t2 = round(current_price + (buffer * 2.0), 0)
        risk_pct = round((current_price - stop_loss) / current_price * 100, 1)
        reward_pct = round((t2 - current_price) / current_price * 100, 1)
        return {
            "action": "BUY / AKUMULASI",
            "badge_color": "#00C853",
            "if_holding": f"Tambah muatan bertahap (averaging up) jika berhasil breakout Resistance Rp {res:,.0f} (+{res_dist}%) didukung volume tinggi.",
            "if_not_holding": f"Entry bertahap di area Rp {current_price:,.0f} s/d Rp {sup:,.0f}. Wajib disiplin cut loss jika breakdown di bawah Rp {stop_loss:,.0f} (-{risk_pct}%).",
            "key_levels": f"Stop Loss: Rp {stop_loss:,.0f} (-{risk_pct}%) | Target 1: Rp {t1:,.0f} | Target 2: Rp {t2:,.0f} (+{reward_pct}%)",
            "stop_loss": round(stop_loss, 0),
            "target_1": round(t1, 0),
            "target_2": round(t2, 0),
            "risk_pct": risk_pct,
            "reward_pct": reward_pct,
            "summary": f"Entry Rp {current_price:,.0f} | SL: Rp {stop_loss:,.0f} (-{risk_pct}%) | TP: Rp {t2:,.0f} (+{reward_pct}%)",
        }
    elif "SELL" in signal_type:
        reentry = round(sup, 0)
        return {
            "action": "SELL / EXIT STRATEGY",
            "badge_color": "#D50000",
            "if_holding": f"Amankan profit atau batasi risiko dengan EXIT di Rp {current_price:,.0f}. Batas toleransi terakhir jika ingin hold adalah Support Rp {sup:,.0f} (-{sup_dist}%).",
            "if_not_holding": f"WAIT & SEE — Jangan tangkap pisau jatuh! Tunggu terbentuk pola reversal atau pantulan terkonfirmasi di Support Rp {reentry:,.0f} (-{sup_dist}%).",
            "key_levels": f"Exit Sekarang: Rp {current_price:,.0f} | Support Pantau Re-entry: Rp {reentry:,.0f} (-{sup_dist}%)",
            "stop_loss": round(current_price, 0),
            "target_1": round(reentry, 0),
            "target_2": None,
            "risk_pct": 0.0,
            "reward_pct": sup_dist,
            "summary": f"Exit di Rp {current_price:,.0f} | Jangan beli dulu, pantau reversal di Rp {reentry:,.0f}",
        }
    elif "AVOID" in signal_type:
        return {
            "action": "AVOID / PROTEKSI MODAL EKSTREM",
            "badge_color": "#E91E63",
            "if_holding": "Evaluasi likuidasi bertahap pada sesi Full Call Auction (FCA) bila terdapat antrian bid. DILARANG KERAS averaging down!",
            "if_not_holding": "STAY AWAY 100% — Saham FCA/gocap (< Rp 50). Sangat berisiko modal terkunci dan tidak bisa diperdagangkan secara reguler.",
            "key_levels": "Papan Pemantauan Khusus (FCA) — Likuiditas & Mekanisme Pasar Terbatas",
            "stop_loss": None,
            "target_1": None,
            "target_2": None,
            "risk_pct": 100.0,
            "reward_pct": 0.0,
            "summary": "Hindari transaksi — Potensi risiko modal terkunci sangat tinggi",
        }
    elif "ILLIQUID" in signal_type:
        return {
            "action": "HOLD / ILLIQUID WARNING",
            "badge_color": "#FFB300",
            "if_holding": "Jika ingin menjual, pasang antrian limit order bertahap dengan lot kecil pada harga offer. Jangan buang kiri (HAKI) sekaligus.",
            "if_not_holding": "Hindari masuk dalam jumlah lot besar. Volume transaksi tipis dan spread lebar menyulitkan exit cepat.",
            "key_levels": f"Support: Rp {sup:,.0f} | Resistance: Rp {res:,.0f}",
            "stop_loss": round(sup, 0),
            "target_1": round(res, 0),
            "target_2": None,
            "risk_pct": sup_dist,
            "reward_pct": res_dist,
            "summary": "Likuiditas tipis — Gunakan antrian limit order kecil jika bertransaksi",
        }
    else:  # HOLD
        trailing_stop = max(1.0, sup)
        ts_pct = round((current_price - trailing_stop) / current_price * 100, 1)
        breakout = round(res, 0)
        bo_pct = round((breakout - current_price) / current_price * 100, 1)
        return {
            "action": "HOLD / TRAILING STOP",
            "badge_color": "#FFD740",
            "if_holding": f"Pertahankan posisi (Let Winners Run). Pasang Trailing Stop di Support Rp {trailing_stop:,.0f} (-{ts_pct}%) untuk mengunci keuntungan.",
            "if_not_holding": f"WAIT FOR BREAKOUT — Tunggu konfirmasi breakout Resistance Rp {breakout:,.0f} (+{bo_pct}%) dengan volume tinggi, atau Buy on Weakness di Support Rp {trailing_stop:,.0f}.",
            "key_levels": f"Trailing Stop: Rp {trailing_stop:,.0f} (-{ts_pct}%) | Target Breakout: Rp {breakout:,.0f} (+{bo_pct}%)",
            "stop_loss": round(trailing_stop, 0),
            "target_1": round(breakout, 0),
            "target_2": None,
            "risk_pct": ts_pct,
            "reward_pct": bo_pct,
            "summary": f"Hold dengan Trailing Stop Rp {trailing_stop:,.0f} (-{ts_pct}%) | Tunggu Breakout Rp {breakout:,.0f}",
        }


def calculate_trade_levels(current_price: float, atr: Optional[float]) -> dict:
    """Backward compatibility wrapper."""
    return generate_action_plan("BUY", current_price, atr)


def generate_signals(ticker: str) -> Optional[dict]:
    """
    Generate sinyal trading berakurasi tinggi dengan filter likuiditas,
    papan khusus (saham FCA/gocap), konfirmasi volume, tren mayor, dan batas stop loss.
    """
    df = get_price_df_from_db(ticker, limit=365)
    if df.empty or len(df) < 30:
        return None

    scorecard = get_technical_scorecard(df)
    if not scorecard:
        return None

    snap = scorecard.get("snapshot", {})
    current_price = snap.get("close") or 0.0
    volume = snap.get("volume") or 0.0
    vol_ma20 = snap.get("Vol_MA20") or 0.0
    ma20 = snap.get("MA20")
    ma50 = snap.get("MA50")
    ma200 = snap.get("MA200")
    rsi = snap.get("RSI")
    macd = snap.get("MACD")
    macd_signal = snap.get("MACD_Signal")
    macd_hist = snap.get("MACD_Hist")
    atr = snap.get("ATR")

    fund = get_fundamental(ticker) or {}
    rules = get_alert_rules(ticker)

    score = 0
    max_score = 7.0   # V3: +0.75 StochRSI +0.5 Candlestick ditambahkan
    reasons = []
    warnings = []
    trade_plan = {}

    # ─────────────────────────────────────────────────────────────
    # FILTER 1: PENGECEKAN SAHAM GOCAP / PAPAN KHUSUS (FCA)
    # ─────────────────────────────────────────────────────────────
    is_penny_stock = current_price < 50.0
    if is_penny_stock:
        warnings.append("⚠️ SAHAM GOCAP/FCA: Harga di bawah Rp 50. Sinyal teknikal tidak valid!")

    # ─────────────────────────────────────────────────────────────
    # FILTER 2: LIKUIDITAS VOLUME
    # ─────────────────────────────────────────────────────────────
    is_illiquid = volume < 500_000
    if is_illiquid and not is_penny_stock:
        warnings.append(f"⚠️ VOLUME RENDAH: Volume harian hanya {volume:,.0f} lembar. Rawan manipulasi.")

    # ─────────────────────────────────────────────────────────────
    # 1. TREN: MA CROSSOVER & HARGA VS MA20/MA50
    # ─────────────────────────────────────────────────────────────
    if ma20 and ma50:
        if ma20 > ma50:
            if current_price > ma20:
                score += 1.5
                reasons.append(f"• Golden Cross: MA20 ({ma20:.0f}) > MA50 ({ma50:.0f}) & Harga di atas MA20")
            else:
                score += 0.5
                reasons.append(f"• Trend Positif: MA20 > MA50, tapi harga sedang koreksi di bawah MA20")
        else:
            if current_price < ma20:
                score -= 1.5
                reasons.append(f"• Death Cross: MA20 ({ma20:.0f}) < MA50 ({ma50:.0f}) & Harga di bawah MA20")
            else:
                score -= 0.5
                reasons.append(f"• Trend Lemah: MA20 < MA50, harga mencoba rebound menembus MA20")

    # ─────────────────────────────────────────────────────────────
    # 2. TREN MAYOR: MA200 (REGIM PASAR)
    # ─────────────────────────────────────────────────────────────
    if ma200:
        if current_price > ma200:
            score += 0.5
            reasons.append(f"• Super Trend: Harga ({current_price:.0f}) di atas MA200 ({ma200:.0f}) — Uptrend Jangka Panjang")
        else:
            score -= 0.5
            reasons.append(f"• Downtrend Mayor: Harga ({current_price:.0f}) di bawah MA200 ({ma200:.0f})")

    # ─────────────────────────────────────────────────────────────
    # 3. MOMENTUM: RSI (14) DENGAN PENCEGAH FALLING KNIFE
    # ─────────────────────────────────────────────────────────────
    if rsi is not None:
        if rsi < 25:
            # Extreme oversold
            if macd_hist and macd_hist > 0:
                score += 1.0
                reasons.append(f"• RSI Reversal: RSI ({rsi:.1f}) Super Oversold + MACD Hist membaik (Ada Rebound)")
            else:
                reasons.append(f"• Warning Falling Knife: RSI ({rsi:.1f}) sangat rendah tapi belum ada konfirmasi pantulan")
                score -= 0.5
        elif rsi <= 35:
            score += 0.5
            reasons.append(f"• RSI Masuk Area Oversold ({rsi:.1f})")
        elif rsi >= 75:
            score -= 1.0
            reasons.append(f"• RSI Overbought Ekstrem ({rsi:.1f}) — Rawan Aksi Profit Taking")
        elif rsi >= 65:
            score -= 0.5
            reasons.append(f"• RSI Tinggi ({rsi:.1f}) mendekati overbought")

    # ─────────────────────────────────────────────────────────────
    # 3.5. STOCHASTIC RSI (lebih sensitif, konfirmasi timing entry)
    # ─────────────────────────────────────────────────────────────
    try:
        stoch_sig = get_stochrsi_signal(df)
        stoch_signal_type = stoch_sig.get("signal", "HOLD")
        stoch_k = stoch_sig.get("k")
        if stoch_k is not None:
            if stoch_signal_type == "BUY" and stoch_k < 20:
                score += 0.75
                reasons.append(f"• StochRSI Oversold Kuat (K={stoch_k:.0f}%): Timing entry terbaik")
            elif stoch_signal_type == "BUY":
                score += 0.5
                reasons.append(f"• StochRSI K memotong naik (K={stoch_k:.0f}%): Momentum membaik")
            elif stoch_signal_type == "SELL" and stoch_k > 80:
                score -= 0.75
                reasons.append(f"• StochRSI Overbought Kuat (K={stoch_k:.0f}%): Timing keluar/tunggu koreksi")
            elif stoch_signal_type == "SELL":
                score -= 0.5
                reasons.append(f"• StochRSI K memotong turun (K={stoch_k:.0f}%): Momentum melemah")
    except Exception:
        pass  # StochRSI tidak wajib, skip jika error

    # ─────────────────────────────────────────────────────────────
    # 3.6. CANDLESTICK PATTERN (konfirmasi sinyal dari pola visual)
    # ─────────────────────────────────────────────────────────────
    try:
        patterns = detect_patterns(df)
        if patterns:
            latest_pat = patterns[0]  # Pola paling baru
            if latest_pat["type"] == "bullish" and latest_pat["reliability"] == "High":
                score += 0.5
                reasons.append(f"• Pola Bullish Kuat: {latest_pat['pattern']} terdeteksi ({str(latest_pat['date'])[:10]})")
            elif latest_pat["type"] == "bearish" and latest_pat["reliability"] == "High":
                score -= 0.5
                reasons.append(f"• Pola Bearish Kuat: {latest_pat['pattern']} terdeteksi ({str(latest_pat['date'])[:10]})")
    except Exception:
        pass

    # ─────────────────────────────────────────────────────────────
    # 4. KONFIRMASI MACD
    # ─────────────────────────────────────────────────────────────
    if macd is not None and macd_signal is not None and macd_hist is not None:
        if macd > macd_signal and macd_hist > 0:
            score += 1.0
            reasons.append(f"• MACD Bullish: MACD ({macd:.2f}) > Signal ({macd_signal:.2f}) dengan momentum menguat")
        elif macd < macd_signal and macd_hist < 0:
            score -= 1.0
            reasons.append(f"• MACD Bearish: MACD ({macd:.2f}) < Signal ({macd_signal:.2f}) dengan momentum melemah")

    # ─────────────────────────────────────────────────────────────
    # 5. KONFIRMASI VOLUME TRANSAKSI
    # ─────────────────────────────────────────────────────────────
    if vol_ma20 > 0:
        vol_ratio = volume / vol_ma20
        if vol_ratio >= 1.5 and score > 0:
            score += 0.5
            reasons.append(f"• Konfirmasi Volume: Terjadi akumulasi ({vol_ratio:.1f}x dari rata-rata 20 hari)")
        elif vol_ratio < 0.5 and score > 1.0:
            score -= 0.5
            reasons.append(f"• Volume Lemah: Kenaikan tidak didukung volume transaksi ({vol_ratio:.1f}x)")

    # ─────────────────────────────────────────────────────────────
    # 6. FILTER FUNDAMENTAL (KESEHATAN BISNIS)
    # ─────────────────────────────────────────────────────────────
    pe = fund.get("pe_ratio")
    roe = fund.get("roe")
    der = fund.get("der")

    if roe is not None:
        if roe > 0.15:
            score += 0.5
            reasons.append(f"• Fundamental Sehat: ROE menguntungkan ({roe*100:.1f}%)")
        elif roe < 0:
            score -= 0.5
            reasons.append(f"• Risiko Fundamental: Perusahaan membukukan kerugian (ROE {roe*100:.1f}%)")

    if der is not None and der > 5.0:
        score -= 0.5
        reasons.append(f"• Utang Sangat Tinggi: DER ({der:.1f}x)")

    # ─────────────────────────────────────────────────────────────
    # 7. ALERT RULES KUSTOM USER
    # ─────────────────────────────────────────────────────────────
    if rules and current_price > 0:
        for rule in rules:
            rt = rule.get("rule_type")
            val = rule.get("value")
            if rt == "PRICE_BELOW" and current_price < val:
                reasons.append(f"• Alert Terpicu: Harga ({current_price:.0f}) < Batas Target Beli ({val:.0f})")
                score += 1.0
            elif rt == "PRICE_ABOVE" and current_price > val:
                reasons.append(f"• Alert Terpicu: Harga ({current_price:.0f}) > Batas Target Jual ({val:.0f})")
                score -= 1.0

    # ─────────────────────────────────────────────────────────────
    # FINAL CLASSIFICATION & SAFETY OVERRIDE
    # ─────────────────────────────────────────────────────────────
    # VETO KERAS: Jika saham di bawah Rp 50, TIDAK BOLEH BUY!
    if is_penny_stock:
        signal_type = "AVOID / HIGH_RISK"
        strength = 10
        score = -5.0
    elif is_illiquid:
        signal_type = "HOLD / ILLIQUID"
        strength = 30
    else:
        ratio = score / max_score
        if ratio >= 0.55:
            signal_type = "STRONG_BUY"
        elif ratio >= 0.25:
            signal_type = "BUY"
        elif ratio <= -0.55:
            signal_type = "STRONG_SELL"
        elif ratio <= -0.25:
            signal_type = "SELL"
        else:
            signal_type = "HOLD"
        
        strength = max(5, min(95, int((ratio + 1) / 2 * 100)))

    # Buat Action Plan untuk SEMUA jenis sinyal (BUY, SELL, HOLD, AVOID)
    sr_levels = find_support_resistance(df)
    trade_plan = generate_action_plan(signal_type, current_price, atr, sr_levels)
    if trade_plan:
        reasons.append(f"🎯 Action Plan ({trade_plan['action']}):")
        reasons.append(f"  • Sudah Punya: {trade_plan['if_holding']}")
        reasons.append(f"  • Belum Punya: {trade_plan['if_not_holding']}")
        reasons.append(f"  • Level Kunci: {trade_plan['key_levels']}")

    all_notes = warnings + reasons
    reason_text = "\n".join(all_notes) if all_notes else "Kondisi konsolidasi, belum ada tren dominan."

    return {
        "signal_type": signal_type,
        "strength":    strength,
        "score":       round(score, 2),
        "max_score":   max_score,
        "reasons":     reason_text,
        "trade_plan":  trade_plan,
        "scorecard":   scorecard,
        "is_warning":  bool(warnings),
    }


def generate_and_save_signals(ticker: str):
    """Generate sinyal dan simpan ke database jika relevan."""
    result = generate_signals(ticker)
    if not result:
        return None

    sig = result["signal_type"]
    save_signal(
        ticker=ticker,
        signal_type=sig,
        strength=result["strength"],
        reason=result["reasons"],
    )
    print(f"[Signal Engine V3] {ticker}: {sig} (strength={result['strength']})")
    return result
