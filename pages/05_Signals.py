"""pages/04_Signals.py — Terminal Sinyal, Radar Saham Esok Hari (T+1), & Radar Scalping"""

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

from database.models import get_signals, get_watchlist, get_latest_price
from analysis.signals import generate_and_save_signals, generate_signals
import importlib
import analysis.technical
import analysis.forecast
try:
    importlib.reload(analysis.technical)
    importlib.reload(analysis.forecast)
except Exception:
    pass

from analysis.forecast import get_watchlist_forecast_radar, calculate_next_day_forecast
from analysis.ihsg import analyze_ihsg_regime
from analysis.scalping import generate_scalping_signals
from data.fetcher import get_price_df_from_db

st.set_page_config(page_title="Signals & Radar — Saham Monitor", page_icon="🚦", layout="wide")
st.title("🚦 Terminal Sinyal & Radar Saham")

# ── IHSG Context Banner ──────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def get_ihsg_signal_context():
    try:
        return analyze_ihsg_regime()
    except Exception:
        return None

ihsg_ctx = get_ihsg_signal_context()
if ihsg_ctx and ihsg_ctx.get("status") != "UNKNOWN":
    st.markdown(f'''
    <div style="background-color: rgba(22, 27, 34, 0.85); border-left: 6px solid {ihsg_ctx['color']}; border-radius: 8px; padding: 10px 16px; margin-bottom: 14px;">
        <span style="font-size: 1.0rem; font-weight: 700; color: {ihsg_ctx['color']};">{ihsg_ctx['traffic_light']} KONTEKS IHSG: {ihsg_ctx['regime_title']} ({ihsg_ctx['price']:,.2f} | {ihsg_ctx['change_pct']:+.2f}%)</span>
        <span style="color: #c9d1d9; font-size: 0.9rem; margin-left: 10px;">• Alokasi Lot Maksimal: <b>{int(ihsg_ctx['lot_multiplier']*100)}%</b> • {ihsg_ctx['action_advice']}</span>
    </div>
    ''', unsafe_allow_html=True)


# ── Sidebar ───────────────────────────────────────────────
with st.sidebar:
    st.header("⚡ Generate Sinyal")
    watchlist = get_watchlist()

    if watchlist:
        if st.button("🔄 Generate & Refresh Semua Sinyal", use_container_width=True, type="primary"):
            with st.spinner("Menganalisis semua saham..."):
                count = 0
                for s in watchlist:
                    ticker = s["ticker"]
                    df = get_price_df_from_db(ticker, limit=365)
                    if not df.empty and len(df) >= 30:
                        generate_and_save_signals(ticker)
                        count += 1
            st.success(f"✅ Sinyal di-generate untuk {count} saham!")
            st.rerun()


tab_radar, tab_scalp_radar, tab_signals = st.tabs([
    "🔮 Radar Saham Esok Hari (T+1)",
    "⚡ Radar Scalping Watchlist",
    "🚦 Sinyal Swing Engine V3",
])


# ════════════════════════════════════════════════════════
# TAB 1: RADAR SAHAM ESOK HARI (T+1)
# ════════════════════════════════════════════════════════
with tab_radar:
    st.subheader("🔮 Leaderboard Radar Saham untuk Sesi Besok (T+1)")
    st.caption("Peringkat seluruh saham watchlist diurutkan dari probabilitas penguatan tertinggi esok hari berdasarkan model kuantitatif multi-faktor.")

    if not watchlist:
        st.info("Watchlist kosong. Tambah saham di Settings.")
    else:
        with st.spinner("Mengkalkulasi radar esok hari..."):
            radar_data = get_watchlist_forecast_radar(watchlist)

        if not radar_data:
            st.info("Data harga belum cukup untuk kalkulasi radar esok hari.")
        else:
            top_stock = radar_data[0]
            top_prob = top_stock["prob_up"]

            # Top pick banner jika ada
            if top_prob >= 50:
                st.markdown(
                    f"""
                    <div style="background: rgba(0, 200, 83, 0.12); border: 2px solid #00C853;
                                border-radius: 12px; padding: 16px 20px; margin-bottom: 20px;">
                        <h4 style="color: #00C853; margin: 0 0 6px 0;">⭐ Top Bullish Candidate Besok: {top_stock['ticker']} ({top_stock['name']})</h4>
                        <div style="font-size: 1.05em; color: #eee;">
                            Probabilitas Naik: <b>{top_prob}%</b> &nbsp;|&nbsp; 
                            Harga Acuan: <b>Rp {top_stock['price']:,.0f}</b> &nbsp;|&nbsp; 
                            Level Penentu (Pivot): <b>Rp {top_stock['pivot']:,.0f}</b> &nbsp;|&nbsp; 
                            Target Atas: <b>Rp {top_stock['proj_max']:,.0f} (+{top_stock['upside_pct']}%)</b>
                        </div>
                        <div style="font-size: 0.9em; color: #ccc; margin-top: 6px;">
                            💡 <i>{top_stock['action_plan_tomorrow']}</i>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            # Tabel Radar Komprehensif
            radar_rows = []
            for r in radar_data:
                radar_rows.append({
                    "Ticker": r["ticker"],
                    "Perusahaan": r["name"],
                    "Harga": f"Rp {r['price']:,.0f}",
                    "Prob. Naik": f"{r['prob_up']}%",
                    "Prob. Turun": f"{r['prob_down']}%",
                    "Arah Bias": f"{r['bias_emoji']} {r['bias_label'].split('(')[0].strip()}",
                    "Pivot Penentu": f"Rp {r['pivot']:,.0f}",
                    "Target Atas": f"Rp {r['proj_max']:,.0f} (+{r['upside_pct']}%)",
                    "Target Bawah": f"Rp {r['proj_min']:,.0f} (-{r['downside_pct']}%)",
                    "Smart Money (CMF)": f"{r['cmf_status'].split('(')[0].strip()}",
                    "Setup Scalp": r["scalp_setups"],
                })

            df_radar_table = pd.DataFrame(radar_rows)
            st.dataframe(df_radar_table, use_container_width=True, hide_index=True)

            st.divider()

            # Kartu Rinci Per Saham
            st.markdown("#### 🔍 Detail Rencana & Skenario Esok Hari")
            for r in radar_data:
                with st.expander(f"{r['bias_emoji']} {r['ticker']} — Probabilitas Naik: {r['prob_up']}% | Harga: Rp {r['price']:,.0f} | Pivot: Rp {r['pivot']:,.0f}"):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown(f"**📍 Harga Terakhir:** Rp {r['price']:,.0f}")
                        st.markdown(f"**🔑 Level Penentu (Pivot):** Rp {r['pivot']:,.0f}")
                        st.markdown(f"**🟢 Target Atas:** Rp {r['proj_max']:,.0f} (+{r['upside_pct']}%)")
                        st.markdown(f"**🔴 Batas Bawah:** Rp {r['proj_min']:,.0f} (-{r['downside_pct']}%)")
                        st.markdown(f"**🌊 Arus Smart Money:** <span style='color:{r['cmf_color']}'><b>{r['cmf_status']}</b></span>", unsafe_allow_html=True)
                    with c2:
                        st.markdown(f"**⚡ Setup Scalping Aktif:** {r['scalp_setups']}")
                        st.markdown(f"**📊 Divergensi Volume:** {r['divergence']}")
                        st.info(f"📋 **Panduan Jam 09:00 WIB:** {r['action_plan_tomorrow']}")


# ════════════════════════════════════════════════════════
# TAB 2: RADAR SCALPING WATCHLIST
# ════════════════════════════════════════════════════════
with tab_scalp_radar:
    st.subheader("⚡ Scanner Setup Scalping Terverifikasi")
    st.caption("Memindai saham di watchlist yang sedang membentuk formasi siap entry (Pullback EMA, Fast Stochastic Cross, Bollinger Squeeze, atau Volume Spike).")

    if not watchlist:
        st.info("Watchlist kosong.")
    else:
        scalp_active = []
        for s in watchlist:
            ticker = s["ticker"]
            df = get_price_df_from_db(ticker, limit=60)
            if df.empty or len(df) < 25:
                continue
            sc = generate_scalping_signals(df)
            setups = sc.get("setups", [])
            if setups or "BUY" in sc.get("signal", ""):
                scalp_active.append({
                    "ticker": ticker,
                    "name": s["name"],
                    "signal": sc.get("signal", "WAIT"),
                    "color": sc.get("color", "#888"),
                    "emoji": sc.get("emoji", "⚪"),
                    "strength": sc.get("strength", 50),
                    "setups": setups,
                    "risk_mgmt": sc.get("risk_mgmt", {}),
                    "snap": sc.get("snapshot", {}),
                })

        if not scalp_active:
            st.info("ℹ️ Belum ada setup scalping aktif dengan konfirmasi tinggi di watchlist saat ini. Scalper pro bersabar menunggu momentum.")
        else:
            for item in scalp_active:
                col_a, col_b = st.columns([1, 3])
                with col_a:
                    st.markdown(
                        f"""
                        <div style="background:{item['color']}22; border: 1.5px solid {item['color']};
                                    border-radius: 8px; padding: 12px; text-align: center;">
                            <h3 style="color: {item['color']}; margin:0;">{item['emoji']} {item['ticker']}</h3>
                            <div style="font-size:0.9em; color:#ddd; margin-top:4px;">{item['signal']}</div>
                            <div style="font-size:0.8em; color:#aaa;">Skor: {item['strength']}/100</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                with col_b:
                    st.markdown(f"**{item['name']}** — Harga: Rp {item['snap'].get('price', 0):,.0f}")
                    rm = item["risk_mgmt"]
                    st.write(f"🛑 SL: Rp {rm.get('stop_loss', 0):,.0f} | 🎯 TP: Rp {rm.get('take_profit', 0):,.0f} | Rasio RR: {rm.get('risk_reward_ratio', '1:1.5')}")
                    for stp in item["setups"]:
                        st.caption(f"⚡ **{stp['name']}**: {stp['entry']} | {stp['exit']}")
                st.divider()


# ════════════════════════════════════════════════════════
# TAB 3: SINYAL SWING ENGINE V3
# ════════════════════════════════════════════════════════
with tab_signals:
    st.subheader("📋 Riwayat Sinyal Swing & Action Plan (Engine V3)")

    signals = get_signals(limit=100)

    if not signals:
        st.info("Belum ada sinyal. Klik **Generate & Refresh Semua Sinyal** di sidebar.")
    else:
        df_sig = pd.DataFrame(signals)

        # Filter
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            all_types = ["STRONG_BUY", "BUY", "HOLD", "HOLD / ILLIQUID", "SELL", "STRONG_SELL", "AVOID / HIGH_RISK"]
            filter_type = st.multiselect("Filter Sinyal", options=all_types, default=all_types)
        with col_f2:
            ticker_list = sorted(df_sig["ticker"].unique())
            filter_ticker = st.multiselect("Filter Saham", options=ticker_list)

        if filter_type:
            df_sig = df_sig[df_sig["signal_type"].isin(filter_type)]
        if filter_ticker:
            df_sig = df_sig[df_sig["ticker"].isin(filter_ticker)]

        SIGNAL_CONFIG = {
            "STRONG_BUY":        {"color": "#00C853", "emoji": "🟢🟢", "bg": "#00C85320"},
            "BUY":               {"color": "#69F0AE", "emoji": "🟢",   "bg": "#69F0AE15"},
            "HOLD":              {"color": "#FFD740", "emoji": "🟡",   "bg": "#FFD74015"},
            "HOLD / ILLIQUID":   {"color": "#FFB300", "emoji": "⚠️",   "bg": "#FFB30015"},
            "SELL":              {"color": "#FF6D00", "emoji": "🔴",   "bg": "#FF6D0015"},
            "STRONG_SELL":       {"color": "#D50000", "emoji": "🔴🔴", "bg": "#D5000020"},
            "AVOID / HIGH_RISK": {"color": "#E91E63", "emoji": "⛔",   "bg": "#E91E6325"},
        }

        # ── Tampilkan Kartu Sinyal ─────────────────────────
        for _, row in df_sig.head(20).iterrows():
            stype = row.get("signal_type", "")
            cfg = SIGNAL_CONFIG.get(stype, {"color": "#888", "emoji": "⚪", "bg": "#88888815"})
            t = row.get("ticker", "")
            lp_row = get_latest_price(t)
            lp_price = lp_row.get("close") if isinstance(lp_row, dict) else lp_row
            price_str = f"Rp {lp_price:,.0f}" if lp_price is not None else "—"
            strength_val = row.get("strength")
            strength_str = f"{strength_val}/100" if strength_val is not None else "—"
            created = str(row.get("generated_at", "—"))[:16]

            st.markdown(
                f"""
                <div style="background:{cfg['bg']}; border-left: 5px solid {cfg['color']}; border-radius: 0 8px 8px 0;
                            padding: 12px 16px; margin-bottom: 8px;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <span style="font-size:1.2em; font-weight:bold;">{t}</span>
                            &nbsp;
                            <span style="color:{cfg['color']}; font-weight:bold;">{cfg['emoji']} {stype}</span>
                        </div>
                        <div style="color:#aaa; font-size:0.85em;">
                            {created} &nbsp;|&nbsp; Harga: <b>{price_str}</b> &nbsp;|&nbsp; Skor: <b>{strength_str}</b>
                        </div>
                    </div>
                    <div style="color:#ddd; margin-top:6px; font-size:0.9em;">
                        {row.get('reason', '—')}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.divider()

        # Statistik Sinyal
        st.subheader("📊 Statistik Sinyal")
        all_signals = get_signals(limit=500)
        if all_signals:
            df_all = pd.DataFrame(all_signals)
            col1, col2 = st.columns(2)
            with col1:
                signal_counts = df_all["signal_type"].value_counts().reset_index()
                signal_counts.columns = ["signal_type", "count"]
                color_map = {k: v["color"] for k, v in SIGNAL_CONFIG.items()}
                fig = px.bar(
                    signal_counts, x="signal_type", y="count",
                    title="Distribusi Sinyal",
                    color="signal_type",
                    color_discrete_map=color_map,
                )
                fig.update_layout(template="plotly_dark", height=280, showlegend=False, margin=dict(l=0, r=0, t=40, b=0))
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                ticker_buy = df_all[df_all["signal_type"].isin(["BUY", "STRONG_BUY"])]
                if not ticker_buy.empty:
                    ticker_buy_count = ticker_buy["ticker"].value_counts().head(10).reset_index()
                    ticker_buy_count.columns = ["ticker", "count"]
                    fig2 = px.bar(
                        ticker_buy_count, x="ticker", y="count",
                        title="Top Saham dengan Sinyal BUY",
                        color_discrete_sequence=["#00C853"],
                    )
                    fig2.update_layout(template="plotly_dark", height=280, margin=dict(l=0, r=0, t=40, b=0))
                    st.plotly_chart(fig2, use_container_width=True)


st.markdown("---")

with st.expander("📚 Glosarium Klasifikasi Sinyal & Manajemen Risiko (Signals)", expanded=False):
    st.markdown("""
    Berikut panduan memahami arti status sinyal dan istilah trading plan yang dihasilkan sistem:

    | Status Sinyal | Badge | Arti & Tindakan yang Disarankan |
    | :--- | :---: | :--- |
    | **STRONG_BUY** | 🟢🟢 | **Sinyal Beli Sangat Kuat**: Terjadi konfirmasi serempak (Golden Cross MA20/50, MACD Bullish, harga di atas MA200, dan didukung volume akumulasi). |
    | **BUY** | 🟢 | **Sinyal Beli**: Tren teknikal positif dan momentum mendukung. Sistem langsung menyertakan rekomendasi level Stop Loss dan Target Take Profit. |
    | **HOLD** | 🟡 | **Tahan / Menunggu**: Saham sedang berada dalam fase konsolidasi atau belum memiliki arah tren yang tegas. Disarankan *wait and see* sebelum buka posisi baru. |
    | **HOLD / ILLIQUID** | ⚠️ | **Volume Transaksi Tipis**: Meskipun ada kenaikan, likuiditas lembar saham harian sangat kecil (< 500 ribu lembar), berisiko sulit dijual kembali. |
    | **SELL / STRONG_SELL** | 🔴 / 🔴🔴 | **Sinyal Jual / Hindari**: Terjadi Death Cross atau penembusan ke bawah garis support MA mayor. Momentum melemah (MACD negatif). |
    | **AVOID / HIGH_RISK** | ⛔ | **Proteksi Khusus (Saham Gocap / FCA)**: Saham berada di bawah harga Rp 50 atau masuk Papan Pemantauan Khusus. |
    """)
