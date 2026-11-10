"""pages/01_IHSG_Market_Pulse.py — Radar Sentimen Makro, Prediksi Besok (T+1), & Market Regime IHSG

Fitur:
1. Tombol "🔄 Refresh Data IHSG Sekarang" di Sidebar & Atas Halaman.
2. Prediksi Kuantitatif Arah IHSG Besok (T+1):
   - Probabilitas Naik vs Turun (% Directional Probability)
   - Rentang Proyeksi High-Low Tom DeMark & Volatilitas ATR
   - Level Penentu Make-or-Break (Pivot Sesi Pagi 09:00 WIB)
   - Skenario Bullish vs Skenario Bearish
3. Traffic Light System Real-Time (🟢 RISK-ON / 🟡 SELECTIVE / 🔴 RISK-OFF).
4. Rekomendasi Alokasi Modal & Ukuran Lot berdasarkan kondisi IHSG.
5. Level Penentu (Pivot, Support 1-2, Resistance 1-2, Moving Average 20/50/200).
6. Grafik Interaktif Candlestick & Indikator Teknikal IHSG (MA, BB, MACD, RSI).
7. Breadth Pasar BEI (Rasio Saham Naik vs Turun di Universe BEI).
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import importlib
import time

import analysis.ihsg
import analysis.forecast
from data.idx_universe import get_all_universe_tickers
from data.scanner import fetch_universe_ohlcv_batch
try:
    importlib.reload(analysis.ihsg)
    importlib.reload(analysis.forecast)
except Exception:
    pass

from analysis.ihsg import analyze_ihsg_regime, fetch_ihsg_data
from analysis.forecast import calculate_next_day_forecast

st.set_page_config(page_title="IHSG Market Pulse — Saham Monitor", page_icon="🏛️", layout="wide")

# ── Header ───────────────────────────────────────────────────
st.title("🏛️ IHSG Market Pulse & Sentimen Makro BEI")
st.caption("Pusat Komando Makro Bursa Efek Indonesia — Analisis Tren Indeks Acuan, Market Regime, & Prediksi Arah IHSG Sesi Besok (T+1).")


# ── Load IHSG Analysis & Forecast ────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def get_cached_ihsg_all():
    df = fetch_ihsg_data(period="1y")
    regime = analyze_ihsg_regime(df)
    # Proyeksi untuk BESOK (T+1) dihitung dari data hari ini
    forecast_tomorrow = calculate_next_day_forecast(df)
    # Proyeksi untuk HARI INI dihitung dari data kemarin (baseline T-1)
    df_yest = df.iloc[:-1].copy() if len(df) > 1 else df.copy()
    forecast_today = calculate_next_day_forecast(df_yest)
    return df, regime, forecast_today, forecast_tomorrow, time.time()


# ── Sidebar Controls ──────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Kontrol Data IHSG")
    st.info("💡 **Tips**: Data IHSG di-cache selama 5 menit agar cepat. Gunakan tombol di bawah untuk mengambil data tick bursa terbaru.")
    
    if st.button("🔄 Refresh Data IHSG Sekarang", type="primary", use_container_width=True):
        st.cache_data.clear()
        st.success("Cache IHSG dibersihkan! Mengambil data pasar terbaru...")
        st.rerun()

    st.markdown("---")
    st.markdown("### 📌 Indeks Acuan:")
    st.markdown("- **Ticker:** `^JKSE` (BEI)")
    st.markdown("- **Jam Bursa:** 09:00 - 16:00 WIB")
    st.markdown("- **Sesi 1:** 09:00 - 12:00 WIB")
    st.markdown("- **Sesi 2:** 13:30 - 15:49 WIB")


with st.spinner("📡 Mengambil data sentimen & kalkulasi proyeksi IHSG (^JKSE)..."):
    df_raw, regime, forecast_today, forecast_tomorrow, t_stamp = get_cached_ihsg_all()

if not regime or regime.get("status") == "UNKNOWN":
    st.error("Gagal memuat data IHSG dari feed pasar. Silakan coba lagi beberapa saat.")
    st.stop()


# ── TRAFFIC LIGHT HERO BANNER ─────────────────────────────────
light = regime["traffic_light"]
color = regime["color"]
title = regime["regime_title"]
advice = regime["action_advice"]
lot_mult = int(regime["lot_multiplier"] * 100)

st.markdown(f"""
<div style="background-color: rgba(22, 27, 34, 0.85); border: 2px solid {color}; border-radius: 12px; padding: 18px 24px; margin-bottom: 20px;">
    <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap;">
        <div>
            <h2 style="margin: 0; color: {color}; font-size: 1.6rem;">{light} MARKET REGIME: {title}</h2>
            <p style="margin: 6px 0 0 0; color: #e6edf3; font-size: 1.05rem;">{advice}</p>
        </div>
        <div style="text-align: right; margin-top: 8px;">
            <span style="font-size: 0.9rem; color: #8b949e;">Rekomendasi Kapasitas Lot:</span><br>
            <span style="font-size: 1.8rem; font-weight: 800; color: {color};">{lot_mult}% Modus</span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)


# ── KEY METRICS CARDS ─────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric(
    "Indeks IHSG (^JKSE)",
    f"{regime['price']:,.2f}",
    delta=f"{regime['change_pts']:+,.2f} ({regime['change_pct']:+.2f}%)"
)
c2.metric(
    "Support Kunci (S1)",
    f"{regime['s1']:,.1f}",
    delta=f"{regime['price'] - regime['s1']:+,.1f} pt buffer"
)
c3.metric(
    "Resistance Kunci (R1)",
    f"{regime['r1']:,.1f}",
    delta=f"{regime['r1'] - regime['price']:,.1f} pt to test"
)
c4.metric(
    "RSI Momentum (14)",
    f"{regime['rsi']:.1f}",
    delta="Jenuh Jual (Oversold)" if regime['rsi'] < 30 else ("Jenuh Beli" if regime['rsi'] > 70 else "Zona Netral")
)

st.markdown("<hr style='margin:15px 0;'>", unsafe_allow_html=True)


# ── TABS LAYOUT ───────────────────────────────────────────────
tab_today, tab_tomorrow, tab_chart, tab_structure, tab_breadth, tab_guidance = st.tabs([
    "🎯 1. Prediksi & Tracking Hari Ini",
    "🔮 2. Proyeksi IHSG Besok (T+1)",
    "📈 3. Grafik Teknikal IHSG",
    "🧱 4. Struktur Level Kunci & Moving Average",
    "🌊 5. Market Breadth (Saham Naik vs Turun)",
    "🧭 6. Panduan Taktis Eksekusi",
])


# ══════════════════════════════════════════════════════════════
# TAB 1: PREDIKSI & TRACKING HARI INI
# ══════════════════════════════════════════════════════════════
with tab_today:
    st.subheader("🎯 Prediksi & Real-Time Tracking IHSG Hari Ini")
    st.caption("Membandingkan target proyeksi yang dihitung dari penutupan kemarin dengan pergerakan nyata indeks IHSG sesi hari ini.")

    if not forecast_today:
        st.info("Data tidak cukup untuk menghitung prediksi IHSG hari ini.")
    else:
        last_bar = df_raw.iloc[-1]
        c_live = float(last_bar["close"])
        h_today = float(last_bar["high"])
        l_today = float(last_bar["low"])
        o_today = float(last_bar["open"])
        
        pivot_today = float(forecast_today["pivot"])
        proj_max_today = float(forecast_today["proj_max"])
        proj_min_today = float(forecast_today["proj_min"])
        r1_today = float(forecast_today["r1"])
        s1_today = float(forecast_today["s1"])
        prob_up_today = forecast_today["prob_up"]
        
        # Tracking Status Real-time vs Proyeksi Hari Ini
        diff_from_pivot = c_live - pivot_today
        if c_live >= r1_today:
            track_status = "🚀 BULLISH EXPANSION (Menembus Target R1)"
            track_badge = "badge-bull"
            track_msg = f"IHSG menguat perkasa di atas R1 ({r1_today:,.1f}). Pembeli sangat dominan!"
        elif c_live > pivot_today:
            track_status = "🟢 ON TRACK BULLISH (Di Atas Pivot)"
            track_badge = "badge-bull"
            track_msg = f"IHSG berhasil bertahan di atas level Pivot ({pivot_today:,.1f}). Skenario Bullish aktif!"
        elif c_live <= s1_today:
            track_status = "🛑 BEARISH BREAKDOWN (Jebol Support S1)"
            track_badge = "badge-loss"
            track_msg = f"IHSG tertekan menembus Support S1 ({s1_today:,.1f}). Waspada pelemahan lanjutan!"
        else:
            track_status = "🟡 KONSOLIDASI (Di Bawah Pivot, Di Atas Support)"
            track_badge = "badge-warn"
            track_msg = f"IHSG berada sedikit di bawah Pivot ({pivot_today:,.1f}), menguji bantalan support S1."

        # Hero Tracking Banner Hari Ini
        st.markdown(f'''
        <div style="background-color: rgba(22, 27, 34, 0.85); border: 2px solid #30363d; border-radius: 10px; padding: 14px 20px; margin-bottom: 20px;">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
                <div>
                    <span style="font-size: 1.15rem; font-weight: 800; color: #58a6ff;">STATUS SESI HARI INI: {track_status}</span>
                    <p style="margin: 4px 0 0 0; color: #e6edf3; font-size: 0.95rem;">💡 {track_msg}</p>
                </div>
                <div style="text-align: right;">
                    <span style="font-size: 0.85rem; color: #8b949e;">Posisi vs Pivot Hari Ini:</span><br>
                    <span style="font-size: 1.3rem; font-weight: 800; color: {'#22c55e' if diff_from_pivot >= 0 else '#ef4444'};">{diff_from_pivot:+,.1f} pt</span>
                </div>
            </div>
        </div>
        ''', unsafe_allow_html=True)

        col_td1, col_td2, col_td3 = st.columns(3)
        with col_td1:
            with st.container(border=True):
                st.markdown("### 📊 Prediksi Arah Hari Ini")
                st.metric("Peluang Menguat", f"{prob_up_today}%", delta=f"{forecast_today['bias_label']}")
                st.progress(prob_up_today / 100.0)
                st.caption(f"Tingkat Keyakinan: **{forecast_today.get('confidence', 'Moderat')}**")
                st.markdown(f"- 📈 **Batas Atas Hari Ini:** `Rp {proj_max_today:,.1f}`")
                st.markdown(f"- 📍 **Pivot Penentu Pagi:** `Rp {pivot_today:,.1f}`")
                st.markdown(f"- 📉 **Batas Bawah Hari Ini:** `Rp {proj_min_today:,.1f}`")

        with col_td2:
            with st.container(border=True):
                st.markdown("### ⚡ Realisasi Pasar Hari Ini")
                st.metric("Indeks Running", f"{c_live:,.2f}", delta=f"{c_live - o_today:+,.2f} vs Open")
                st.markdown(f"- 🔼 **Tertinggi (High):** `Rp {h_today:,.2f}`")
                st.markdown(f"- 🚪 **Pembukaan (Open):** `Rp {o_today:,.2f}`")
                st.markdown(f"- 🔻 **Terendah (Low):** `Rp {l_today:,.2f}`")
                
                # Check target hits
                if h_today >= r1_today:
                    st.success(f"🎯 Target R1 ({r1_today:,.1f}) sempat tersentuh hari ini!")
                elif l_today <= s1_today:
                    st.warning(f"⚠️ Support S1 ({s1_today:,.1f}) sempat diuji hari ini.")

        with col_td3:
            with st.container(border=True):
                st.markdown("### 🧭 Panduan Eksekusi Hari Ini")
                st.markdown(f"**Skenario Aktif:** {'🟢 Bullish' if c_live >= pivot_today else '🔴 Defensif / Uji Support'}")
                if c_live >= pivot_today:
                    st.info(f"IHSG kuat di atas Pivot Rp {pivot_today:,.1f}. Kamu boleh aktif scalping pada saham-saham di tab Top Scalping!")
                else:
                    st.warning(f"IHSG di bawah Pivot Rp {pivot_today:,.1f}. Batasi lot scalping, jangan memaksakan diri masuk ke saham yang mulai merah.")
                st.caption(f"Target Sasaran Sesi 2: **Rp {r1_today:,.1f}** | Benteng Batas: **Rp {s1_today:,.1f}**")

        st.markdown("---")
        st.markdown("#### 🔍 Visualisasi Posisi Real-Time Hari Ini di Dalam Rentang Prediksi:")
        fig_today = go.Figure()
        fig_today.add_trace(go.Scatter(
            x=[0, 10], y=[proj_max_today, proj_max_today],
            mode="lines", line=dict(color="#22c55e", width=2),
            name="Batas Atas Prediksi"
        ))
        fig_today.add_trace(go.Scatter(
            x=[0, 10], y=[r1_today, r1_today],
            mode="lines", line=dict(color="#86efac", width=1.5, dash="dot"),
            name="Target R1"
        ))
        fig_today.add_trace(go.Scatter(
            x=[0, 10], y=[pivot_today, pivot_today],
            mode="lines", line=dict(color="#3b82f6", width=2, dash="dash"),
            name="Pivot Penentu"
        ))
        fig_today.add_trace(go.Scatter(
            x=[0, 10], y=[s1_today, s1_today],
            mode="lines", line=dict(color="#fca5a5", width=1.5, dash="dot"),
            name="Support S1"
        ))
        fig_today.add_trace(go.Scatter(
            x=[0, 10], y=[proj_min_today, proj_min_today],
            mode="lines", line=dict(color="#ef4444", width=2),
            name="Batas Bawah Prediksi"
        ))
        fig_today.add_trace(go.Scatter(
            x=[5], y=[c_live],
            mode="markers+text",
            marker=dict(size=14, color="#ffffff", line=dict(width=3, color="#f59e0b")),
            text=[f"IHSG Live: {c_live:,.1f}"], textposition="middle right",
            name="IHSG Saat Ini"
        ))
        fig_today.update_layout(
            template="plotly_dark",
            height=260,
            margin=dict(l=10, r=20, t=10, b=10),
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
            yaxis=dict(
                showgrid=True,
                tickvals=[proj_min_today, s1_today, pivot_today, r1_today, proj_max_today],
                ticktext=[f"Min: {proj_min_today:,.0f}", f"S1: {s1_today:,.0f}", f"Pivot: {pivot_today:,.0f}", f"R1: {r1_today:,.0f}", f"Max: {proj_max_today:,.0f}"],
            ),
        )
        st.plotly_chart(fig_today, use_container_width=True)


# ══════════════════════════════════════════════════════════════
# TAB 2: PROYEKSI IHSG BESOK (T+1)
# ══════════════════════════════════════════════════════════════
with tab_tomorrow:
    st.subheader("🔮 Proyeksi & Probabilitas Arah IHSG untuk Sesi Besok (T+1)")
    st.caption("Hasil komputasi model kuantitatif multi-faktor standar institusional: Closing Range Strength, Candlestick Momentum, Moving Average Slope, Tom DeMark Range, dan ATR Volatility.")

    forecast = forecast_tomorrow
    if not forecast:
        st.info("Data tidak cukup untuk menghitung prediksi IHSG besok.")
    else:
        prob_up = forecast["prob_up"]
        prob_down = forecast["prob_down"]
        bias_label = forecast["bias_label"]
        bias_col = forecast["bias_color"]
        bias_emoji = forecast["bias_emoji"]

        # Card Probabilitas Arah
        fc_col1, fc_col2 = st.columns([4, 6])
        with fc_col1:
            with st.container(border=True):
                st.markdown(f"### {bias_emoji} Bias Arah: **{bias_label}**")
                st.metric("Peluang Menguat (Naik)", f"{prob_up}%", delta=f"{prob_up - 50:+d}% vs Netral")
                st.progress(prob_up / 100.0)
                st.metric("Peluang Melemah (Koreksi)", f"{prob_down}%")
                st.caption(f"Tingkat Keyakinan Model: **{forecast.get('confidence', 'Moderat')}**")

        with fc_col2:
            with st.container(border=True):
                st.markdown("### 🎯 Estimasi Rentang Indeks Sesi Besok")
                r_c1, r_c2, r_c3 = st.columns(3)
                r_c1.metric("Batas Atas (Max High)", f"{forecast['proj_max']:,.1f}", f"+{forecast['upside_pct']}%")
                r_c2.metric("Level Pivot Penentu", f"{forecast['pivot']:,.1f}", "Make-or-Break")
                r_c3.metric("Batas Bawah (Min Low)", f"{forecast['proj_min']:,.1f}", f"-{forecast['downside_pct']}%")
                
                st.markdown(f"""
                - 🔼 **DeMark Range High:** `Rp {forecast['demark_high']:,.1f}`
                - 🔻 **DeMark Range Low:** `Rp {forecast['demark_low']:,.1f}`
                - ⚡ **Volatilitas Harian ATR(14):** `±{forecast.get('atr', 0):,.1f} poin`
                """)

        st.markdown("---")

        # Katalis Teknis
        c_katalis1, c_katalis2 = st.columns(2)
        with c_katalis1:
            st.markdown("#### 🟢 Katalis Pendorong Kenaikan (Bullish Factors):")
            if forecast.get("reasons_bullish"):
                for rb in forecast["reasons_bullish"]:
                    st.markdown(f"- ✅ {rb}")
            else:
                st.markdown("- *Belum ada katalis teknikal bullish dominan.*")

        with c_katalis2:
            st.markdown("#### 🔴 Faktor Penekan / Beban Indeks (Bearish Factors):")
            if forecast.get("reasons_bearish"):
                for rbe in forecast["reasons_bearish"]:
                    st.markdown(f"- ⚠️ {rbe}")
            else:
                st.markdown("- *Tekanan jual makro relatif mereda.*")

        st.markdown("---")

        # Dua Skenario Taktis Besok Pagi
        sc1, sc2 = st.columns(2)
        with sc1:
            with st.container(border=True):
                st.markdown("### 🟢 Skenario Bullish (Jika Dibuka Hijau)")
                st.markdown(f"**Pemicu:** {forecast['scenario_bullish']['trigger']}")
                st.markdown(f"- **Target 1:** `{forecast['scenario_bullish']['target_1']}`")
                st.markdown(f"- **Target 2:** `{forecast['scenario_bullish']['target_2']}`")
                st.info(f"💡 **Aksi Trader:** {forecast['scenario_bullish']['action']}")

        with sc2:
            with st.container(border=True):
                st.markdown("### 🔴 Skenario Bearish (Jika Tekanan Berlanjut)")
                st.markdown(f"**Pemicu:** {forecast['scenario_bearish']['trigger']}")
                st.markdown(f"- **Support 1:** `{forecast['scenario_bearish']['support_1']}`")
                st.markdown(f"- **Support 2:** `{forecast['scenario_bearish']['support_2']}`")
                st.warning(f"🛡️ **Aksi Trader:** {forecast['scenario_bearish']['action']}")

        # Panduan Khusus Jam 09:00 WIB
        plan_txt = str(forecast.get("action_plan_tomorrow", ""))
        header_txt = "Panduan Jam 09:00 WIB Besok Pagi: "
        st.success(header_txt + plan_txt)

# ══════════════════════════════════════════════════════════════
# TAB 2: GRAFIK TEKNIKAL IHSG
# ══════════════════════════════════════════════════════════════
with tab_chart:
    st.subheader("📈 Analisis Candlestick & Indikator Tren IHSG")
    df_chart = regime["df"].tail(120).copy()

    # Subplots Candlestick + MACD
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.72, 0.28],
    )

    # 1. Candlestick
    fig.add_trace(go.Candlestick(
        x=df_chart["date"],
        open=df_chart["open"],
        high=df_chart["high"],
        low=df_chart["low"],
        close=df_chart["close"],
        name="IHSG",
        increasing_line_color="#22c55e",
        decreasing_line_color="#ef4444",
    ), row=1, col=1)

    # Moving Averages
    fig.add_trace(go.Scatter(
        x=df_chart["date"], y=df_chart["MA20"],
        line=dict(color="#3b82f6", width=1.5),
        name="MA20 (Jangka Pendek)"
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=df_chart["date"], y=df_chart["MA50"],
        line=dict(color="#f59e0b", width=1.5),
        name="MA50 (Menengah)"
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=df_chart["date"], y=df_chart["MA200"],
        line=dict(color="#ec4899", width=2),
        name="MA200 (Benteng Utama)"
    ), row=1, col=1)

    # 2. MACD Histogram
    colors_macd = ["#22c55e" if val >= 0 else "#ef4444" for val in df_chart["MACD_Hist"]]
    fig.add_trace(go.Bar(
        x=df_chart["date"], y=df_chart["MACD_Hist"],
        marker_color=colors_macd, name="MACD Hist"
    ), row=2, col=1)

    fig.add_trace(go.Scatter(
        x=df_chart["date"], y=df_chart["MACD"],
        line=dict(color="#60a5fa", width=1.2), name="MACD Line"
    ), row=2, col=1)

    fig.add_trace(go.Scatter(
        x=df_chart["date"], y=df_chart["MACD_Signal"],
        line=dict(color="#f97316", width=1.2), name="Signal"
    ), row=2, col=1)

    fig.update_layout(
        template="plotly_dark",
        height=520,
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig, use_container_width=True)


# ══════════════════════════════════════════════════════════════
# TAB 3: STRUKTUR LEVEL KUNCI
# ══════════════════════════════════════════════════════════════
with tab_structure:
    st.subheader("🧱 Peta Benteng Support & Resistance IHSG")
    st.caption("Level-level matematis yang menjadi acuan manajer investasi & bandar dalam menjaga pergerakan indeks.")

    col_lvl1, col_lvl2 = st.columns(2)
    with col_lvl1:
        st.markdown("#### 🛡️ Benteng Pertahanan (Support Levels):")
        st.markdown(f"- **S1 (Support Harian Utama):** `Rp {regime['s1']:,.1f}`")
        st.markdown(f"- **S2 (Batas Bawah Ekstrem):** `Rp {regime['s2']:,.1f}`")
        st.markdown(f"- **Support MA20:** `Rp {regime['ma20']:,.1f}`")
        st.markdown(f"- **Support MA50:** `Rp {regime['ma50']:,.1f}`")
        st.markdown(f"- **Support MA200:** `Rp {regime['ma200']:,.1f}`")

    with col_lvl2:
        st.markdown("#### 🎯 Sasaran Penembusan (Resistance Levels):")
        st.markdown(f"- **Pivot Level (Penentu Pagi):** `Rp {regime['pivot']:,.1f}`")
        st.markdown(f"- **R1 (Target Rebound 1):** `Rp {regime['r1']:,.1f}`")
        st.markdown(f"- **R2 (Target Konfirmasi Bullish):** `Rp {regime['r2']:,.1f}`")

    st.markdown("---")
    st.markdown("#### 📋 Faktor Evaluasi Algoritma Makro:")
    for r in regime["reasons"]:
        st.markdown(f"- {r}")


# ══════════════════════════════════════════════════════════════
# TAB 4: MARKET BREADTH (KESEHATAN PASAR BEI)
# ══════════════════════════════════════════════════════════════
with tab_breadth:
    st.subheader("🌊 Market Breadth: Berapa Banyak Saham yang Naik vs Turun?")
    st.caption("Mengukur apakah pergerakan IHSG ditopang oleh mayoritas saham atau hanya segelintir saham konglomerasi.")

    @st.cache_data(ttl=600, show_spinner=False)
    def calculate_market_breadth():
        universe = get_all_universe_tickers()
        dfs = fetch_universe_ohlcv_batch(universe[:50], period="5d")
        advances = 0
        declines = 0
        unchanged = 0
        for t, d in dfs.items():
            if len(d) >= 2:
                c_now = float(d.iloc[-1]["close"])
                c_prev = float(d.iloc[-2]["close"])
                if c_now > c_prev:
                    advances += 1
                elif c_now < c_prev:
                    declines += 1
                else:
                    unchanged += 1
        return advances, declines, unchanged, len(dfs)

    adv, dec, unc, total_scanned = calculate_market_breadth()
    b1, b2, b3 = st.columns(3)
    b1.metric("🟢 Saham Menguat (Advancing)", f"{adv} Saham", f"{(adv/max(total_scanned,1)*100):.1f}% bursa")
    b2.metric("🔴 Saham Melemah (Declining)", f"{dec} Saham", f"{(dec/max(total_scanned,1)*100):.1f}% bursa", delta_color="inverse")
    b3.metric("⚪ Saham Mendatar (Unchanged)", f"{unc} Saham", f"{(unc/max(total_scanned,1)*100):.1f}%")

    if dec > adv * 2:
        st.error("⚠️ **Peringatan Tekanan Jual Luas:** Mayoritas saham di bursa sedang melemah. Hindari berspekulasi berlebihan.")
    elif adv > dec * 2:
        st.success("🚀 **Sentimen Bullish Meluas:** Sebagian besar saham bursa sedang diakumulasi naik.")
    else:
        st.info("⚖️ **Pasar Berimbang:** Pergerakan saham terpolarisasi merata.")


# ══════════════════════════════════════════════════════════════
# TAB 5: PANDUAN TAKTIS EKSEKUSI
# ══════════════════════════════════════════════════════════════
with tab_guidance:
    st.subheader("🧭 Aturan Main & Taktik Trading Sesuai Kondisi IHSG")
    st.markdown(f"""
    ### Status Saat Ini: **{light} {title}**
    
    1. **Bagi Scalper (Fast In-Out):**
       - **Ukuran Lot:** Pasang maksimal **{lot_mult}%** dari alokasi normal kamu.
       - **Strategi:** Jangan pegang barang terlalu lama. Begitu menyentuh target +1.5% s/d +3%, langsung kunci profit!
       - **Filter:** Pilih saham yang memiliki status *Anti-IHSG* (tetap hijau dan ada volume akumulasi tebal meskipun indeks tertekan).
    
    2. **Bagi Swing Trader (Hold Harian/Mingguan):**
       - Tunggu konfirmasi IHSG memantul dari level Support `Rp {regime['s1']:,.1f}` sebelum membuka posisi baru dalam jumlah besar.
       - Pasang *Trailing Stop* lebih longgar hanya untuk saham-saham yang bertahan di atas MA20.
    
    3. **Manajemen Emosi & Psikologi:**
       - Di pasar modal, **CASH ADALAH POSISI**. Tidak harus trading setiap hari jika kondisi indeks makro sedang berisiko tinggi.
    """)
