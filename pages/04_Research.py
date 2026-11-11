"""pages/03_Research.py — Analisis mendalam teknikal + fundamental per saham"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

from database.models import get_watchlist, get_fundamental, get_latest_price, get_portfolio_summary
from data.fetcher import fetch_price_history, get_price_df_from_db, fetch_fundamental_yf
from data.fundamental import get_all_fundamental
from database.models import upsert_fundamental
import importlib
import analysis.technical
import analysis.calculator
import analysis.forecast
try:
    importlib.reload(analysis.technical)
    importlib.reload(analysis.calculator)
    importlib.reload(analysis.forecast)
except Exception:
    pass

from analysis.technical import add_indicators, get_technical_scorecard, get_smart_money_flow
from analysis.signals import generate_signals
from analysis.patterns import detect_patterns, find_support_resistance, get_stochrsi_signal
from analysis.scalping import generate_scalping_signals, compute_scalping_indicators
from analysis.forecast import calculate_next_day_forecast
from analysis.calculator import calculate_trade_position, calculate_holding_exit, generate_whatsapp_trading_plan

st.set_page_config(page_title="Research — Saham Monitor", page_icon="🔬", layout="wide")
st.title("🔬 Research & Analisis Mendalam")


# ── Sidebar ───────────────────────────────────────────────
with st.sidebar:
    st.header("Pilih Saham")
    watchlist = get_watchlist()

    if not watchlist:
        st.warning("Watchlist kosong. Tambah saham di Settings.")
        st.stop()

    ticker_list = [s["ticker"] for s in watchlist]
    selected = st.selectbox(
        "Saham",
        ticker_list,
        index=0,
        format_func=lambda t: f"{t} — {next((s['name'] for s in watchlist if s['ticker']==t), '')}",
    )
    stock_info = next((s for s in watchlist if s["ticker"] == selected), {})

    if st.button("🔄 Refresh Semua Data", use_container_width=True):
        with st.spinner("Mengambil data..."):
            fetch_price_history(selected, period="2y", save_to_db=True)
            fund = get_all_fundamental(selected)
            if fund:
                upsert_fundamental(selected, fund)
        st.success("Data diperbarui!")
        st.rerun()


st.subheader(f"📊 {selected} — {stock_info.get('name', '')} | {stock_info.get('sector', '')}")

# ── Load Data ─────────────────────────────────────────────
df_raw = get_price_df_from_db(selected, limit=500)
fund = get_fundamental(selected)
latest_price = get_latest_price(selected)

tab_today, tab_forecast, tab_tech, tab_fund, tab_signal, tab_scalp, tab_pattern, tab_sr = st.tabs([
    "🎯 Prediksi Hari Ini",
    "🔮 Proyeksi Besok",
    "📈 Teknikal",
    "📊 Fundamental",
    "🚦 Sinyal & Skor",
    "⚡ Scalping Pro",
    "🕯️ Pola Candlestick",
    "📍 Support & Resistance",
])


# ════════════════════════════════════════════════════════
# TAB PREDIKSI & TRACKING HARI INI (BARU)
# ════════════════════════════════════════════════════════
with tab_today:
    st.subheader(f"🎯 Prediksi & Tracking Real-Time Hari Ini: {selected}")
    st.caption("Membandingkan hasil prediksi yang dihitung dari penutupan kemarin dengan data pergerakan riil pasar sesi hari ini.")

    if df_raw.empty or len(df_raw) < 25:
        st.info("Data belum cukup untuk kalkulasi prediksi hari ini (minimal butuh 25 hari bursa).")
    else:
        df_yest = df_raw.iloc[:-1].copy() if len(df_raw) > 1 else df_raw.copy()
        fc_td = calculate_next_day_forecast(df_yest)
        
        last_row = df_raw.iloc[-1]
        c_live = float(last_row["close"])
        h_today = float(last_row["high"])
        l_today = float(last_row["low"])
        o_today = float(last_row["open"])

        p_up_td = fc_td.get("prob_up", 50)
        p_down_td = fc_td.get("prob_down", 50)
        pivot_td = float(fc_td.get("pivot", c_live))
        p_max_td = float(fc_td.get("proj_max", c_live))
        p_min_td = float(fc_td.get("proj_min", c_live))
        r1_td = float(fc_td.get("r1", c_live))
        s1_td = float(fc_td.get("s1", c_live))
        diff_piv = c_live - pivot_td
        diff_piv_pct = (diff_piv / pivot_td * 100) if pivot_td > 0 else 0

        # Status tracking hari ini
        if c_live >= r1_td:
            td_status = "🚀 TARGET R1 TERCAPAI (BULLISH KUAT)"
            td_col = "#00C853"
            td_desc = f"Harga menembus target atas R1 (Rp {r1_td:,.0f}). Pembeli sangat dominan!"
        elif c_live > pivot_td:
            td_status = "🟢 ON TRACK BULLISH (Di Atas Pivot)"
            td_col = "#00C853"
            td_desc = f"Harga bertahan kokoh di atas level Pivot penentu (Rp {pivot_td:,.0f}). Skenario bullish aktif!"
        elif c_live <= s1_td:
            td_status = "🛑 JEBOL SUPPORT S1 (BEARISH)"
            td_col = "#D50000"
            td_desc = f"Harga tertekan menembus Support S1 (Rp {s1_td:,.0f}). Waspada pelemahan lanjutan!"
        else:
            td_status = "🟡 KONSOLIDASI (Menguji Support)"
            td_col = "#FFD740"
            td_desc = f"Harga berada sedikit di bawah Pivot (Rp {pivot_td:,.0f}), menguji bantalan support."

        # Hero Banner Tracking Hari Ini
        st.markdown(
            f"""
            <div style="background:{td_col}18; border: 2px solid {td_col}; border-radius: 12px;
                        padding: 16px 20px; margin-bottom: 20px;">
                <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap;">
                    <div>
                        <div style="font-size:0.85em; color:#bbb; text-transform:uppercase; letter-spacing:1px;">
                            Status Sesi Hari Ini vs Prediksi Pagi
                        </div>
                        <h3 style="color:{td_col}; margin:6px 0;">{td_status}</h3>
                        <p style="margin:0; color:#eee; font-size:0.95em;">💡 {td_desc}</p>
                    </div>
                    <div style="text-align:right;">
                        <span style="font-size:0.85em; color:#aaa;">Posisi vs Pivot Hari Ini:</span><br>
                        <span style="font-size:1.4em; font-weight:800; color:{'#00C853' if diff_piv >= 0 else '#D50000'};">
                            {diff_piv:+,.0f} ({diff_piv_pct:+.2f}%)
                        </span>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        col_t1, col_t2, col_t3 = st.columns(3)
        with col_t1:
            with st.container(border=True):
                st.markdown("### 📊 Prediksi Arah Hari Ini")
                st.metric("Peluang Menguat", f"{p_up_td}%", delta=fc_td.get("bias_label", "NETRAL"))
                st.progress(p_up_td / 100.0)
                st.markdown(f"- 🔼 **Target Maksimal:** `Rp {p_max_td:,.0f}`")
                st.markdown(f"- 📍 **Pivot Penentu:** `Rp {pivot_td:,.0f}`")
                st.markdown(f"- 🔻 **Batas Bawah:** `Rp {p_min_td:,.0f}`")

        with col_t2:
            with st.container(border=True):
                st.markdown("### ⚡ Realisasi Pasar Hari Ini")
                chg_open = c_live - o_today
                st.metric("Harga Terakhir", f"Rp {c_live:,.0f}", delta=f"{chg_open:+,.0f} vs Open")
                st.markdown(f"- 🔼 **Tertinggi (High):** `Rp {h_today:,.0f}`")
                st.markdown(f"- 🚪 **Pembukaan (Open):** `Rp {o_today:,.0f}`")
                st.markdown(f"- 🔻 **Terendah (Low):** `Rp {l_today:,.0f}`")

        with col_t3:
            with st.container(border=True):
                st.markdown("### 🧭 Panduan Eksekusi Hari Ini")
                if c_live >= pivot_td:
                    st.success(f"Harga berada di zona aman (di atas Pivot Rp {pivot_td:,.0f}). Rencana take profit tetap diincar di kisaran Rp {r1_td:,.0f} s/d Rp {p_max_td:,.0f}.")
                else:
                    st.warning(f"Harga di bawah Pivot Rp {pivot_td:,.0f}. Disiplin amankan posisi jika mendekati Support S1 Rp {s1_td:,.0f}.")
                st.caption(f"DeMark Range Hari Ini: **Rp {fc_td.get('demark_low',0):,.0f} - Rp {fc_td.get('demark_high',0):,.0f}**")

        st.markdown("---")
        st.markdown("#### 🔍 Posisi Harga Running di Dalam Rentang Prediksi Hari Ini:")
        fig_td = go.Figure()
        fig_td.add_trace(go.Scatter(
            x=[0, 10], y=[p_max_td, p_max_td],
            mode="lines", line=dict(color="#00C853", width=2),
            name="Batas Atas Prediksi"
        ))
        fig_td.add_trace(go.Scatter(
            x=[0, 10], y=[r1_td, r1_td],
            mode="lines", line=dict(color="#69F0AE", width=1.5, dash="dot"),
            name="Target R1"
        ))
        fig_td.add_trace(go.Scatter(
            x=[0, 10], y=[pivot_td, pivot_td],
            mode="lines", line=dict(color="#29B6F6", width=2, dash="dash"),
            name="Pivot Hari Ini"
        ))
        fig_td.add_trace(go.Scatter(
            x=[0, 10], y=[s1_td, s1_td],
            mode="lines", line=dict(color="#FF8A80", width=1.5, dash="dot"),
            name="Support S1"
        ))
        fig_td.add_trace(go.Scatter(
            x=[0, 10], y=[p_min_td, p_min_td],
            mode="lines", line=dict(color="#D50000", width=2),
            name="Batas Bawah Prediksi"
        ))
        fig_td.add_trace(go.Scatter(
            x=[5], y=[c_live],
            mode="markers+text",
            marker=dict(size=14, color="#ffffff", line=dict(width=3, color="#FFD740")),
            text=[f"Live: Rp {c_live:,.0f}"], textposition="middle right",
            name="Harga Saat Ini"
        ))
        fig_td.update_layout(
            template="plotly_dark",
            height=260,
            margin=dict(l=10, r=20, t=10, b=10),
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
            yaxis=dict(
                showgrid=True,
                tickvals=[p_min_td, s1_td, pivot_td, r1_td, p_max_td],
                ticktext=[f"Min: {p_min_td:,.0f}", f"S1: {s1_td:,.0f}", f"Pivot: {pivot_td:,.0f}", f"R1: {r1_td:,.0f}", f"Max: {p_max_td:,.0f}"],
            ),
        )
        st.plotly_chart(fig_td, use_container_width=True)

        st.divider()

# ════════════════════════════════════════════════════════
# TAB TEKNIKAL
# ════════════════════════════════════════════════════════
with tab_tech:
    if df_raw.empty:
        st.info("Belum ada data harga. Klik Refresh di sidebar.")
    else:
        df = add_indicators(df_raw)
        scorecard = get_technical_scorecard(df_raw)
        snap = scorecard.get("snapshot", {})

        # ── StochRSI & Smart Money Flow Banners ───────────
        stoch = get_stochrsi_signal(df_raw)
        stoch_colors = {"BUY": "#00C853", "SELL": "#D50000", "HOLD": "#FFD740", "UNKNOWN": "#888"}
        sc = stoch_colors.get(stoch["signal"], "#888")

        smf = get_smart_money_flow(df_raw)
        smf_col = smf.get("cmf_color", "#888")

        b_col1, b_col2 = st.columns(2)
        with b_col1:
            st.markdown(
                f'<div style="background:{sc}22;border:1px solid {sc};border-radius:8px;'
                f'padding:10px 16px;margin-bottom:12px;">'
                f'<b>⚡ StochRSI:</b> <span style="color:{sc};font-weight:bold;">{stoch["signal"]}</span>'
                f' — {stoch["detail"]}</div>',
                unsafe_allow_html=True,
            )
        with b_col2:
            st.markdown(
                f'<div style="background:{smf_col}22;border:1px solid {smf_col};border-radius:8px;'
                f'padding:10px 16px;margin-bottom:12px;">'
                f'<b>🌊 Smart Money Flow:</b> <span style="color:{smf_col};font-weight:bold;">{smf["cmf_status"]}</span>'
                f' (CMF: {smf["cmf"]:+.2f})</div>',
                unsafe_allow_html=True,
            )

        if smf.get("divergence") != "Tidak ada":
            st.warning(smf["divergence"])

        # ── Indikator Cards ───────────────────────────────
        st.subheader("📐 Nilai Indikator Terkini")
        col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
        stoch_k = f"{stoch['k']:.0f}%" if stoch["k"] is not None else "—"
        metrics = [
            ("RSI(14)",       snap.get("RSI"),    "< 30 = Oversold | > 70 = Overbought"),
            ("StochRSI K",    stoch["k"],          "< 20 = Oversold | > 80 = Overbought"),
            ("MA20",          snap.get("MA20"),   "Short-term trend"),
            ("MA50",          snap.get("MA50"),   "Mid-term trend"),
            ("MACD",          snap.get("MACD"),   "Momentum"),
            ("CMF (20)",      snap.get("CMF"),    "> +0.05 Akumulasi | < -0.05 Distribusi"),
            ("ATR(14)",       snap.get("ATR"),     "Volatilitas harian"),
        ]
        for col, (label, val, desc) in zip([col1, col2, col3, col4, col5, col6, col7], metrics):
            with col:
                if label.startswith("MA"):
                    display = f"Rp {val:,.0f}" if val else "—"
                elif label == "StochRSI K":
                    display = f"{val:.0f}%" if val is not None else "—"
                elif label.startswith("CMF"):
                    display = f"{val:+.2f}" if val is not None else "—"
                else:
                    display = f"{val:.2f}" if val else "—"
                st.metric(label, display)
                st.caption(desc)

        st.divider()

        # ── Grafik Perbandingan MA ─────────────────────────
        st.subheader("📉 Grafik MA + Harga (1 Tahun Terakhir)")
        df_1y = df.tail(252)

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_1y["date"], y=df_1y["close"], name="Harga",
            line=dict(color="white", width=2)
        ))
        for ma, color in [("MA20", "#1565C0"), ("MA50", "#E65100"), ("MA200", "#6A1B9A")]:
            if ma in df_1y.columns:
                fig.add_trace(go.Scatter(
                    x=df_1y["date"], y=df_1y[ma], name=ma,
                    line=dict(color=color, width=1.5)
                ))
        fig.update_layout(template="plotly_dark", height=350, margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig, use_container_width=True)

        # ── RSI + StochRSI History ────────────────────────
        st.subheader("📊 RSI + StochRSI History (6 Bulan Terakhir)")
        df_6m = df.tail(126)
        fig_rsi = go.Figure()
        if "RSI" in df_6m.columns:
            fig_rsi.add_trace(go.Scatter(
                x=df_6m["date"], y=df_6m["RSI"], name="RSI",
                line=dict(color="#AB47BC", width=2),
                fill="tozeroy", fillcolor="rgba(171,71,188,0.1)",
            ))
        # Add StochRSI K & D if available
        try:
            from ta.momentum import StochRSIIndicator
            _srsi = StochRSIIndicator(df_6m["close"], window=14, smooth1=3, smooth2=3)
            k_scaled = _srsi.stochrsi_k() * 100
            d_scaled = _srsi.stochrsi_d() * 100
            fig_rsi.add_trace(go.Scatter(
                x=df_6m["date"], y=k_scaled, name="StochRSI K",
                line=dict(color="#00E5FF", width=1.5, dash="dot"),
            ))
            fig_rsi.add_trace(go.Scatter(
                x=df_6m["date"], y=d_scaled, name="StochRSI D",
                line=dict(color="#FF6D00", width=1.5, dash="dot"),
            ))
        except Exception:
            pass
        fig_rsi.add_hline(y=70, line=dict(color="red",   dash="dash", width=1.5), annotation_text="OB 70")
        fig_rsi.add_hline(y=30, line=dict(color="green", dash="dash", width=1.5), annotation_text="OS 30")
        fig_rsi.add_hline(y=80, line=dict(color="orange", dash="dot",  width=1), annotation_text="StochRSI OB 80")
        fig_rsi.add_hline(y=20, line=dict(color="cyan",   dash="dot",  width=1), annotation_text="StochRSI OS 20")
        fig_rsi.add_hline(y=50, line=dict(color="gray",  dash="dot",  width=1))
        fig_rsi.update_layout(
            template="plotly_dark", height=280,
            yaxis=dict(range=[0, 100]),
            margin=dict(l=0, r=0, t=0, b=0),
        )
        st.plotly_chart(fig_rsi, use_container_width=True)

        # ── Bollinger Bands ───────────────────────────────
        st.subheader("📏 Bollinger Bands (3 Bulan Terakhir)")
        df_3m = df.tail(63)
        fig_bb = go.Figure()
        fig_bb.add_trace(go.Scatter(
            x=df_3m["date"], y=df_3m["BB_Upper"], name="BB Upper",
            line=dict(color="rgba(100,181,246,0.7)", dash="dot"),
        ))
        fig_bb.add_trace(go.Scatter(
            x=df_3m["date"], y=df_3m["BB_Lower"], name="BB Lower",
            line=dict(color="rgba(100,181,246,0.7)", dash="dot"),
            fill="tonexty", fillcolor="rgba(100,181,246,0.05)",
        ))
        fig_bb.add_trace(go.Scatter(
            x=df_3m["date"], y=df_3m["close"], name="Harga",
            line=dict(color="white", width=2),
        ))
        fig_bb.add_trace(go.Scatter(
            x=df_3m["date"], y=df_3m["BB_Mid"], name="BB Mid (MA20)",
            line=dict(color="#1565C0", dash="dash", width=1),
        ))
        fig_bb.update_layout(template="plotly_dark", height=300, margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig_bb, use_container_width=True)


# ════════════════════════════════════════════════════════
# TAB FUNDAMENTAL
# ════════════════════════════════════════════════════════
with tab_fund:
    if not fund:
        st.info("Belum ada data fundamental. Klik **Refresh Semua Data** di sidebar.")
    else:
        st.subheader("📊 Data Fundamental")
        col1, col2, col3, col4 = st.columns(4)

        def fmt_num(val, prefix="", suffix="", decimals=2):
            if val is None: return "—"
            if abs(val) >= 1e12: return f"{prefix}{val/1e12:.1f}T{suffix}"
            if abs(val) >= 1e9:  return f"{prefix}{val/1e9:.1f}M{suffix}"
            if abs(val) >= 1e6:  return f"{prefix}{val/1e6:.1f}Jt{suffix}"
            return f"{prefix}{val:.{decimals}f}{suffix}"

        with col1:
            pe = fund.get("pe_ratio")
            pe_note = "Murah (< 15)" if pe and pe < 15 else ("Mahal (> 30)" if pe and pe > 30 else "Wajar")
            st.metric("P/E Ratio", fmt_num(pe, decimals=2), pe_note)
            pb = fund.get("pb_ratio")
            st.metric("P/B Ratio", fmt_num(pb, decimals=2))

        with col2:
            roe = fund.get("roe")
            st.metric("ROE", fmt_num(roe, suffix="%", decimals=1) if roe else "—",
                      "Bagus (> 20%)" if roe and roe > 0.2 else "")
            der = fund.get("der")
            st.metric("DER", fmt_num(der, decimals=2) if der else "—")

        with col3:
            eps = fund.get("eps")
            st.metric("EPS", fmt_num(eps, prefix="Rp ", decimals=0) if eps else "—")
            div = fund.get("dividend_yield")
            st.metric("Dividend Yield",
                      f"{div*100:.2f}%" if div else "—",
                      "Baik (> 3%)" if div and div > 0.03 else "")

        with col4:
            mcap = fund.get("market_cap")
            st.metric("Market Cap", fmt_num(mcap, prefix="Rp "))
            rev = fund.get("revenue")
            st.metric("Revenue", fmt_num(rev, prefix="Rp "))

        st.divider()

        # Fundamental Scorecard
        st.subheader("🎯 Scorecard Fundamental")
        fund_items = [
            ("P/E Ratio", fund.get("pe_ratio"), lambda v: "✅ Value (< 15)" if v < 15 else ("⚠️ Wajar (15-30)" if v < 30 else "❌ Mahal (> 30)")),
            ("P/B Ratio", fund.get("pb_ratio"), lambda v: "✅ Murah (< 1)" if v < 1 else ("⚠️ Wajar (1-3)" if v < 3 else "❌ Mahal (> 3)")),
            ("ROE",       fund.get("roe"),       lambda v: "✅ Bagus (> 20%)" if v > 0.2 else ("⚠️ OK (10-20%)" if v > 0.1 else "❌ Lemah (< 10%)")),
            ("DER",       fund.get("der"),       lambda v: "✅ Aman (< 1)" if v < 1 else ("⚠️ Moderat (1-2)" if v < 2 else "❌ Berisiko (> 2)")),
        ]

        for name, val, evaluator in fund_items:
            if val is not None:
                try:
                    assessment = evaluator(float(val))
                    st.markdown(f"**{name}**: {val:.2f} — {assessment}")
                except Exception:
                    st.markdown(f"**{name}**: {val}")

        st.caption(f"Data diambil: {fund.get('fetched_at', 'N/A')}")

        # Profil Dividen & Aksi Korporasi
        from data.fundamental import fetch_dividend_info
        div_spec = fetch_dividend_info(selected)
        if div_spec.get("dividend_yield", 0) > 0 or div_spec.get("ex_dividend_date") != "-":
            st.divider()
            st.subheader("💰 Profil Dividen & Aksi Korporasi")
            cd1, cd2, cd3, cd4 = st.columns(4)
            cd1.metric("Dividend Yield", f"{div_spec['dividend_yield']}%")
            cd2.metric("Dividen Terakhir", f"Rp {div_spec['last_dividend']:,.1f} / lbr")
            cd3.metric("Tanggal Ex-Dividend", div_spec['ex_dividend_date'])
            cd4.metric("Payout Ratio", f"{div_spec['payout_ratio']}%")


# ════════════════════════════════════════════════════════
# TAB SINYAL
# ════════════════════════════════════════════════════════
with tab_signal:
    st.subheader("🚦 Analisis Sinyal Komprehensif (Engine V3)")

    result = generate_signals(selected)

    if not result:
        st.warning("Data tidak cukup untuk menghasilkan sinyal (butuh minimal 30 hari data).")
    else:
        sig_type = result["signal_type"]
        strength = result["strength"]

        colors = {
            "STRONG_BUY": "#00C853", "BUY": "#69F0AE",
            "HOLD": "#FFD740", "HOLD / ILLIQUID": "#FFB300",
            "SELL": "#FF6D00", "STRONG_SELL": "#D50000",
            "AVOID / HIGH_RISK": "#E91E63",
        }
        color = colors.get(sig_type, "#888")
        emoji = {
            "STRONG_BUY": "🟢🟢", "BUY": "🟢", "HOLD": "🟡",
            "HOLD / ILLIQUID": "⚠️", "SELL": "🔴", "STRONG_SELL": "🔴🔴",
            "AVOID / HIGH_RISK": "⛔",
        }.get(sig_type, "ℹ️")

        st.markdown(
            f"""
            <div style="
                background: {color}22; border: 2px solid {color};
                border-radius: 12px; padding: 20px; text-align: center;
            ">
                <h2 style="color: {color}; margin: 0;">{emoji} {sig_type}</h2>
                <p style="color: #aaa; margin: 8px 0 0;">Kekuatan Sinyal: {strength}/100</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ── ACTION PLAN & PANDUAN EKSEKUSI (SEMUA STATUS) ──
        tp = result.get("trade_plan", {})
        if tp:
            tp_badge_color = tp.get("badge_color", color)
            st.markdown(
                f"""
                <div style="background:{tp_badge_color}18; border: 1.5px solid {tp_badge_color};
                            border-radius: 10px; padding: 16px; margin: 16px 0;">
                    <div style="font-size: 1.15em; font-weight: bold; color: {tp_badge_color}; margin-bottom: 8px;">
                        🎯 Action Plan: {tp.get('action', 'RENCANA TRADING')}
                    </div>
                    <div style="margin-bottom: 8px; font-size: 0.95em;">
                        <b>🔹 Sudah Punya Saham:</b> {tp.get('if_holding', '—')}
                    </div>
                    <div style="margin-bottom: 8px; font-size: 0.95em;">
                        <b>🔸 Belum Punya Saham:</b> {tp.get('if_not_holding', '—')}
                    </div>
                    <div style="background: rgba(0,0,0,0.3); border-radius: 6px; padding: 8px 12px; font-size: 0.9em; color: #ddd;">
                        <b>📍 Level Kunci:</b> {tp.get('key_levels', '—')}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # StochRSI sinyal tambahan
        stoch_sig = get_stochrsi_signal(df_raw)
        s_color = {"BUY": "#00C853", "SELL": "#D50000", "HOLD": "#FFD740", "UNKNOWN": "#888"}.get(stoch_sig["signal"], "#888")
        st.markdown(
            f'<div style="background:{s_color}11;border-left:4px solid {s_color};padding:10px 14px;'
            f'border-radius:0 8px 8px 0;margin-top:12px;">'
            f'⚡ <b>StochRSI</b>: <span style="color:{s_color};font-weight:bold;">{stoch_sig["signal"]}</span>'
            f' — {stoch_sig["detail"]}</div>',
            unsafe_allow_html=True,
        )

        st.markdown("### 📋 Alasan Sinyal")
        st.markdown(result["reasons"] or "Tidak ada sinyal kuat saat ini.")

        st.markdown("### 📏 Kekuatan Sinyal")
        st.progress(strength / 100)

        st.markdown("### 🎯 Detail Per Indikator")
        scorecard = result.get("scorecard", {})
        ind_map = {
            "MA Crossover":    ("ma",     "📈"),
            "RSI":             ("rsi",    "📊"),
            "MACD":            ("macd",   "🌊"),
            "Bollinger Bands": ("bb",     "📏"),
            "Volume":          ("volume", "📦"),
        }
        for name, (key, icon) in ind_map.items():
            ind = scorecard.get(key, {})
            sig = ind.get("signal", "—")
            detail = ind.get("detail", "—")
            col_a, col_b = st.columns([1, 4])
            with col_a:
                st.markdown(f"{icon} **{name}**")
            with col_b:
                badge_color = "#00C853" if "BUY" in sig else ("#D50000" if "SELL" in sig else "#888")
                st.markdown(f'<span style="color:{badge_color}">**{sig}**</span> — {detail}', unsafe_allow_html=True)


# ════════════════════════════════════════════════════════
# TAB SCALPING PRO (BARU)
# ════════════════════════════════════════════════════════
with tab_scalp:
    st.subheader("⚡ Scalping Pro Engine & Fast Trading Terminal")
    st.caption("Analisis momentum ultra-cepat, deteksi pullback EMA, fast oscillator, volatilitas BB Squeeze, dan money management ketat khusus day trading / scalping.")

    if df_raw.empty or len(df_raw) < 25:
        st.info("Data belum cukup untuk analisis scalping (butuh minimal 25 hari data).")
    else:
        sc_res = generate_scalping_signals(df_raw)
        snap = sc_res.get("snapshot", {})
        rm = sc_res.get("risk_mgmt", {})
        sig_color = sc_res.get("color", "#888")
        sig_name = sc_res.get("signal", "WAIT")
        sig_emoji = sc_res.get("emoji", "⏸️")
        strength = sc_res.get("strength", 50)
        curr_p = snap.get("price", 0)

        # ── 1. Sinyal Scalping Badge ──────────────────────
        st.markdown(
            f"""
            <div style="
                background: {sig_color}22; border: 2px solid {sig_color};
                border-radius: 12px; padding: 18px; text-align: center; margin-bottom: 15px;
            ">
                <h2 style="color: {sig_color}; margin: 0;">{sig_emoji} {sig_name}</h2>
                <p style="color: #ccc; margin: 6px 0 0; font-size: 1.05em;">
                    Status Tren: <b>{snap.get('trend_status', 'N/A')}</b> &nbsp;|&nbsp;
                    Kekuatan Sinyal Scalp: <b>{strength}/100</b>
                </p>
                <p style="color: #888; font-size: 0.85em; margin: 4px 0 0;">
                    {snap.get('trend_detail', '')}
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Warnings jika ada
        for w in sc_res.get("warnings", []):
            st.warning(w)

        # ── 2. Setup Scalping Terdeteksi ──────────────────
        setups = sc_res.get("setups", [])
        st.markdown("#### 🎯 Setup Scalping Terkonfirmasi (Actionable)")
        if not setups:
            st.info("ℹ️ Belum ada setup scalping terkonfirmasi saat ini. Scalper pro bersabar menunggu momentum breakout atau pullback.")
        else:
            for s in setups:
                stype = s.get("type", "bullish")
                sbg = "#00C85318" if "bullish" in stype else ("#D5000018" if "bearish" in stype else "#FFD74018")
                sbdr = "#00C853" if "bullish" in stype else ("#D50000" if "bearish" in stype else "#FFD740")
                st.markdown(
                    f"""
                    <div style="background:{sbg}; border-left: 5px solid {sbdr}; border-radius: 0 8px 8px 0;
                                padding: 14px 18px; margin-bottom: 12px;">
                        <div style="font-size: 1.1em; font-weight: bold; color: {sbdr};">
                            {s['name']} <span style="font-size:0.8em; color:#aaa;">(Akurasi: {s.get('reliability','High')})</span>
                        </div>
                        <div style="color: #ddd; margin: 6px 0; font-size: 0.95em;">
                            {s['detail']}
                        </div>
                        <div style="display: flex; gap: 20px; font-size: 0.9em; background: rgba(0,0,0,0.3); padding: 8px 12px; border-radius: 6px; margin-top: 8px;">
                            <div><b>🟢 Trigger Entry:</b> {s['entry']}</div>
                            <div><b>🎯 Rencana Keluar:</b> {s['exit']}</div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        st.divider()

        # ── 3. Rencana Eksekusi & Risk Management ─────────
        st.markdown("#### 🛡️ Rencana Eksekusi Scalping (Action Plan & Target Harga)")
        
        is_buy = rm.get("is_buy_bias", True)
        plan_act = rm.get("plan_action", "WAIT")
        act_guide = rm.get("action_guide", "")
        plan_bg = "#00C85318" if is_buy else "#D5000018"
        plan_border = "#00C853" if is_buy else "#D50000"

        plan_html = (
            f'<div style="background:{plan_bg}; border: 1.5px solid {plan_border}; border-radius: 10px; padding: 14px 18px; margin-bottom: 15px;">'
            f'<div style="font-size: 1.1em; font-weight: bold; color: {plan_border};">📋 ARAHAN EKSEKUSI: {plan_act}</div>'
            f'<div style="font-size: 0.95em; color: #eee; margin-top: 6px;">{act_guide}</div>'
            f'</div>'
        )
        st.markdown(plan_html, unsafe_allow_html=True)

        c_rm1, c_rm2, c_rm3, c_rm4 = st.columns(4)

        with c_rm1:
            st.metric("📍 Harga Sekarang", f"Rp {curr_p:,.0f}")
            st.caption(f"ATR(5) Cepat: Rp {rm.get('atr5', 0):,.1f}")

        with c_rm2:
            sl_val = rm.get("stop_loss", 0)
            sl_pct = rm.get("risk_pct", 0)
            if is_buy:
                st.metric("🛑 Stop Loss (Cut Loss)", f"Rp {sl_val:,.0f}", f"-{sl_pct}%", delta_color="inverse")
                st.caption("Batas disiplin buang jika harga turun")
            else:
                st.metric("🛑 Batas Toleransi Exit", f"Rp {sl_val:,.0f}", f"+{sl_pct}% (Max Rugi)")
                st.caption("Jika nekat hold, batas cut loss")

        with c_rm3:
            tp_val = rm.get("take_profit", 0)
            tp_pct = rm.get("reward_pct", 0)
            if is_buy:
                st.metric("🎯 Target Take Profit", f"Rp {tp_val:,.0f}", f"+{tp_pct}%")
                st.caption(f"Target jual untung (RR {rm.get('risk_reward_ratio', '1:1.5')})")
            else:
                st.metric("📉 Target Penurunan Harga", f"Rp {tp_val:,.0f}", f"-{tp_pct}%")
                st.caption("Potensi harga ambrol ke sini")

        with c_rm4:
            sug_lot = rm.get("suggested_lot", 1)
            st.metric("📦 Saran Ukuran Lot", f"{sug_lot:,} Lot")
            st.caption(f"Max Resiko: {rm.get('max_daily_loss', 'Rp 0')}")

        st.divider()

        # ── 4. Indikator Scalping Grid ────────────────────
        st.markdown("#### 📐 Snapshot Indikator Scalping (Fast Momentum)")
        grid_col1, grid_col2, grid_col3, grid_col4 = st.columns(4)

        with grid_col1:
            st.markdown("**Triple EMA (Tren Cepat)**")
            st.write(f"• **EMA 5:** Rp {snap.get('ema5') or 0:,.0f}")
            st.write(f"• **EMA 13:** Rp {snap.get('ema13') or 0:,.0f}")
            st.write(f"• **EMA 21:** Rp {snap.get('ema21') or 0:,.0f}")
            st.caption("EMA5 di atas EMA13 & 21 = Uptrend akseleratif.")

        with grid_col2:
            st.markdown("**Fast Oscillator**")
            r5 = snap.get('rsi5')
            st.write(f"• **RSI (5):** {r5 if r5 else '—'}")
            st.write(f"• **Stoch K:** {snap.get('stoch_k') or '—'}")
            st.write(f"• **Stoch D:** {snap.get('stoch_d') or '—'}")
            st.caption("<20 = Oversold cepat | >80 = Overbought.")

        with grid_col3:
            st.markdown("**Volatilitas & Squeeze**")
            bbw = snap.get('bb_width')
            is_sq = snap.get('is_squeeze')
            st.write(f"• **BB Width:** {bbw:.2f}%" if bbw else "• **BB Width:** —")
            st.write(f"• **Status Squeeze:** {'🔥 SQUEEZE (Kompresi)' if is_sq else '⚪ Normal'}")
            st.write(f"• **Williams %R:** {snap.get('williams_r') or '—'}")
            st.caption("Squeeze = Bersiap ledakan arah baru.")

        with grid_col4:
            st.markdown("**Volume & Kekuatan Tren**")
            v_rat = snap.get('vol_ratio', 1.0)
            v_spk = snap.get('vol_spike', False)
            adx_val = snap.get('adx')
            st.write(f"• **Volume vs MA20:** {v_rat:.2f}x")
            st.write(f"• **Volume Spike:** {'⚡ LONJAKAN BESAR' if v_spk else '⚪ Normal'}")
            st.write(f"• **ADX (14):** {adx_val if adx_val else '—'}")
            st.caption("ADX > 25 = Tren valid untuk scalping.")

        st.divider()

        # ── 5. Grafik Interaktif Scalping ─────────────────
        st.markdown("#### 📉 Grafik Scalping: Candlestick + Triple EMA + Fast Stochastic")
        df_sc = sc_res.get("df")
        if df_sc is not None and not df_sc.empty:
            df_chart = df_sc.tail(45).reset_index(drop=True)

            fig_sc = make_subplots(
                rows=2, cols=1, shared_xaxes=True,
                vertical_spacing=0.06, row_heights=[0.7, 0.3],
                subplot_titles=("Candlestick + EMA(5, 13, 21) + Bollinger Bands", "Fast Stochastic (5, 3, 3) + RSI(5)")
            )

            # Row 1: Candlestick + EMA5/13/21 + BB
            fig_sc.add_trace(go.Candlestick(
                x=df_chart["date"], open=df_chart["open"], high=df_chart["high"],
                low=df_chart["low"], close=df_chart["close"], name="OHLC",
                increasing_line_color="#00C853", decreasing_line_color="#D50000"
            ), row=1, col=1)

            fig_sc.add_trace(go.Scatter(
                x=df_chart["date"], y=df_chart["EMA5"], name="EMA 5 (Trigger)",
                line=dict(color="#00E5FF", width=1.5)
            ), row=1, col=1)

            fig_sc.add_trace(go.Scatter(
                x=df_chart["date"], y=df_chart["EMA13"], name="EMA 13 (Pullback)",
                line=dict(color="#FF9100", width=1.5)
            ), row=1, col=1)

            fig_sc.add_trace(go.Scatter(
                x=df_chart["date"], y=df_chart["EMA21"], name="EMA 21 (Baseline)",
                line=dict(color="#D500F9", width=1.5)
            ), row=1, col=1)

            fig_sc.add_trace(go.Scatter(
                x=df_chart["date"], y=df_chart["BB_Upper"], name="BB Upper",
                line=dict(color="rgba(255,255,255,0.3)", dash="dot")
            ), row=1, col=1)

            fig_sc.add_trace(go.Scatter(
                x=df_chart["date"], y=df_chart["BB_Lower"], name="BB Lower",
                line=dict(color="rgba(255,255,255,0.3)", dash="dot"),
                fill="tonexty", fillcolor="rgba(255,255,255,0.02)"
            ), row=1, col=1)

            # Row 2: Fast Stochastic + RSI5
            fig_sc.add_trace(go.Scatter(
                x=df_chart["date"], y=df_chart["Stoch_K"], name="Stoch %K",
                line=dict(color="#00E676", width=1.5)
            ), row=2, col=1)

            fig_sc.add_trace(go.Scatter(
                x=df_chart["date"], y=df_chart["Stoch_D"], name="Stoch %D",
                line=dict(color="#FF5252", width=1.5, dash="dot")
            ), row=2, col=1)

            fig_sc.add_trace(go.Scatter(
                x=df_chart["date"], y=df_chart["RSI5"], name="RSI(5)",
                line=dict(color="#FFD740", width=1)
            ), row=2, col=1)

            fig_sc.add_hline(y=80, line=dict(color="red", dash="dash", width=1), row=2, col=1)
            fig_sc.add_hline(y=20, line=dict(color="green", dash="dash", width=1), row=2, col=1)

            fig_sc.update_layout(
                template="plotly_dark", height=500,
                margin=dict(l=0, r=0, t=30, b=0),
                xaxis_rangeslider_visible=False,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig_sc, use_container_width=True)

        st.divider()

        # ── 6. Panduan SOP & Aturan Emas Scalper Pro ───────
        st.markdown("#### 📘 Standar Operasional Prosedur (SOP) Scalper Profesional di BEI")
        col_sop1, col_sop2 = st.columns(2)

        with col_sop1:
            st.markdown("""
            **⏰ 1. Golden Hours (Jam Keramat Scalping di BEI):**
            * **09:00 - 09:30 WIB (Sesi Pembukaan):**
              Volatilitas tertinggi! Momentum HAKA/HAKI paling deras. Reaksi pasar terhadap berita semalam.
            * **10:00 - 13:30 WIB (Dead Zone / Zona Sepi):**
              **BAHAYA!** Volume transaksi mereda, spread bid-offer melebar. Rawan jebakan *whipsaw*. Trader pro biasanya istirahat di jam ini.
            * **14:00 - 15:30 WIB (Sesi Penutupan):**
              Lonjakan volume kedua. Penentuan posisi penutupan (*closing run*). Waktu ideal mengamankan profit intraday.
            
            **⚔️ 2. Teknik Eksekusi Beli & Jual (Order Execution):**
            * **Kapan HAKA (Hajar Kanan):** Hanya saat ada breakout resistance dengan volume spike > 2x, atau konfirmasi stochastic golden cross di area oversold.
            * **Kapan Antri di Bid:** Saat terjadi *Pullback to EMA5/13* di tengah uptrend yang sehat.
            * **Partial Profit Taking:** Amankan 50% lot saat profit mencapai target pertama (+1.5% s/d +2.5%), lalu geser Stop Loss sisa lot ke harga modal (*Breakeven Stop*).
            """)

        with col_sop2:
            st.markdown("""
            **🧠 3. Golden Rules Psikologi & Risk Management Pro:**
            1. **Stop Loss adalah Harga Mati:** Scalper yang sukses bukan yang selalu benar, tapi yang **kerugiannya selalu kecil**. Jangan pernah tawar-menawar Stop Loss!
            2. **Dilarang Averaging Down:** Jika harga berlawanan dengan analisismu, segera keluar. Jangan pernah menambah posisi rugi saat scalping.
            3. **Jangan Berubah Jadi 'Investor Nyangkut':** Scalping adalah transaksi menit/jam. Jika salah arah, cut loss hari itu juga. Jangan di-hold semalam dengan harapan esok hari naik!
            4. **Fee-Conscious:** Perhitungkan total fee beli (±0.15%) + jual (±0.25%) = total ±0.40%. Target profit scalping harus di atas 1.0% agar hasil bersih tetap menguntungkan.
            5. **Maksimal 3 Transaksi Rugi per Hari:** Jika sudah 3x berturut-turut kena Stop Loss, matikan layar! Pasar sedang tidak cocok dengan gaya tradingmu hari ini.
            """)


# ════════════════════════════════════════════════════════
# TAB PROYEKSI BESOK (BARU)
# ════════════════════════════════════════════════════════
with tab_forecast:
    st.subheader(f"🔮 Proyeksi & Probabilitas Arah Esok Hari: {selected}")
    st.caption("Model kuantitatif prediktif berbasis Closing Price Action, Tom DeMark Range, Fast Momentum, dan Volatilitas ATR untuk memprediksi arah sesi perdagangan berikutnya.")

    if df_raw.empty or len(df_raw) < 25:
        st.info("Data belum cukup untuk kalkulasi proyeksi besok (minimal butuh 25 hari bursa).")
    else:
        fc = calculate_next_day_forecast(df_raw)
        curr_p = fc.get("current_price", 0)
        p_up = fc.get("prob_up", 50)
        p_down = fc.get("prob_down", 50)
        b_color = fc.get("bias_color", "#FFD740")
        b_label = fc.get("bias_label", "KONSOLIDASI")
        b_emoji = fc.get("bias_emoji", "⚖️")
        pivot_val = fc.get("pivot", curr_p)

        # ── 1. Probabilitas Arah Banner ────────────────────
        st.markdown(
            f"""
            <div style="background:{b_color}18; border: 2px solid {b_color}; border-radius: 12px;
                        padding: 20px; text-align: center; margin-bottom: 20px;">
                <div style="font-size: 0.9em; color: #bbb; text-transform: uppercase; letter-spacing: 1px;">
                    Estimasi Arah Sesi Besok (T+1)
                </div>
                <h2 style="color: {b_color}; margin: 8px 0;">{b_emoji} {b_label}</h2>
                <div style="font-size: 1.15em; color: #eee; margin-top: 6px;">
                    Peluang Naik: <b style="color: #00C853;">{p_up}%</b> &nbsp;|&nbsp; 
                    Peluang Turun: <b style="color: #D50000;">{p_down}%</b> &nbsp;
                    <span style="font-size: 0.85em; color: #aaa;">(Tingkat Keyakinan: {fc.get('confidence', 'Moderat')})</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Visual Probability Bar
        st.write(f"**Distribusi Probabilitas:** 🟢 Naik {p_up}% vs 🔴 Turun {p_down}%")
        st.progress(p_up / 100.0)

        st.divider()

        # ── 2. Kartu Level & Rentang Harga Besok ───────────
        st.markdown("#### 🎯 Level Penentu & Estimasi Rentang Harga Esok Hari")
        c_fc1, c_fc2, c_fc3, c_fc4 = st.columns(4)

        with c_fc1:
            st.metric("📍 Harga Terakhir", f"Rp {curr_p:,.0f}")
            st.caption("Harga penutupan sesi terakhir")

        with c_fc2:
            st.metric("🔑 Level Penentu (Pivot)", f"Rp {pivot_val:,.0f}")
            st.caption("Level kunci pembukaan besok pagi")

        with c_fc3:
            p_max = fc.get("proj_max", curr_p)
            up_pct = fc.get("upside_pct", 0)
            st.metric("🟢 Target Batas Atas", f"Rp {p_max:,.0f}", f"+{up_pct}%")
            st.caption(f"DeMark & ATR High: Rp {fc.get('demark_high', 0):,.0f}")

        with c_fc4:
            p_min = fc.get("proj_min", curr_p)
            down_pct = fc.get("downside_pct", 0)
            st.metric("🔴 Target Batas Bawah", f"Rp {p_min:,.0f}", f"-{down_pct}%", delta_color="inverse")
            st.caption(f"DeMark & ATR Low: Rp {fc.get('demark_low', 0):,.0f}")

        st.divider()

        # ── 3. Rekomendasi Jam 09:00 WIB Besok Pagi ───────
        st.markdown("#### ⏰ Rencana Eksekusi Pre-Opening & Pukul 09:00 WIB")
        st.info(f"💡 **Panduan Besok Pagi:** {fc.get('action_plan_tomorrow', '')}")

        st.divider()

        # ── 4. Dua Skenario Taktis Besok (Bullish vs Bearish)
        st.markdown("#### ⚔️ Dua Skenario Taktis Pergerakan Harga Besok")
        sc_col1, sc_col2 = st.columns(2)

        sc_bull = fc.get("scenario_bullish", {})
        sc_bear = fc.get("scenario_bearish", {})

        with sc_col1:
            st.markdown(
                f"""
                <div style="background: rgba(0, 200, 83, 0.08); border-left: 5px solid #00C853;
                            border-radius: 0 10px 10px 0; padding: 16px 20px; height: 100%;">
                    <h4 style="color: #00C853; margin: 0 0 10px 0;">{sc_bull.get('title', '')}</h4>
                    <p style="margin: 6px 0; font-size: 0.95em;">
                        <b>⚡ Syarat Terjadi:</b> {sc_bull.get('trigger', '')}
                    </p>
                    <p style="margin: 6px 0; font-size: 0.95em;">
                        <b>🎯 Target Penguatan:</b> Target 1: <b>{sc_bull.get('target_1', '')}</b> | Target 2: <b>{sc_bull.get('target_2', '')}</b>
                    </p>
                    <div style="background: rgba(0,0,0,0.3); padding: 10px 14px; border-radius: 6px; margin-top: 10px; font-size: 0.9em; color: #ddd;">
                        <b>📋 Aksi:</b> {sc_bull.get('action', '')}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with sc_col2:
            st.markdown(
                f"""
                <div style="background: rgba(213, 0, 0, 0.08); border-left: 5px solid #D50000;
                            border-radius: 0 10px 10px 0; padding: 16px 20px; height: 100%;">
                    <h4 style="color: #D50000; margin: 0 0 10px 0;">{sc_bear.get('title', '')}</h4>
                    <p style="margin: 6px 0; font-size: 0.95em;">
                        <b>⚡ Syarat Terjadi:</b> {sc_bear.get('trigger', '')}
                    </p>
                    <p style="margin: 6px 0; font-size: 0.95em;">
                        <b>📉 Target Penurunan:</b> Support 1: <b>{sc_bear.get('support_1', '')}</b> | Support 2: <b>{sc_bear.get('support_2', '')}</b>
                    </p>
                    <div style="background: rgba(0,0,0,0.3); padding: 10px 14px; border-radius: 6px; margin-top: 10px; font-size: 0.9em; color: #ddd;">
                        <b>📋 Aksi:</b> {sc_bear.get('action', '')}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.divider()

        # ── 5. Faktor Pendukung Probabilitas ───────────────
        st.markdown("#### 🔬 Faktor Analisis Kuantitatif yang Ditemukan")
        f_col1, f_col2 = st.columns(2)

        bull_reasons = fc.get("reasons_bullish", [])
        bear_reasons = fc.get("reasons_bearish", [])

        with f_col1:
            st.markdown("**🟢 Faktor Penggerak Naik (Bullish Factors):**")
            if not bull_reasons:
                st.caption("Tidak ada faktor bullish signifikan saat ini.")
            else:
                for r in bull_reasons:
                    st.write(f"• {r}")

        with f_col2:
            st.markdown("**🔴 Faktor Penekan Turun (Bearish Factors):**")
            if not bear_reasons:
                st.caption("Tidak ada faktor bearish signifikan saat ini.")
            else:
                for r in bear_reasons:
                    st.write(f"• {r}")

        st.divider()

        # ── 6. Kalkulator Money Management & Fee Broker BEI (Dual Mode: Portofolio vs Simulasi)
        with st.expander("🧮 Kalkulator Position Sizing, Modal & Fee Broker BEI (Interaktif)", expanded=True):
            # Cek apakah saham ini ada di portofolio user
            holdings = get_portfolio_summary()
            current_holding = next((h for h in holdings if h["ticker"] == selected), None)

            if current_holding:
                st.markdown(
                    f"""
                    <div style="background: rgba(0, 200, 83, 0.12); border-left: 4px solid #00C853; border-radius: 0 8px 8px 0;
                                padding: 10px 14px; margin-bottom: 12px; font-size: 0.95em;">
                        📦 <b>Saham Terdeteksi di Portofoliomu:</b> Kamu sedang memiliki <b>{current_holding['net_lot']:,} Lot</b> 
                        dengan modal rata-rata <b>Rp {current_holding['avg_price']:,.0f}</b> / lembar.
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                calc_mode = st.radio(
                    "Pilih Mode Kalkulator:",
                    ["📦 Posisi Portofolio Saya (Rencana Jual / Exit)", "🎯 Simulasi Beli Baru"],
                    horizontal=True,
                    key="calc_mode_radio"
                )
            else:
                calc_mode = "🎯 Simulasi Beli Baru"

            pos = None
            h_res = None

            if calc_mode == "📦 Posisi Portofolio Saya (Rencana Jual / Exit)":
                st.markdown("##### 📦 Kalkulasi Realisasi Posisi Portofolio Saya")
                c_p1, c_p2, c_p3 = st.columns(3)
                with c_p1:
                    hold_lot = st.number_input(
                        "Jumlah Lot yang Ingin Dijual",
                        min_value=1, max_value=max(1, int(current_holding["net_lot"])),
                        value=max(1, int(current_holding["net_lot"])), step=1,
                        help="Kamu bisa mengurangi lot jika hanya ingin partial take profit."
                    )
                with c_p2:
                    default_tp = float(fc.get("r1", curr_p * 1.08))
                    hold_tp = st.number_input("Target Harga Take Profit (Rp)", min_value=1.0, value=default_tp, step=1.0)
                with c_p3:
                    default_sl = max(1.0, float(fc.get("s1", curr_p * 0.95)))
                    hold_sl = st.number_input("Batas Harga Cut Loss / SL (Rp)", min_value=1.0, value=default_sl, step=1.0)

                h_res = calculate_holding_exit(
                    net_lot=hold_lot,
                    avg_price=float(current_holding["avg_price"]),
                    current_price=float(curr_p),
                    target_profit=hold_tp,
                    stop_loss=hold_sl,
                )

                if h_res:
                    st.markdown("---")
                    st.markdown("##### 📊 Proyeksi Hasil Realisasi Portofolio")
                    r_h1, r_h2, r_h3, r_h4 = st.columns(4)
                    with r_h1:
                        st.metric("💵 Modal Beli Awal", f"Rp {h_res['total_cost']:,.0f}")
                        st.caption(f"{hold_lot:,} Lot @ Rp {current_holding['avg_price']:,.0f}")
                    with r_h2:
                        float_delta = f"{h_res['unrealized_pnl_pct']:+.2f}%"
                        st.metric("📍 Nilai Saham Saat Ini", f"Rp {h_res['current_net']:,.0f}", float_delta)
                        st.caption(f"Floating P/L: Rp {h_res['unrealized_pnl_idr']:+,.0f}")
                    with r_h3:
                        tp_delta = f"{h_res['tp_profit_pct']:+.2f}%"
                        st.metric("🎯 Untung Bersih di TP", f"Rp {h_res['tp_profit_idr']:+,.0f}", tp_delta)
                        st.caption(f"Jual di Rp {hold_tp:,.0f} (Net fee 0.25%)")
                    with r_h4:
                        sl_delta = f"{h_res['sl_pnl_pct']:+.2f}%"
                        st.metric("🛑 Hasil Bersih di SL", f"Rp {h_res['sl_pnl_idr']:+,.0f}", sl_delta, delta_color="inverse")
                        st.caption(f"Jual di Rp {hold_sl:,.0f} (Net fee 0.25%)")

                    st.info(f"💡 **Harga Impas Modalmu (BEP): Rp {h_res['bep_tick']:,.0f}**. Jika menjual di atas harga ini, transaksimu sudah menghasilkan laba bersih setelah dipotong seluruh fee broker!")

            else:
                st.markdown("##### ⚙️ Parameter Modal & Risiko (Simulasi Beli Baru)")
                c_calc1, c_calc2, c_calc3 = st.columns(3)
                with c_calc1:
                    calc_capital = st.number_input(
                        "Alokasi Modal Trading (Rp)",
                        min_value=500_000, max_value=1_000_000_000,
                        value=10_000_000, step=1_000_000, format="%d",
                        key="calc_cap"
                    )
                with c_calc2:
                    calc_risk_pct = st.slider(
                        "Maksimal Risiko per Transaksi (% Modal)",
                        min_value=0.5, max_value=3.0, value=1.5, step=0.1,
                        help="Trader pro umumnya membatasi risiko maksimal 1% - 2% dari total modal per transaksi.",
                        key="calc_risk"
                    )
                with c_calc3:
                    calc_entry = st.number_input("Rencana Harga Beli (Rp)", min_value=1.0, value=float(curr_p), step=1.0, key="calc_ent")

                c_calc4, c_calc5, c_calc6 = st.columns(3)
                with c_calc4:
                    default_sl = max(1.0, float(fc.get("s1", curr_p * 0.95)))
                    calc_sl = st.number_input("Batas Cut Loss / SL (Rp)", min_value=1.0, value=default_sl, step=1.0, key="calc_sl")
                with c_calc5:
                    default_tp = float(fc.get("r1", curr_p * 1.08))
                    calc_tp = st.number_input("Target Take Profit (Rp)", min_value=1.0, value=default_tp, step=1.0, key="calc_tp")
                with c_calc6:
                    st.caption("Fee Broker BEI Default: Beli 0.15% | Jual 0.25% (Include PPh & Levy)")

                pos = calculate_trade_position(
                    capital=calc_capital,
                    risk_pct=calc_risk_pct,
                    entry_price=calc_entry,
                    stop_loss=calc_sl,
                    target_profit=calc_tp,
                )

                if pos:
                    st.markdown("---")
                    st.markdown("##### 📊 Hasil Kalkulasi Order Profesional")
                    r_c1, r_c2, r_c3, r_c4 = st.columns(4)

                    with r_c1:
                        st.metric("📦 Ukuran Posisi Ideal", f"{pos['recommended_lot']:,} Lot")
                        st.caption(f"Total: {pos['total_shares']:,} lembar saham")
                    with r_c2:
                        st.metric("💵 Total Modal Beli (Net Fee)", f"Rp {pos['net_buy_cost']:,.0f}")
                        st.caption(f"Fee Beli: Rp {pos['total_fee_buy']:,.0f}")
                    with r_c3:
                        st.metric("🎯 Untung Bersih (Net TP)", f"Rp {pos['net_profit_idr']:,.0f}", f"+{pos['net_profit_pct']}%")
                        st.caption(f"Setelah dipotong seluruh fee broker")
                    with r_c4:
                        st.metric("🛑 Maksimal Rugi Bersih (Net SL)", f"Rp {pos['net_loss_idr']:,.0f}", f"-{pos['net_loss_pct']}%", delta_color="inverse")
                        st.caption(f"Risk:Reward Bersih: 1 : {pos['net_rr_ratio']}")

                    st.info(f"💡 **Harga Impas (Breakeven Point / BEP): Rp {pos['bep_tick']:,.0f}**. Kamu baru mulai profit jika menjual di atas harga ini!")

        # ── 7. Salin Trading Plan ke WhatsApp / Telegram
        with st.expander("📋 Salin Ringkasan Trading Plan (Format WhatsApp / Telegram)", expanded=False):
            st.caption("Klik tombol salin di pojok kanan kotak teks di bawah untuk langsung membagikan atau menyimpan trading plan ke HP:")
            
            # Tentukan nilai untuk WA plan berdasarkan mode aktif
            if h_res:
                wa_entry = float(current_holding["avg_price"])
                wa_sl = hold_sl
                wa_tp = hold_tp
                wa_lot = hold_lot
                wa_profit = h_res.get("tp_profit_idr")
                wa_loss = h_res.get("sl_pnl_idr")
            elif pos:
                wa_entry = calc_entry
                wa_sl = calc_sl
                wa_tp = calc_tp
                wa_lot = pos.get("recommended_lot")
                wa_profit = pos.get("net_profit_idr")
                wa_loss = pos.get("net_loss_idr")
            else:
                wa_entry = curr_p
                wa_sl = fc.get("s1", curr_p * 0.95)
                wa_tp = fc.get("r1", curr_p * 1.08)
                wa_lot = None
                wa_profit = None
                wa_loss = None

            wa_text = generate_whatsapp_trading_plan(
                ticker=selected,
                company_name=stock_info.get("name", ""),
                current_price=curr_p,
                entry_price=wa_entry,
                stop_loss=wa_sl,
                target_1=wa_tp,
                target_2=fc.get("r2"),
                pivot=pivot_val,
                bias_label=b_label,
                prob_up=p_up,
                recommended_lot=wa_lot,
                net_profit_idr=wa_profit,
                net_loss_idr=wa_loss,
                note=fc.get("action_plan_tomorrow", "")
            )
            st.code(wa_text, language="markdown")


# ════════════════════════════════════════════════════════
# TAB POLA CANDLESTICK (BARU)
# ════════════════════════════════════════════════════════
with tab_pattern:
    st.subheader("🕯️ Deteksi Pola Candlestick Otomatis")
    st.caption("Pola berbasis analisis formasi candle 3-5 hari terakhir — dipakai trader profesional untuk konfirmasi entry/exit.")

    if df_raw.empty:
        st.info("Belum ada data harga. Klik Refresh di sidebar.")
    else:
        patterns = detect_patterns(df_raw)

        if not patterns:
            st.info("ℹ️ Tidak ada pola signifikan terdeteksi dalam 100 hari terakhir.")
        else:
            # Pola terbaru (5 teratas)
            recent = patterns[:5]
            st.markdown("#### 🔍 5 Pola Terbaru Terdeteksi")
            for p in recent:
                ptype = p["type"]
                bg = "#00C85322" if ptype == "bullish" else ("#D5000022" if ptype == "bearish" else "#44444422")
                border = "#00C853" if ptype == "bullish" else ("#D50000" if ptype == "bearish" else "#888")
                rel_icon = "🔴" if p["reliability"] == "Low" else ("🟡" if p["reliability"] == "Medium" else "🟢")
                date_str = str(p["date"])[:10]
                st.markdown(
                    f'<div style="background:{bg};border-left:4px solid {border};'
                    f'padding:10px 16px;border-radius:0 8px 8px 0;margin-bottom:8px;">'
                    f'<b>{p["pattern"]}</b> &nbsp;|&nbsp; Tanggal: <b>{date_str}</b> '
                    f'&nbsp;|&nbsp; Harga: Rp {p["close"]:,.0f} '
                    f'&nbsp;|&nbsp; Akurasi: {rel_icon} {p["reliability"]}</div>',
                    unsafe_allow_html=True,
                )

            # Ringkasan bias
            bull_count = sum(1 for p in patterns if p["type"] == "bullish")
            bear_count = sum(1 for p in patterns if p["type"] == "bearish")
            st.divider()
            st.markdown("#### 📊 Ringkasan Bias Pola")
            c1, c2, c3 = st.columns(3)
            c1.metric("🟢 Bullish", bull_count, "Pola reversal naik")
            c2.metric("🔴 Bearish", bear_count, "Pola reversal turun")
            c3.metric("🏆 Bias Dominan", "BULLISH 📈" if bull_count > bear_count else ("BEARISH 📉" if bear_count > bull_count else "NETRAL ⚖️"))

        st.divider()
        st.markdown("#### 📘 Panduan Membaca Pola Candlestick")
        guide_data = {
            "Pola": [
                "Hammer 🔨", "Shooting Star 💫", "Bullish Engulfing 🟢📦",
                "Bearish Engulfing 🔴📦", "Morning Star ⭐", "Evening Star 🌟",
                "Dragonfly Doji 🪁", "Gravestone Doji 🪦", "Doji ✚",
                "Bullish Harami 🤰", "Bearish Harami 🤰"
            ],
            "Bias": [
                "🟢 Bullish", "🔴 Bearish", "🟢 Bullish",
                "🔴 Bearish", "🟢 Bullish", "🔴 Bearish",
                "🟢 Bullish", "🔴 Bearish", "⚪ Netral",
                "🟢 Bullish", "🔴 Bearish"
            ],
            "Akurasi": ["High", "High", "High", "High", "High", "High", "Medium", "Medium", "Low", "Medium", "Medium"],
            "Penjelasan Singkat": [
                "Ekor bawah panjang = tekanan jual habis, pembeli mulai masuk",
                "Ekor atas panjang = harga tolak kenaikan, penjual dominan",
                "Candle hijau besar 'menelan' merah kemarin = momentum berbalik naik",
                "Candle merah besar 'menelan' hijau kemarin = momentum berbalik turun",
                "3 candle: merah besar → bintang kecil → hijau besar = pembalikan kuat",
                "3 candle: hijau besar → bintang kecil → merah besar = pembalikan turun",
                "Ekor bawah panjang tanpa ekor atas = pembalikan bull potensial",
                "Ekor atas panjang tanpa ekor bawah = pembalikan bear potensial",
                "Badan sangat kecil = ketidakpastian, pasar ragu-ragu",
                "Candle kecil 'di dalam' candle besar bearish kemarin = tekanan jual melemah",
                "Candle kecil 'di dalam' candle besar bullish kemarin = tekanan beli melemah",
            ]
        }
        st.dataframe(pd.DataFrame(guide_data), use_container_width=True, hide_index=True)


# ════════════════════════════════════════════════════════
# TAB SUPPORT & RESISTANCE (BARU)
# ════════════════════════════════════════════════════════
with tab_sr:
    st.subheader("📍 Level Support & Resistance Otomatis")
    st.caption("Dihitung dari Pivot Point klasik + Swing High/Low historis. Level ini adalah zona 'jual-beli alami' yang sering dijadikan acuan trader institusi.")

    if df_raw.empty:
        st.info("Belum ada data harga. Klik Refresh di sidebar.")
    else:
        lvl = find_support_resistance(df_raw)

        if not lvl:
            st.warning("Data tidak cukup untuk menghitung level (butuh minimal 50 hari data).")
        else:
            current = lvl["current"]

            # ── Kartu ringkasan ───────────────────────────
            st.markdown("#### 🎯 Level Kritis Terdekat")
            c1, c2, c3 = st.columns(3)
            c1.metric(
                "📍 Harga Sekarang",
                f"Rp {current:,.0f}",
            )
            c2.metric(
                "⬆️ Resistance Terdekat",
                f"Rp {lvl['nearest_resistance']:,.0f}",
                f"+{lvl['upside_to_resistance']}% dari harga",
            )
            c3.metric(
                "⬇️ Support Terdekat",
                f"Rp {lvl['nearest_support']:,.0f}",
                f"-{lvl['downside_to_support']}% dari harga",
                delta_color="inverse",
            )

            st.divider()

            # ── Pivot Points ──────────────────────────────
            st.markdown("#### 🔵 Pivot Point Klasik (berdasarkan candle kemarin)")
            pp_cols = st.columns(7)
            pp_labels = ["S3", "S2", "S1", "Pivot", "R1", "R2", "R3"]
            pp_values = [lvl["s3"], lvl["s2"], lvl["s1"], lvl["pivot"], lvl["r1"], lvl["r2"], lvl["r3"]]
            pp_colors = ["#D50000", "#E53935", "#EF5350", "#FFD740", "#43A047", "#2E7D32", "#1B5E20"]
            for col, label, val, color in zip(pp_cols, pp_labels, pp_values, pp_colors):
                marker = "← HARGA SEKARANG" if abs(val - current) / max(current, 1) < 0.02 else ""
                col.markdown(
                    f'<div style="text-align:center;background:{color}33;border:1px solid {color};'
                    f'border-radius:8px;padding:8px;">'
                    f'<div style="color:{color};font-weight:bold;">{label}</div>'
                    f'<div style="font-size:13px;">Rp {val:,.0f}</div></div>',
                    unsafe_allow_html=True,
                )

            st.divider()

            # ── Grafik S/R ─────────────────────────────────
            st.markdown("#### 📉 Grafik Harga + Level S/R (3 Bulan)")
            df_3m = df_raw.tail(63).reset_index(drop=True)
            fig_sr = go.Figure()
            fig_sr.add_trace(go.Candlestick(
                x=df_3m["date"], open=df_3m["open"], high=df_3m["high"],
                low=df_3m["low"], close=df_3m["close"], name="OHLC",
                increasing_line_color="#00C853", decreasing_line_color="#D50000",
            ))

            # Plot level swing supports
            for s in lvl.get("swing_supports", [])[:3]:
                fig_sr.add_hline(y=s, line=dict(color="#EF5350", dash="dash", width=1),
                                 annotation_text=f"Support Rp {s:,.0f}", annotation_position="bottom right")

            # Plot level swing resistances
            for r in lvl.get("swing_resistances", [])[:3]:
                fig_sr.add_hline(y=r, line=dict(color="#43A047", dash="dash", width=1),
                                 annotation_text=f"Resistance Rp {r:,.0f}", annotation_position="top right")

            # Pivot
            fig_sr.add_hline(y=lvl["pivot"], line=dict(color="#FFD740", dash="dot", width=1.5),
                             annotation_text=f"Pivot {lvl['pivot']:,.0f}")

            fig_sr.update_layout(
                template="plotly_dark", height=400,
                margin=dict(l=0, r=0, t=0, b=0),
                xaxis_rangeslider_visible=False,
            )
            st.plotly_chart(fig_sr, use_container_width=True)

            # ── Tabel Semua Level ─────────────────────────
            st.markdown("#### 📋 Semua Level")
            level_rows = []
            for label, val in [
                ("R3", lvl["r3"]), ("R2", lvl["r2"]), ("R1", lvl["r1"]),
                ("Pivot", lvl["pivot"]),
                ("S1", lvl["s1"]), ("S2", lvl["s2"]), ("S3", lvl["s3"]),
            ]:
                dist_pct = round((val - current) / max(current, 1) * 100, 1)
                role = "Resistance 🔴" if val > current else ("Support 🟢" if val < current else "Pivot 🟡")
                level_rows.append({
                    "Level": label, "Tipe": role,
                    "Harga (Rp)": f"{val:,.0f}",
                    "Jarak dari Harga": f"{dist_pct:+.1f}%",
                })
            st.dataframe(pd.DataFrame(level_rows), use_container_width=True, hide_index=True)


st.markdown("---")

with st.expander("📚 Glosarium Indikator Teknikal & Fundamental (Research)", expanded=False):
    st.markdown("""
    Berikut rangkuman dan panduan membaca seluruh metrik yang ada di halaman Research:

    ### 📈 1. Indikator Teknikal
    * **RSI (Relative Strength Index)**: Indikator pengukur kecepatan & perubahan harga (skala 0-100).
      * `< 30 (Oversold)`: Harga sudah turun tajam, rawan terjadi pantulan teknikal.
      * `> 70 (Overbought)`: Harga sudah naik sangat tinggi, waspada aksi ambil untung.
    * **StochRSI (Stochastic RSI)**: RSI dari RSI — lebih sensitif dan lebih cepat mendeteksi pembalikan arah daripada RSI biasa.
      * `K < 20`: Zona oversold yang kuat (area akumulasi ideal).
      * `K > 80`: Zona overbought yang kuat (area distribusi/jual).
      * **Golden Cross StochRSI**: Garis K memotong naik garis D di zona oversold = sinyal beli paling kuat.
      * **Death Cross StochRSI**: Garis K memotong turun garis D di zona overbought = sinyal jual kuat.
    * **MA20 & MA50 (Moving Average)**: Rata-rata harga 20 hari (bulanan) dan 50 hari (kuartalan).
      * **Golden Cross**: MA20 memotong naik MA50 = sinyal bullish jangka menengah.
      * **Death Cross**: MA20 memotong turun MA50 = sinyal bearish.
    * **MA200 (Super Trend)**: Garis tren utama 1 tahun. Saham di atas MA200 = fase bullish jangka panjang.
    * **MACD**: Pengukur momentum tren. Histogram hijau positif = momentum naik dominan.
    * **Bollinger Bands**: Harga yang menembus BB Lower cenderung memantul ke BB Mid.
    * **ATR (Average True Range)**: Volatilitas harian dalam rupiah. Dipakai hitung stop loss.
    * **Pivot Point**: Level kunci harian yang dihitung dari High+Low+Close hari sebelumnya.
      * **R1, R2, R3**: Level Resistance (rintangan di atas harga saat ini).
      * **S1, S2, S3**: Level Support (lantai di bawah harga saat ini).
    * **Pola Candlestick**: Formasi satu/beberapa candle yang mengindikasikan pembalikan atau kelanjutan tren.

    ---

    ### 📊 2. Rasio Fundamental
    * **P/E Ratio**: Harga vs Laba — `< 15x` murah, `15-30x` wajar, `> 30x` mahal.
    * **P/B Ratio**: Harga vs Nilai buku — `< 1x` murah, `1-3x` normal.
    * **ROE**: Kemampuan mencetak laba dari modal — `> 20%` sangat bagus.
    * **DER**: Rasio utang/modal — `< 1x` aman, `> 2x` berisiko.
    * **Dividend Yield**: Imbal hasil dividen — `> 3%` menarik.
    * **Market Cap**: Total nilai pasar seluruh saham perusahaan.

    ---

    ### ⚡ 3. Istilah & Indikator Scalping Pro
    * **Scalping**: Gaya trading ultra-cepat hitungan menit hingga jam untuk mengamankan profit kecil berulang kali (1% s/d 3%) dengan risiko sekecil mungkin.
    * **Triple EMA (EMA 5, 13, 21)**: Kombinasi exponential moving average yang sangat sensitif:
      * `EMA 5`: Garis pemicu (trigger line) gerak harga tercepat.
      * `EMA 13`: Garis pantulan dinamis (dynamic pullback support).
      * `EMA 21`: Garis batas tren mikro (baseline). Selama EMA5 > EMA13 > EMA21, momentum scalp naik sangat aman.
    * **RSI (5) Ultra-Fast**: RSI dengan periode pendek (5 candle) untuk mendeteksi titik jenuh ekstrem intraday (<20 oversold, >80 overbought).
    * **Fast Stochastic (5, 3, 3)**: Pengukur timing entry paling tajam. Golden cross di bawah 20/30 adalah sinyal masuk paling diincar scalper.
    * **Bollinger Band Squeeze**: Kondisi pita Bollinger Bands menyempit drastis. Menandakan volatilitas sedang "ditekan" dan akan segera meledak ke salah satu arah.
    * **ADX (Average Directional Index)**: Pengukur kekuatan tren. Jika `ADX < 20`, pasar sedang sideways lemah (hindari scalping karena rawan kena false break/whipsaw). Jika `ADX > 25`, tren kuat dan aman untuk follow-the-trend scalping.
    * **HAKA (Hajar Kanan)**: Membeli langsung di harga Offer (antrean jual) tanpa mengantri agar langsung match saat ada momentum breakout cepat.
    * **HAKI (Hajar Kiri)**: Menjual langsung di harga Bid (antrean beli) untuk langsung keluar/cut loss tanpa menunggu antrean.
    * **Trailing Stop Loss**: Menggeser level Stop Loss ke atas mengikuti kenaikan harga untuk mengunci keuntungan yang sudah didapat.
    * **Partial Take Profit**: Menjual sebagian posisi (misal 50%) pada target awal, lalu membiarkan sisa posisi berjalan dengan stop loss di harga modal (*breakeven*).
    """)
