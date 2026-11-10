"""pages/05_Market_Scanner.py — Quant Market Scanner & Trending Saham BEI

Fitur Kuantitatif:
1. Memindai 80+ saham likuid & aktif di Bursa Efek Indonesia (BEI) dalam 3-5 detik via batch processing.
2. 5 Tab Terstruktur & Terpisah agar tidak membingungkan:
   - 📜 Histori & Validasi Kemarin: Audit bukti akurasi sinyal kemarin terhadap pasar hari ini (Win/Loss/Cuan)
   - ⚡ Top Scalping Hari Ini: Setup fast momentum & execution plan intraday
   - 🔥 Trending & Volume Surge: Saham dengan lonjakan likuiditas & akumulasi
   - 🌊 Top Swing Trading: Setup Stage 2 Uptrend & Pullback MA20 (RR min 1:2)
   - 🔮 Proyeksi Esok Hari (T+1): Model probabilitas arah harga sesi besok
3. Filter berdasarkan Kategori Emiten (Semua, LQ45/IDX30, Scalping Friendly, dsb.)
4. 1-Click Action: Tambahkan ke Watchlist
"""

import time
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import importlib

import data.idx_universe
import data.scanner
import analysis.scalping
import analysis.forecast
import analysis.technical
try:
    importlib.reload(data.idx_universe)
    importlib.reload(data.scanner)
    importlib.reload(analysis.scalping)
    importlib.reload(analysis.forecast)
    importlib.reload(analysis.technical)
except Exception:
    pass

from data.idx_universe import IDX_UNIVERSE, get_all_universe_tickers, get_universe_by_category
from data.scanner import fetch_universe_ohlcv_batch, run_full_market_scan, run_historical_validation
from analysis.ihsg import analyze_ihsg_regime
from database.models import get_watchlist, add_to_watchlist

st.set_page_config(page_title="Market Scanner — Saham BEI", page_icon="🔎", layout="wide")

st.markdown("""
<style>
.badge-bull {
    background-color: rgba(34, 197, 94, 0.15);
    color: #22c55e;
    padding: 3px 8px;
    border-radius: 6px;
    font-weight: 600;
    font-size: 0.85rem;
    border: 1px solid rgba(34, 197, 94, 0.3);
}
.badge-loss {
    background-color: rgba(239, 68, 68, 0.15);
    color: #ef4444;
    padding: 3px 8px;
    border-radius: 6px;
    font-weight: 600;
    font-size: 0.85rem;
    border: 1px solid rgba(239, 68, 68, 0.3);
}
.badge-neutral {
    background-color: rgba(148, 163, 184, 0.15);
    color: #94a3b8;
    padding: 3px 8px;
    border-radius: 6px;
    font-weight: 600;
    font-size: 0.85rem;
    border: 1px solid rgba(148, 163, 184, 0.3);
}
.badge-info {
    background-color: rgba(59, 130, 246, 0.15);
    color: #3b82f6;
    padding: 3px 8px;
    border-radius: 6px;
    font-weight: 600;
    font-size: 0.85rem;
    border: 1px solid rgba(59, 130, 246, 0.3);
}
.badge-warn {
    background-color: rgba(234, 179, 8, 0.15);
    color: #eab308;
    padding: 3px 8px;
    border-radius: 6px;
    font-weight: 600;
    font-size: 0.85rem;
    border: 1px solid rgba(234, 179, 8, 0.3);
}
.badge-chase {
    background-color: rgba(168, 85, 247, 0.15);
    color: #a855f7;
    padding: 3px 8px;
    border-radius: 6px;
    font-weight: 600;
    font-size: 0.85rem;
    border: 1px solid rgba(168, 85, 247, 0.3);
}
</style>
""", unsafe_allow_html=True)

st.title("🔎 Market Scanner & Analisis Saham BEI")
st.caption("Terminal Kuantitatif Otomatis Bursa Efek Indonesia — Pisahkan dengan jelas antara Rekam Jejak Kemarin, Setup Hari Ini, dan Peluang Esok Hari.")


# ── CACHED DATA FETCHING ───────────────────────────────────────
@st.cache_data(ttl=600, show_spinner=False)
def get_cached_scanner_data():
    tickers = get_all_universe_tickers()
    dfs = fetch_universe_ohlcv_batch(tickers, period="2mo")
    results = run_full_market_scan(dfs)
    validation = run_historical_validation(dfs)
    return dfs, results, validation, time.time()


# ── SIDEBAR CONTROLS ──────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Pengaturan Scanner")
    
    cat_filter = st.selectbox(
        "Kategori Universe BEI:",
        options=["ALL (Semua ~80 Saham)", "LQ45 / IDX30 (Blue Chip Likuid)", "SCALP_FRIENDLY (Volatilitas Tinggi)", "SWING (Uptrend Mantap)"],
        index=0,
    )
    cat_key = "ALL"
    if "LQ45" in cat_filter:
        cat_key = "LQ45"
    elif "SCALP_FRIENDLY" in cat_filter:
        cat_key = "SCALP_FRIENDLY"
    elif "SWING" in cat_filter:
        cat_key = "SWING"

    all_sectors = sorted(list(set(s["sector"] for s in IDX_UNIVERSE)))
    selected_sector = st.selectbox("Filter Sektor:", options=["Semua Sektor"] + all_sectors)

    st.markdown("---")
    if st.button("🔄 Scan Ulang Pasar Sekarang", type="primary", use_container_width=True):
        st.cache_data.clear()
        st.success("Cache dibersihkan! Memindai ulang pasar...")
        st.rerun()

    st.info("💡 **Tips Institusional**: Data di-cache selama 10 menit agar akses cepat. Klik 'Scan Ulang' jika ingin data realtime terbaru.")


# ── RUN SCREENING ──────────────────────────────────────────────
with st.spinner("📡 Memindai puluhan saham BEI secara batch..."):
    dfs, scan_results, validation_results, timestamp = get_cached_scanner_data()

curr_watchlist = get_watchlist()
wl_tickers = {item["ticker"] for item in curr_watchlist}


def filter_items(items: list) -> list:
    filtered = []
    category_tickers = {s["ticker"] for s in get_universe_by_category(cat_key)} if cat_key != "ALL" else None
    for it in items:
        t = it["ticker"]
        if category_tickers is not None and t not in category_tickers:
            continue
        if selected_sector != "Semua Sektor" and it.get("sector") != selected_sector:
            continue
        filtered.append(it)
    return filtered


# ── IHSG MACRO REGIME BANNER ──────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def get_ihsg_banner_info():
    try:
        return analyze_ihsg_regime()
    except Exception:
        return None

ihsg_reg = get_ihsg_banner_info()
if ihsg_reg and ihsg_reg.get("status") != "UNKNOWN":
    ihsg_light = ihsg_reg["traffic_light"]
    ihsg_col = ihsg_reg["color"]
    ihsg_title = ihsg_reg["regime_title"]
    ihsg_advice = ihsg_reg["action_advice"]
    ihsg_lot = int(ihsg_reg["lot_multiplier"] * 100)
    
    st.markdown(f'''
    <div style="background-color: rgba(22, 27, 34, 0.85); border-left: 6px solid {ihsg_col}; border-radius: 8px; padding: 12px 18px; margin-bottom: 16px;">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
            <div>
                <span style="font-size: 1.1rem; font-weight: 700; color: {ihsg_col};">{ihsg_light} KONDISI MAKRO IHSG: {ihsg_title}</span>
                <span style="color: #8b949e; margin-left: 10px;">(^JKSE: {ihsg_reg['price']:,.2f} | {ihsg_reg['change_pct']:+.2f}%)</span>
                <p style="margin: 4px 0 0 0; color: #c9d1d9; font-size: 0.92rem;">💡 <b>Panduan Trader:</b> {ihsg_advice}</p>
            </div>
            <div style="text-align: right;">
                <span style="font-size: 0.85rem; color: #8b949e;">Batas Lot Disarankan:</span>
                <span style="font-size: 1.25rem; font-weight: 800; color: {ihsg_col}; margin-left: 6px;">{ihsg_lot}%</span>
            </div>
        </div>
    </div>
    ''', unsafe_allow_html=True)

# ── TOP SUMMARY METRICS ────────────────────────────────────────
trending_data = filter_items(scan_results.get("trending", []))
scalp_data = filter_items(scan_results.get("scalping", []))
swing_data = filter_items(scan_results.get("swing", []))
forecast_data = filter_items(scan_results.get("forecast", []))
hist_records = filter_items(validation_results.get("records", []))

c1, c2, c3, c4 = st.columns(4)
c1.metric("📜 Validasi Kemarin", f"{validation_results.get('win_rate', 0)}% Win", delta=f"{validation_results.get('win_count', 0)} Cuan / {validation_results.get('loss_count', 0)} Rugi")
c2.metric("⚡ Scalping Hari Ini", f"{len(scalp_data)} Emiten", delta="Fast In-Out")
c3.metric("🔥 Trending & Volume", f"{len(trending_data)} Emiten", delta="Surge")
c4.metric("🔮 Proyeksi Besok (T+1)", f"{len(forecast_data)} Emiten", delta="P > 52%")

st.markdown("<hr style='margin:10px 0;'>", unsafe_allow_html=True)


# ── TABS INTERFACE (DIPISAH SESUAI TIMELINE AGAR JELAS) ────────
tab_history, tab_scalping, tab_trending, tab_swing, tab_forecast = st.tabs([
    "📜 1. Histori & Validasi Kemarin",
    "⚡ 2. Top Scalping Hari Ini",
    "🔥 3. Saham Trending Hari Ini",
    "🌊 4. Top Swing Trading",
    "🔮 5. Proyeksi Esok Hari (T+1)",
])


# ══════════════════════════════════════════════════════════════
# TAB 1: HISTORI & VALIDASI HASIL KEMARIN
# ══════════════════════════════════════════════════════════════
with tab_history:
    st.subheader("📜 Rekam Jejak & Validasi: Pembuktian Sinyal Kemarin")
    st.caption(f"Audit objektif performa sinyal kemarin ({validation_results.get('date_signal', 'T-1')}) terhadap apa yang benar-benar terjadi di pasar hari ini ({validation_results.get('date_eval', 'T')}).")

    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    m_col1.metric("Tingkat Akurasi (Win Rate)", f"{validation_results.get('win_rate', 0)}%", delta="Peluang Cuan Intraday")
    m_col2.metric("Sinyal Kasih Cuan (Win)", f"{validation_results.get('win_count', 0)} Saham", delta="High sempat naik")
    m_col3.metric("Kena Stop Loss (Loss)", f"{validation_results.get('loss_count', 0)} Saham", delta="Disiplin Cut Loss", delta_color="inverse")
    m_col4.metric("Rata-rata Kenaikan Puncak", f"+{validation_results.get('avg_max_gain', 0)}%", delta="Max Intraday Gain")

    st.markdown("---")

    if not hist_records:
        st.info("Tidak ada data histori validasi untuk filter yang dipilih.")
    else:
        for idx, row in enumerate(hist_records):
            t = row["ticker"]
            with st.container(border=True):
                col_id, col_plan, col_res, col_badge = st.columns([3, 3, 2, 2])

                p_sig = row['price_signal']
                p_high = row['today_high']
                p_low = row['today_low']
                p_close = row['today_close']
                p_tp = row.get('target_tp', p_sig * 1.025)
                gain_pts = p_high - p_sig

                with col_id:
                    st.markdown(f"### **{t}** — {row['name']}")
                    st.markdown(f"🏷️ `{row['sector']}` | Sinyal Kemarin: **{row['scalp_signal']}**")
                    st.markdown(f"🎯 Setup: `{row['setup_name']}`")
                    st.markdown(f"💰 **Harga Rekomendasi Awal:** `Rp {p_sig:,.0f}`")
                    st.caption(f"Target TP Awal: Rp {p_tp:,.0f} | Stop Loss: Rp {row.get('stop_loss', p_sig*0.98):,.0f}")

                with col_plan:
                    st.markdown("**📊 Lintasan Harga Riil Hari Ini:**")
                    st.markdown(f"- 🚀 **Dari:** `Rp {p_sig:,.0f}` ➡️ **Melesat Tembus:** `Rp {p_high:,.0f}` (**+{row['max_gain_pct']:.2f}%** / `+{gain_pts:,.0f} poin`)")
                    st.markdown(f"- 🔻 **Titik Terendah (Low):** `Rp {p_low:,.0f}` ({row['max_dd_pct']:+.2f}%)")
                    st.markdown(f"- 🏁 **Penutupan Sesi:** `Rp {p_close:,.0f}` ({row['close_gain_pct']:+.2f}%)")

                with col_res:
                    st.metric("Kenaikan Tertinggi", f"+{row['max_gain_pct']:.2f}%", f"+{gain_pts:,.0f} poin")
                    if row["hit_tp"]:
                        st.markdown(f"<span class='badge-bull'>🎯 TEMBUS TP Rp {p_tp:,.0f}</span>", unsafe_allow_html=True)
                    elif row["hit_sl"]:
                        st.markdown("<span class='badge-loss'>🛑 KENA SL</span>", unsafe_allow_html=True)
                    else:
                        st.markdown("<span class='badge-neutral'>🟡 RUNNING</span>", unsafe_allow_html=True)

                with col_badge:
                    st.write("")
                    if row["badge_type"] == "WIN":
                        st.markdown(f"<span class='badge-bull'>{row['outcome']}</span>", unsafe_allow_html=True)
                        st.caption("Peluang take profit tercapai di sesi bursa.")
                    elif row["badge_type"] == "LOSS":
                        st.markdown(f"<span class='badge-loss'>{row['outcome']}</span>", unsafe_allow_html=True)
                        st.caption("Harga jebol batas bawah toleransi.")
                    else:
                        st.markdown(f"<span class='badge-neutral'>{row['outcome']}</span>", unsafe_allow_html=True)
                        st.caption("Harga bergerak mendatar.")


# ══════════════════════════════════════════════════════════════
# TAB 2: TOP SCALPING SETUPS HARI INI
# ══════════════════════════════════════════════════════════════
with tab_scalping:
    st.subheader("⚡ Top Scalping Setups Hari Ini — Cepat Masuk, Cepat Amankan Profit")
    st.caption("Setup teknikal ultra-cepat aktif untuk sesi perdagangan hari ini berdasarkan Bollinger Squeeze, Fast Stochastic, dan Triple EMA pullback.")

    if not scalp_data:
        st.info("Tidak ada saham dengan sinyal scalping valid pada filter ini hari ini.")
    else:
        for idx, row in enumerate(scalp_data):
            t = row["ticker"]
            with st.container(border=True):
                col_info, col_plan, col_chart, col_act = st.columns([3, 3, 3, 1.5])
                
                with col_info:
                    st.markdown(f"### **{t}** — {row['name']}")
                    st.markdown(f"🏷️ `{row['sector']}` | **Harga Running:** `Rp {row['price']:,.0f}` ({row['change_pct']:+.2f}%)")
                    st.markdown(f"🎯 **Setup:** `{row['setup_name']}`")
                    
                    # Live Buy Zone Status Indicator
                    b_badge = row.get("zone_badge", "NEUTRAL")
                    b_class = "badge-bull" if b_badge == "BUY" else ("badge-chase" if b_badge == "CHASE" else ("badge-loss" if b_badge == "LOSS" else ("badge-warn" if b_badge == "WARN" else "badge-neutral")))
                    st.markdown(f"<span class='{b_class}'>{row.get('zone_label', '🟡 RUNNING')}</span>", unsafe_allow_html=True)
                    st.caption(f"💡 *{row.get('zone_desc', '')}*")

                with col_plan:
                    st.markdown("**📌 Rencana Eksekusi PATEN (Order Book):**")
                    st.markdown(f"- 🟢 **Entry Paten:** `Rp {row['entry']:,.0f}` *(Jarak: {row.get('diff_entry_pct', 0):+.2f}%)*")
                    st.markdown(f"- 🎯 **Take Profit (+{row['reward_pct']}%):** `Rp {row['take_profit']:,.0f}`")
                    st.markdown(f"- 🛑 **Stop Loss Ketat (-{row['risk_pct']}%):** `Rp {row['stop_loss']:,.0f}`")
                    
                    # Indikator Akumulasi & Buffer Area Bawah
                    acc_pct = row.get('prob_accum', 60.0)
                    acc_color = "#22c55e" if acc_pct >= 65 else ("#eab308" if acc_pct >= 50 else "#ef4444")
                    st.markdown(f"**⚡ Probabilitas Akumulasi:** <span style='color:{acc_color}; font-weight:700;'>{acc_pct}%</span>", unsafe_allow_html=True)
                    st.markdown(f"🛡️ **Buffer Jarak ke Stop Loss:** `+{row.get('buffer_sl_pct', 0):.1f}%` *(Menghindari Area Bawah)*")

                with col_chart:
                    # Visualisasi Grafik Garis Pesanan (Take Profit, Entry, Stop Loss, Current Price)
                    p_curr = float(row['price'])
                    p_entry = float(row['entry'])
                    p_tp = float(row['take_profit'])
                    p_sl = float(row['stop_loss'])
                    
                    fig_order = go.Figure()
                    # Garis Area Trading Range (Background)
                    fig_order.add_trace(go.Scatter(
                        x=[0, 10], y=[p_entry, p_entry],
                        mode="lines", line=dict(color="#3b82f6", width=2, dash="dash"),
                        name="Entry Paten", hoverinfo="skip"
                    ))
                    fig_order.add_trace(go.Scatter(
                        x=[0, 10], y=[p_tp, p_tp],
                        mode="lines", line=dict(color="#22c55e", width=2.5),
                        name="Target TP", hoverinfo="skip"
                    ))
                    fig_order.add_trace(go.Scatter(
                        x=[0, 10], y=[p_sl, p_sl],
                        mode="lines", line=dict(color="#ef4444", width=2.5),
                        name="Stop Loss", hoverinfo="skip"
                    ))
                    # Titik Posisi Running Saat Ini
                    fig_order.add_trace(go.Scatter(
                        x=[5], y=[p_curr],
                        mode="markers+text",
                        marker=dict(size=12, color="#ffffff", line=dict(width=2, color="#eab308")),
                        text=[f"Live: {p_curr:,.0f}"], textposition="middle right",
                        name="Harga Saat Ini"
                    ))
                    fig_order.update_layout(
                        template="plotly_dark",
                        height=165,
                        margin=dict(l=5, r=10, t=10, b=10),
                        showlegend=False,
                        xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
                        yaxis=dict(
                            showgrid=True,
                            tickvals=[p_sl, p_entry, p_tp],
                            ticktext=[f"🛑 SL {p_sl:,.0f}", f"🟢 Entry {p_entry:,.0f}", f"🎯 TP {p_tp:,.0f}"],
                            zeroline=False,
                        ),
                    )
                    st.plotly_chart(fig_order, use_container_width=True, key=f"chart_ord_{t}_{idx}")

                with col_act:
                    st.write("")
                    st.metric("R:R Ratio", row["rr_ratio"])
                    if t in wl_tickers:
                        st.button("✅ Watchlist", key=f"wl_sc_{t}_{idx}", disabled=True, use_container_width=True)
                    else:
                        if st.button("➕ Watchlist", key=f"wl_sc_{t}_{idx}", use_container_width=True):
                            add_to_watchlist(t, row["name"], row["sector"])
                            st.success(f"{t} ditambahkan!")
                            st.rerun()


# ══════════════════════════════════════════════════════════════
# TAB 3: TRENDING & VOLUME SURGE
# ══════════════════════════════════════════════════════════════
with tab_trending:
    st.subheader("🔥 Saham Paling Trending & Lonjakan Volume Luar Biasa")
    st.caption("Saham yang mengalami akumulasi volume masif (>1.3x rata-rata 20 hari) dan/atau breakout dekat level harga tertinggi 20 hari.")

    if not trending_data:
        st.info("Belum ada saham yang memenuhi kriteria lonjakan volume & breakout pada filter yang dipilih saat ini.")
    else:
        for idx, row in enumerate(trending_data):
            t = row["ticker"]
            with st.container(border=True):
                col_info, col_vol, col_score, col_act = st.columns([3, 2, 2, 2])
                
                with col_info:
                    st.markdown(f"### **{t}** — {row['name']}")
                    st.markdown(f"🏷️ **Sektor:** `{row['sector']}` | **Harga:** `Rp {row['price']:,.0f}` ({row['change_pct']:+.2f}%)")
                    st.markdown(f"💡 **Analisis:** *{row['reason']}*")
                
                with col_vol:
                    st.metric("Volume vs MA20", f"{row['vol_ratio']:.1f}x", delta=f"{row['volume']:,} lembar")
                    if row.get("is_breakout"):
                        st.markdown("<span class='badge-bull'>🚀 BREAKOUT 20D HIGH</span>", unsafe_allow_html=True)
                    else:
                        st.markdown("<span class='badge-info'>📈 ACCUMULATION</span>", unsafe_allow_html=True)

                with col_score:
                    st.metric("Momentum Score", f"{row['trend_score']} / 100")
                    st.progress(min(row["trend_score"] / 100.0, 1.0))

                with col_act:
                    st.write("")
                    if t in wl_tickers:
                        st.button("✅ Ada di Watchlist", key=f"wl_tr_{t}_{idx}", disabled=True, use_container_width=True)
                    else:
                        if st.button("➕ Tambah Watchlist", key=f"wl_tr_{t}_{idx}", use_container_width=True):
                            add_to_watchlist(t, row["name"], row["sector"])
                            st.success(f"{t} ditambahkan!")
                            st.rerun()


# ══════════════════════════════════════════════════════════════
# TAB 4: TOP SWING TRADING
# ══════════════════════════════════════════════════════════════
with tab_swing:
    st.subheader("🌊 Top Swing Trading — Tren Kuat & Pullback Sehat")
    st.caption("Saham dalam fase Stage 2 Uptrend yang terkoreksi sehat mendekati support Moving Average (MA20), menawarkan rasio Risk-Reward prima (min 1:2).")

    if not swing_data:
        st.info("Belum ada setup swing trading yang memenuhi kriteria pullback sehat saat ini.")
    else:
        for idx, row in enumerate(swing_data):
            t = row["ticker"]
            with st.container(border=True):
                col_info, col_plan, col_stat, col_act = st.columns([3, 3, 2, 2])
                
                with col_info:
                    st.markdown(f"### **{t}** — {row['name']}")
                    st.markdown(f"🏷️ **Sektor:** `{row['sector']}` | **Harga:** `Rp {row['price']:,.0f}` ({row['change_pct']:+.2f}%)")
                    st.markdown(f"📊 **Konfirmasi:** *{row['setup']}*")
                    st.markdown(f"📍 **Jarak ke MA20:** `{row['dist_ma20']:+.1f}%`")

                with col_plan:
                    st.markdown("**Rencana Trading (Swing 3-10 Hari):**")
                    st.markdown(f"- 🟢 **Buy Area:** `Rp {row['entry']:,.0f}`")
                    st.markdown(f"- 🎯 **Target Profit (+{row['tp_pct']}%):** `Rp {row['take_profit']:,.0f}`")
                    st.markdown(f"- 🛑 **Stop Loss Proteksi (-{row['sl_pct']}%):** `Rp {row['stop_loss']:,.0f}`")

                with col_stat:
                    st.metric("Swing Score", f"{row['swing_score']} / 100")
                    st.metric("Risk-Reward Ratio", row["rr_ratio"])

                with col_act:
                    st.write("")
                    if t in wl_tickers:
                        st.button("✅ Ada di Watchlist", key=f"wl_sw_{t}_{idx}", disabled=True, use_container_width=True)
                    else:
                        if st.button("➕ Tambah Watchlist", key=f"wl_sw_{t}_{idx}", use_container_width=True):
                            add_to_watchlist(t, row["name"], row["sector"])
                            st.success(f"{t} ditambahkan!")
                            st.rerun()


# ══════════════════════════════════════════════════════════════
# TAB 5: PROYEKSI ESOK HARI (T+1)
# ══════════════════════════════════════════════════════════════
with tab_forecast:
    st.subheader("🔮 Saham dengan Probabilitas Menguat Tertinggi Besok")
    st.caption("Hasil perhitungan model probabilitas arah T+1 (Stochastic momentum, closing range strength, candle body, & volume confirmation).")

    if not forecast_data:
        st.info("Belum ada saham dengan probabilitas naik di atas 52% saat ini.")
    else:
        for idx, row in enumerate(forecast_data):
            t = row["ticker"]
            with st.container(border=True):
                col_info, col_prob, col_range, col_act = st.columns([3, 2, 3, 2])
                
                with col_info:
                    st.markdown(f"### **{t}** — {row['name']}")
                    st.markdown(f"🏷️ **Sektor:** `{row['sector']}` | **Harga:** `Rp {row['price']:,.0f}` ({row['change_pct']:+.2f}%)")
                    st.markdown(f"💡 **Katalis Teknis:** *{row['reasons']}*")

                with col_prob:
                    st.metric("Probabilitas Naik (T+1)", f"{row['prob_up']}%")
                    st.progress(row["prob_up"] / 100.0)

                with col_range:
                    st.markdown("**Estimasi Rentang Esok Hari:**")
                    st.markdown(f"- 🔼 **Ekspektasi High:** `Rp {row['est_high']:,.0f}`")
                    st.markdown(f"- 📍 **Pivot Penentu:** `Rp {row['pivot']:,.0f}`")
                    st.markdown(f"- 🔻 **Batas Bawah:** `Rp {row['est_low']:,.0f}`")

                with col_act:
                    st.write("")
                    if t in wl_tickers:
                        st.button("✅ Ada di Watchlist", key=f"wl_fc_{t}_{idx}", disabled=True, use_container_width=True)
                    else:
                        if st.button("➕ Tambah Watchlist", key=f"wl_fc_{t}_{idx}", use_container_width=True):
                            add_to_watchlist(t, row["name"], row["sector"])
                            st.success(f"{t} ditambahkan!")
                            st.rerun()
