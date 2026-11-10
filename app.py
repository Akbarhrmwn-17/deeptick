"""app.py — Entry point utama Saham Monitor"""

import os
import sys

# ── Path setup ────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
from database.db import init_db
from data.scheduler import start_scheduler
from config import APP_NAME, APP_VERSION

# ── Page Config ───────────────────────────────────────────
st.set_page_config(
    page_title=APP_NAME,
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS Kustom ────────────────────────────────────────────
st.markdown("""
<style>
/* Sidebar */
[data-testid="stSidebar"] { background: #0d1117; }
[data-testid="stSidebar"] * { color: #e6edf3 !important; }

/* Metric cards */
[data-testid="metric-container"] {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 12px;
}

/* Signal badges */
.signal-buy         { color: #00C853; font-weight: bold; }
.signal-strong-buy  { color: #00C853; font-weight: 900; }
.signal-sell        { color: #FF6D00; font-weight: bold; }
.signal-strong-sell { color: #D50000; font-weight: 900; }
.signal-hold        { color: #FFD740; font-weight: bold; }

/* Scrollable dataframe */
.stDataFrame { border-radius: 8px; }
</style>
""", unsafe_allow_html=True)


# ── Init DB & Scheduler (sekali saja) ─────────────────────
@st.cache_resource
def initialize():
    init_db()
    start_scheduler()
    return True


initialize()


# ── Home Page ─────────────────────────────────────────────
st.title(f"📊 {APP_NAME}")
st.caption(f"v{APP_VERSION} · Data dari Yahoo Finance · Waktu lokal Indonesia (WIB)")

st.markdown("""
Selamat datang di **Saham Monitor** — aplikasi pemantau saham IDX pribadimu. 🇮🇩

Navigasi menggunakan menu di **sidebar kiri**:

| Halaman | Fungsi |
|---|---|
| 🏛️ **IHSG Market Pulse** | Barometer makro pasar BEI, traffic light regime, support/resistance indeks |
| 📊 **Dashboard** | Grafik candlestick, indikator teknikal, ringkasan watchlist |
| 💼 **Portfolio** | Catat transaksi beli/jual, hitung P&L otomatis |
| 🔬 **Research** | Analisis mendalam teknikal + fundamental per saham |
| 🚦 **Signals** | Terminal sinyal, Radar Scalping, & Radar Saham T+1 |
| 🔎 **Market Scanner** | Screener 80+ emiten BEI: Trending, Scalping, Swing, Histori Validasi |
| ⚙️ **Settings** | Kelola watchlist, alert rules, konfigurasi broker |
| ⚡ **Running Trade** | Pantauan arus transaksi jual-beli real-time ala Stockbit |
""")

st.divider()

# ── IHSG Market Status Hero ───────────────────────────────
try:
    from analysis.ihsg import analyze_ihsg_regime
    ihsg_summary = analyze_ihsg_regime()
    if ihsg_summary and ihsg_summary.get("status") != "UNKNOWN":
        st.markdown(f'''
        <div style="background-color: rgba(22, 27, 34, 0.9); border: 2px solid {ihsg_summary['color']}; border-radius: 10px; padding: 14px 20px; margin-bottom: 20px;">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
                <div>
                    <span style="font-size: 1.15rem; font-weight: 800; color: {ihsg_summary['color']};">{ihsg_summary['traffic_light']} IHSG MAKRO: {ihsg_summary['regime_title']}</span>
                    <span style="color: #8b949e; margin-left: 12px; font-weight: 600;">^JKSE: {ihsg_summary['price']:,.2f} ({ihsg_summary['change_pct']:+.2f}%)</span>
                    <p style="margin: 6px 0 0 0; color: #e6edf3; font-size: 0.95rem;">{ihsg_summary['action_advice']}</p>
                </div>
                <div style="text-align: right;">
                    <span style="font-size: 0.85rem; color: #8b949e;">Alokasi Lot Aman:</span><br>
                    <span style="font-size: 1.4rem; font-weight: 800; color: {ihsg_summary['color']};">{int(ihsg_summary['lot_multiplier']*100)}%</span>
                </div>
            </div>
        </div>
        ''', unsafe_allow_html=True)
except Exception:
    pass

# ── Quick Stats ───────────────────────────────────────────
from database.models import get_watchlist, get_all_transactions, get_signals

col1, col2, col3, col4 = st.columns(4)

watchlist = get_watchlist()
transactions = get_all_transactions()
signals = get_signals(limit=10)

with col1:
    st.metric("📋 Watchlist", len(watchlist), "saham dipantau")
with col2:
    st.metric("💰 Transaksi", len(transactions), "total tercatat")
with col3:
    buy_signals = [s for s in signals if "BUY" in s["signal_type"]]
    st.metric("🟢 Sinyal BUY", len(buy_signals), "dari 10 terakhir")
with col4:
    sell_signals = [s for s in signals if "SELL" in s["signal_type"]]
    st.metric("🔴 Sinyal SELL", len(sell_signals), "dari 10 terakhir")

st.divider()

# ── Mulai cepat jika watchlist kosong ─────────────────────
if not watchlist:
    st.info(
        "👋 **Watchlist kamu masih kosong!** "
        "Pergi ke halaman **⚙️ Settings** untuk menambahkan saham pertamamu.",
        icon="💡"
    )
else:
    # Tampilkan ringkasan watchlist
    st.subheader("📋 Watchlist Saat Ini")
    from database.models import get_latest_price
    import pandas as pd

    rows = []
    for s in watchlist:
        latest = get_latest_price(s["ticker"])
        rows.append({
            "Ticker": s["ticker"],
            "Nama": s["name"],
            "Sektor": s["sector"],
            "Harga Terakhir": f"Rp {latest['close']:,.0f}" if latest else "—",
            "Tgl Data": latest["date"] if latest else "—",
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.caption("💡 Pergi ke **Dashboard** untuk melihat grafik lengkap.")

st.markdown("---")

with st.expander("📚 Glosarium Induk & Panduan Singkatan Saham Monitor", expanded=False):
    st.markdown("""
    Selamat datang di pusat bantuan istilah Saham Monitor. Berikut ringkasan umum seluruh singkatan penting dalam aplikasi ini:

    | Singkatan / Istilah | Kategori | Penjelasan Singkat |
    | :--- | :--- | :--- |
    | **MA (Moving Average)** | Teknikal | Garis rata-rata harga (MA20 = bulanan, MA50 = kuartalan, MA200 = tahunan / penentu tren utama). |
    | **RSI (14)** | Teknikal | *Relative Strength Index* (0 - 100). Mengukur kejenuhan: di bawah 30 = Jenuh Jual (*Oversold*), di atas 70 = Jenuh Beli (*Overbought*). |
    | **MACD** | Teknikal | *Moving Average Convergence Divergence*. Indikator momentum; histogram hijau di atas nol menunjukkan momentum pembeli menguat. |
    | **BB (Bollinger Bands)** | Teknikal | Pita batas volatilitas normal harga (Upper, Mid, dan Lower Band). |
    | **ATR** | Teknikal | *Average True Range*. Rata-rata gejolak harga harian dalam rupiah (dasar perhitungan jarak Stop Loss). |
    | **P/E & P/B Ratio** | Fundamental | Rasio valuasi harga terhadap laba (*Price to Earnings*) dan modal bersih per lembar (*Price to Book*). |
    | **ROE & DER** | Fundamental | Tingkat profitabilitas modal (*Return on Equity*) dan rasio beban utang terhadap ekuitas (*Debt to Equity*). |
    | **HAKA & HAKI** | Order Flow | *Hajar Kanan* (Beli langsung di harga antrean jual) vs *Hajar Kiri* (Jual langsung di harga antrean beli). |
    | **Unrealized / Realized P&L** | Portofolio | Keuntungan/kerugian berjalan (*floating*) vs keuntungan/kerugian nyata yang sudah dikunci dari penjualan saham. |
    """)

st.caption("⚡ Auto-refresh setiap 30 menit saat market buka (Senin–Jumat, 09:00–16:00 WIB)")
