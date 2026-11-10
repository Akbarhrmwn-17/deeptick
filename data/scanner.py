"""data/scanner.py — Engine Batch Screening Saham BEI

Fitur Kuantitatif:
1. Batch download via yfinance untuk seluruh IDX Universe (~80 emiten) dalam 3-5 detik
2. Screening 4 Kategori Profesional:
   - 🔥 Trending & Volume Surge: Volume >= 1.2x MA20, Net Gain, CMF/Accumulation, Breakout
   - ⚡ Top Scalping Setups: Bollinger Squeeze, Stochastic Cross, EMA Pullback, ATR% tinggi
   - 🌊 Top Swing Trading: Stage 2 Uptrend (Price > EMA20 > MA50), Pullback MA20, MACD Bullish
   - 🔮 Peluang Naik Besok: Directional Probability T+1 > 52% berdasarkan model multi-faktor
3. Streamlit cache terintegrasi untuk performa instan
"""

import time
import pandas as pd
import numpy as np
import yfinance as yf
from typing import Dict, List, Tuple, Any

from config import YF_SUFFIX
from data.idx_universe import IDX_UNIVERSE, get_all_universe_tickers
from analysis.scalping import compute_scalping_indicators, generate_scalping_signals
from analysis.forecast import calculate_next_day_forecast
from analysis.technical import add_indicators


def fetch_universe_ohlcv_batch(tickers: List[str] = None, period: str = "2mo") -> Dict[str, pd.DataFrame]:
    """
    Batch download data OHLCV harian dari Yahoo Finance untuk list emiten IDX.
    Mengembalikan dict: { 'BBCA': df, 'BBRI': df, ... } dengan kolom standard.
    """
    if not tickers:
        tickers = get_all_universe_tickers()

    yf_map = {f"{t}{YF_SUFFIX}": t for t in tickers}
    yf_tickers = list(yf_map.keys())

    try:
        raw_df = yf.download(
            yf_tickers,
            period=period,
            interval="1d",
            group_by="ticker",
            progress=False,
            auto_adjust=True,
        )
    except Exception as e:
        print(f"[Scanner] Error downloading batch: {e}")
        return {}

    result = {}
    if raw_df.empty:
        return result

    for yf_t, clean_t in yf_map.items():
        try:
            if yf_t in raw_df.columns:
                stock_df = raw_df[yf_t].dropna(how="all").copy()
            elif (yf_t,) in raw_df.columns:
                stock_df = raw_df[(yf_t,)].dropna(how="all").copy()
            else:
                continue

            if stock_df.empty or len(stock_df) < 15:
                continue

            stock_df = stock_df.reset_index()
            # Standardize column names lowercase
            stock_df.columns = [str(c).lower() for c in stock_df.columns]
            rename_map = {}
            for col in stock_df.columns:
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

            stock_df.rename(columns=rename_map, inplace=True)
            required_cols = ["date", "open", "high", "low", "close", "volume"]
            if all(rc in stock_df.columns for rc in required_cols):
                stock_df = stock_df.dropna(subset=["close", "volume"])
                if len(stock_df) >= 15:
                    result[clean_t] = stock_df
        except Exception as e:
            continue

    return result


def run_full_market_scan(dfs: Dict[str, pd.DataFrame] = None) -> Dict[str, List[Dict[str, Any]]]:
    """
    Eksekusi algoritma screening pasar profesional terhadap seluruh data OHLCV yang tersedia.
    Menghasilkan 4 kategori screening:
    1. 'trending': Saham breakout & lonjakan volume
    2. 'scalping': Setup cepat terbaik (Squeeze, Stoch cross, High ATR%)
    3. 'swing': Setup trend-following & pullback MA
    4. 'forecast': Saham dengan probabilitas naik tertinggi besok
    """
    if dfs is None:
        dfs = fetch_universe_ohlcv_batch()

    universe_dict = {item["ticker"]: item for item in IDX_UNIVERSE}

    trending_list = []
    scalping_list = []
    swing_list = []
    forecast_list = []

    for ticker, df in dfs.items():
        if df.empty or len(df) < 15:
            continue

        meta = universe_dict.get(ticker, {
            "name": ticker,
            "sector": "Umum",
            "tags": []
        })

        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else last
        c = float(last["close"])
        p_c = float(prev["close"])
        h = float(last["high"])
        l = float(last["low"])
        v = float(last["volume"])
        change_pct = ((c - p_c) / p_c * 100) if p_c > 0 else 0.0

        vol_window = min(20, len(df))
        vol_ma = float(df["volume"].tail(vol_window).mean())
        vol_ratio = v / max(vol_ma, 1.0)

        # ── 1. TRENDING & VOLUME SURGE SCREENER ──────────────────
        high_20d = float(df["high"].tail(20).max())
        is_breakout = c >= (high_20d * 0.985)
        
        trend_score = 0
        reasons_trend = []
        if vol_ratio >= 2.0:
            trend_score += 40
            reasons_trend.append(f"Volume meledak {vol_ratio:.1f}x MA20")
        elif vol_ratio >= 1.3:
            trend_score += 25
            reasons_trend.append(f"Volume akumulasi di atas rata-rata ({vol_ratio:.1f}x)")

        if change_pct >= 4.0:
            trend_score += 30
            reasons_trend.append(f"Kenaikan agresif +{change_pct:.1f}%")
        elif change_pct >= 1.5:
            trend_score += 20
            reasons_trend.append(f"Kenaikan solid +{change_pct:.1f}%")

        if is_breakout:
            trend_score += 30
            reasons_trend.append("Breakout / Dekat High 20 Hari")

        if trend_score >= 45 or (vol_ratio >= 1.4 and change_pct > 0):
            trending_list.append({
                "ticker": ticker,
                "name": meta["name"],
                "sector": meta["sector"],
                "price": c,
                "change_pct": change_pct,
                "vol_ratio": round(vol_ratio, 2),
                "volume": int(v),
                "trend_score": min(100, trend_score),
                "reason": " • ".join(reasons_trend) if reasons_trend else "Momentum positif",
                "is_breakout": is_breakout,
            })

        # ── 2. SCALPING ENGINE SCREENER (ANCHOR PATEN & BUY ZONE TRACKING) ──
        try:
            # Gunakan baseline harga acuan (penutupan kemarin / candle pembuka sesi) agar angka rencana PATEN
            df_base = df.iloc[:-1].copy() if len(df) > 1 else df.copy()
            scalp_base = generate_scalping_signals(df_base)
            risk_base = scalp_base.get("risk_mgmt", {})
            is_buy_bias = risk_base.get("is_buy_bias", False)
            bullish_setups = [s for s in scalp_base.get("setups", []) if s.get("type") == "bullish"]
            
            # Wajib sinyal acuan adalah BUY murni (Entry < TP)
            if scalp_base and is_buy_bias and "SELL" not in scalp_base.get("signal", ""):
                snap_base = scalp_base.get("snapshot", {})
                setups_base = scalp_base.get("setups", [])
                primary_setup = setups_base[0]["name"] if setups_base else "Momentum Scalp"
                
                # Angka Rencana PATEN (tidak bergeser mengikuti running)
                entry_paten = risk_base.get("entry_price", p_c)
                tp_paten = risk_base.get("take_profit", entry_paten * 1.03)
                sl_paten = risk_base.get("stop_loss", entry_paten * 0.98)
                reward_pct = risk_base.get("reward_pct", 3.0)
                risk_pct = risk_base.get("risk_pct", 2.0)
                rr_ratio = risk_base.get("risk_reward_ratio", "1 : 1.5")
                
                # Evaluasi Real-Time Harga Running vs Entry Paten (Buy Zone)
                diff_entry_pct = ((c - entry_paten) / entry_paten * 100) if entry_paten > 0 else 0.0
                
                if h >= tp_paten:
                    zone_label = "🎯 TARGET TERCAPAI"
                    zone_badge = "WIN"
                    zone_desc = f"Harga sempat melesat ke Rp {h:,.0f} menyentuh target profit!"
                elif l <= sl_paten:
                    zone_label = "🛑 HIT STOP LOSS"
                    zone_badge = "LOSS"
                    zone_desc = f"Harga sempat turun ke Rp {l:,.0f} melewati batas risiko."
                elif diff_entry_pct > 2.5:
                    zone_label = f"🚀 SUDAH TERBANG (+{diff_entry_pct:.1f}%)"
                    zone_badge = "CHASE"
                    zone_desc = "Harga sudah melesat jauh dari entry paten, jangan kejar (hindari FOMO)!"
                elif -1.5 <= diff_entry_pct <= 1.5:
                    zone_label = f"🟢 IDEAL BUY ZONE ({diff_entry_pct:+.1f}%)"
                    zone_badge = "BUY"
                    zone_desc = "Harga running masih di sekitar harga rencana beli. Siap antri!"
                elif diff_entry_pct < -1.5:
                    zone_label = f"⚠️ DEKAT STOP LOSS ({diff_entry_pct:+.1f}%)"
                    zone_badge = "WARN"
                    zone_desc = "Harga terkoreksi di bawah entry paten, awasi batas cut loss ketat."
                else:
                    zone_label = f"🟡 RUNNING ({diff_entry_pct:+.1f}%)"
                    zone_badge = "NEUTRAL"
                    zone_desc = "Harga bergerak aktif di dalam rentang rencana trading."
                
                # Hitung Probabilitas Akumulasi & Buffer Hindari Area Bawah
                df_tech = add_indicators(df)
                last_tech = df_tech.iloc[-1]
                cmf_val = float(last_tech.get("CMF", 0)) if not pd.isna(last_tech.get("CMF")) else 0.0
                
                # CLV (Closing Location Value)
                h_f, l_f, c_f = float(last_tech["high"]), float(last_tech["low"]), float(last_tech["close"])
                day_rng = max(h_f - l_f, 0.001)
                clv = ((c_f - l_f) - (h_f - c_f)) / day_rng  # -1.0 s/d +1.0
                
                # Formula Probabilitas Akumulasi (Smart Money Flow)
                acc_score = 50.0 + (cmf_val * 90.0) + (clv * 20.0)
                if snap_base.get("vol_ratio", 1.0) >= 1.3 and c_f >= float(last_tech["open"]):
                    acc_score += 12.0
                elif snap_base.get("vol_ratio", 1.0) >= 1.3 and c_f < float(last_tech["open"]):
                    acc_score -= 12.0
                prob_accum = max(10, min(95, round(acc_score, 1)))
                
                # Buffer Jarak ke Area Bawah (Low hari ini & Stop Loss)
                buffer_low_pct = max(0.0, round((c_f - l_f) / c_f * 100, 2))
                buffer_sl_pct = max(0.0, round((c_f - sl_paten) / c_f * 100, 2))

                scalping_list.append({
                    "ticker": ticker,
                    "name": meta["name"],
                    "sector": meta["sector"],
                    "price": c,
                    "change_pct": change_pct,
                    "signal": scalp_base["signal"],
                    "score": scalp_base["score"],
                    "entry": entry_paten,
                    "stop_loss": sl_paten,
                    "take_profit": tp_paten,
                    "risk_pct": risk_pct,
                    "reward_pct": reward_pct,
                    "rr_ratio": rr_ratio,
                    "atr5": snap_base.get("atr5", 0),
                    "is_squeeze": snap_base.get("is_squeeze", False),
                    "vol_ratio": snap_base.get("vol_ratio", 1.0),
                    "setup_name": primary_setup,
                    "action_guide": risk_base.get("action_guide", ""),
                    "diff_entry_pct": round(diff_entry_pct, 2),
                    "zone_label": zone_label,
                    "zone_badge": zone_badge,
                    "zone_desc": zone_desc,
                    "prob_accum": prob_accum,
                    "buffer_low_pct": buffer_low_pct,
                    "buffer_sl_pct": buffer_sl_pct,
                    "cmf_val": round(cmf_val, 3),
                })
        except Exception:
            pass

        # ── 3. SWING TRADING SCREENER ───────────────────────────
        if len(df) >= 30:
            try:
                c_series = df["close"]
                sma20 = float(c_series.tail(20).mean())
                sma50 = float(c_series.tail(min(50, len(c_series))).mean())

                dist_sma20_pct = (c - sma20) / sma20 * 100
                is_uptrend = c >= sma20 and (len(c_series) < 50 or sma20 >= sma50)
                is_pullback = is_uptrend and (-1.5 <= dist_sma20_pct <= 2.5)

                swing_score = 0
                swing_reasons = []

                if is_uptrend:
                    swing_score += 35
                    swing_reasons.append("Stage 2 Uptrend (Di atas MA)")
                if is_pullback:
                    swing_score += 35
                    swing_reasons.append(f"Ideal Pullback dekat MA20 ({dist_sma20_pct:+.1f}%)")

                if len(c_series) >= 26:
                    df_tech = add_indicators(df)
                    if "MACD_Hist" in df_tech.columns:
                        m_hist = float(df_tech["MACD_Hist"].iloc[-1])
                        m_hist_prev = float(df_tech["MACD_Hist"].iloc[-2])
                        if m_hist > 0 and m_hist > m_hist_prev:
                            swing_score += 30
                            swing_reasons.append("MACD Bullish Expansion")
                        elif m_hist > m_hist_prev:
                            swing_score += 15
                            swing_reasons.append("MACD Rebound Positif")

                if swing_score >= 50:
                    sl_swing = round(min(sma20 * 0.97, c * 0.95), 0)
                    risk_pts = max(c - sl_swing, c * 0.03)
                    tp_swing = round(c + (risk_pts * 2.0), 0)
                    sl_pct = (c - sl_swing) / c * 100
                    tp_pct = (tp_swing - c) / c * 100

                    swing_list.append({
                        "ticker": ticker,
                        "name": meta["name"],
                        "sector": meta["sector"],
                        "price": c,
                        "change_pct": change_pct,
                        "swing_score": swing_score,
                        "entry": c,
                        "stop_loss": sl_swing,
                        "take_profit": tp_swing,
                        "sl_pct": round(sl_pct, 1),
                        "tp_pct": round(tp_pct, 1),
                        "rr_ratio": f"1 : {tp_pct/max(sl_pct, 0.1):.1f}",
                        "setup": " • ".join(swing_reasons),
                        "dist_ma20": round(dist_sma20_pct, 1),
                    })
            except Exception:
                pass

        # ── 4. PREDIKSI BESOK (T+1 DIRECTIONAL PROBABILITY) ───────
        try:
            fc = calculate_next_day_forecast(df)
            if fc and fc.get("prob_up", 0) >= 52.0:
                forecast_list.append({
                    "ticker": ticker,
                    "name": meta["name"],
                    "sector": meta["sector"],
                    "price": c,
                    "change_pct": change_pct,
                    "prob_up": fc["prob_up"],
                    "prob_down": fc["prob_down"],
                    "bias": fc.get("bias", "BULLISH"),
                    "est_low": fc.get("est_low", c * 0.98),
                    "est_high": fc.get("est_high", c * 1.03),
                    "pivot": fc.get("pivot", c),
                    "reasons": " • ".join(fc.get("reasons_bullish", [])) if fc.get("reasons_bullish") else "Momentum naik",
                    "tactic": fc.get("tactical_guide", {}).get("bias_text", ""),
                })
        except Exception:
            pass

    trending_list.sort(key=lambda x: (x["trend_score"], x["vol_ratio"]), reverse=True)
    scalping_list.sort(key=lambda x: (x["score"], x["vol_ratio"]), reverse=True)
    swing_list.sort(key=lambda x: x["swing_score"], reverse=True)
    forecast_list.sort(key=lambda x: x["prob_up"], reverse=True)

    return {
        "trending": trending_list,
        "scalping": scalping_list,
        "swing": swing_list,
        "forecast": forecast_list,
        "scanned_count": len(dfs),
    }


def run_historical_validation(dfs: Dict[str, pd.DataFrame] = None) -> Dict[str, Any]:
    """
    Validasi performa sinyal kemarin terhadap pergerakan riil pasar hari ini.
    Mengevaluasi apakah saham yang kemarin disarankan memberi peluang cuan (Win/Loss/BEP).
    """
    if dfs is None:
        dfs = fetch_universe_ohlcv_batch()

    universe_dict = {item['ticker']: item for item in IDX_UNIVERSE}
    history_records = []
    
    date_signal = ''
    date_eval = ''

    for t, df in dfs.items():
        if len(df) < 20:
            continue
        df_yest = df.iloc[:-1].copy()
        today_bar = df.iloc[-1]
        yest_bar = df_yest.iloc[-1]

        date_signal = str(yest_bar['date'])[:10]
        date_eval = str(today_bar['date'])[:10]

        meta = universe_dict.get(t, {'name': t, 'sector': 'Umum'})
        c_yest = float(yest_bar['close'])
        t_open = float(today_bar['open'])
        t_high = float(today_bar['high'])
        t_low = float(today_bar['low'])
        t_close = float(today_bar['close'])

        scalp = generate_scalping_signals(df_yest)
        risk = scalp.get('risk_mgmt', {})
        is_buy_bias = risk.get('is_buy_bias', False)
        bullish_setups = [s for s in scalp.get('setups', []) if s.get('type') == 'bullish']
        is_valid_scalp = is_buy_bias and 'SELL' not in scalp.get('signal', '')

        fc = calculate_next_day_forecast(df_yest)
        prob_up = fc.get('prob_up', 50.0) if fc else 50.0

        if is_valid_scalp or prob_up >= 60.0:
            max_gain_pct = (t_high - c_yest) / c_yest * 100
            close_gain_pct = (t_close - c_yest) / c_yest * 100
            max_drawdown_pct = (t_low - c_yest) / c_yest * 100

            risk = scalp.get('risk_mgmt', {})
            tp = risk.get('take_profit', c_yest * 1.025)
            sl = risk.get('stop_loss', c_yest * 0.98)

            hit_tp = t_high >= tp
            hit_sl = t_low <= sl

            if max_gain_pct >= 2.0 or hit_tp:
                outcome = '🎯 TARGET PROFIT TERCAPAI'
                badge_type = 'WIN'
            elif max_gain_pct >= 0.8:
                outcome = '✅ PELUANG CUAN INTRADAY'
                badge_type = 'WIN'
            elif max_drawdown_pct <= -2.0 or hit_sl:
                outcome = '🛑 KENA STOP LOSS'
                badge_type = 'LOSS'
            else:
                outcome = '⏸️ NETRAL / BEP'
                badge_type = 'NEUTRAL'

            setup_display = bullish_setups[0]['name'] if bullish_setups else (scalp.get('setups', [{}])[0].get('name', 'Momentum Scalp') if scalp.get('setups') else 'Momentum Scalp')

            gain_pts = t_high - c_yest
            history_records.append({
                'ticker': t,
                'name': meta['name'],
                'sector': meta['sector'],
                'date_signal': date_signal,
                'date_eval': date_eval,
                'price_signal': c_yest,
                'target_tp': tp,
                'stop_loss': sl,
                'gain_pts': gain_pts,
                'today_open': t_open,
                'today_high': t_high,
                'today_low': t_low,
                'today_close': t_close,
                'max_gain_pct': round(max_gain_pct, 2),
                'close_gain_pct': round(close_gain_pct, 2),
                'max_dd_pct': round(max_drawdown_pct, 2),
                'scalp_signal': scalp.get('signal', 'N/A'),
                'scalp_score': scalp.get('score', 0),
                'setup_name': setup_display,
                'prob_up': prob_up,
                'hit_tp': hit_tp,
                'hit_sl': hit_sl,
                'outcome': outcome,
                'badge_type': badge_type,
            })

    history_records.sort(key=lambda x: x['max_gain_pct'], reverse=True)
    total = len(history_records)
    win_count = sum(1 for r in history_records if r['badge_type'] == 'WIN')
    loss_count = sum(1 for r in history_records if r['badge_type'] == 'LOSS')
    neutral_count = total - win_count - loss_count
    win_rate = (win_count / total * 100) if total > 0 else 0.0
    avg_gain = sum(r['max_gain_pct'] for r in history_records) / max(total, 1)

    return {
        'records': history_records,
        'total': total,
        'win_count': win_count,
        'loss_count': loss_count,
        'neutral_count': neutral_count,
        'win_rate': round(win_rate, 1),
        'avg_max_gain': round(avg_gain, 2),
        'date_signal': date_signal,
        'date_eval': date_eval,
    }
