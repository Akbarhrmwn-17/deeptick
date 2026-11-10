"""pages/06_Running_Trade.py — Running Trade Real-Time ala Stockbit"""

import streamlit as st
import pandas as pd
from datetime import datetime
import pytz

from database.models import get_watchlist
from data.running_trade import fetch_live_market_ticks
from config import APP_NAME

st.set_page_config(page_title="Running Trade — Saham Monitor", page_icon="⚡", layout="wide")

# CSS Styling khusus tampilan Running Trade Stockbit
st.markdown("""
<style>
.rt-container {
    font-family: 'Courier New', Courier, monospace;
    background-color: #0b0e14;
    border: 1px solid #1e2638;
    border-radius: 8px;
    padding: 12px;
}
.rt-row {
    display: flex;
    justify-content: space-between;
    padding: 6px 10px;
    border-bottom: 1px solid #161c27;
    font-size: 0.95rem;
}
.rt-row:hover {
    background-color: #151c2c;
}
.text-green { color: #00E676; font-weight: bold; }
.text-red   { color: #FF5252; font-weight: bold; }
.text-gray  { color: #90A4AE; }
.badge-buy  { background: #00C85322; color: #00E676; padding: 2px 8px; border-radius: 4px; font-weight: bold; }
.badge-sell { background: #D5000022; color: #FF5252; padding: 2px 8px; border-radius: 4px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

st.title("⚡ Running Trade (Live Feed IDX)")
st.caption("Memantau arus transaksi jual-beli real-time dari seluruh saham di Watchlist & Bursa.")

# ── Controls Header ───────────────────────────────────────
col_c1, col_c2, col_c3, col_c4 = st.columns([2, 2, 2, 2])

watchlist = get_watchlist()
all_tickers = sorted(list(set([s["ticker"] for s in watchlist] + ["BBCA", "BBRI", "BMRI", "TLKM", "ASII", "GOTO", "MEJA", "BTEK", "MIKA", "RANS", "TAYS"])))

with col_c1:
    filter_stock = st.multiselect("🔍 Filter Saham (Code)", options=all_tickers, default=[])
with col_c2:
    filter_action = st.selectbox("Action", ["Semua Transaksi", "Hanya BUY (Haka)", "Hanya SELL (Haki)"])
with col_c3:
    min_lot = st.number_input("Minimal Lot", min_value=0, value=0, step=10)
with col_c4:
    st.write("")
    st.write("")
    refresh_btn = st.button("🔄 Refresh Data Tiket", type="primary", use_container_width=True)

# ── Fetch Data ───────────────────────────────────────────
query_tickers = filter_stock if filter_stock else all_tickers
ticks = fetch_live_market_ticks(query_tickers)

# Filter logic
if filter_action == "Hanya BUY (Haka)":
    ticks = [t for t in ticks if t["action"] == "Buy"]
elif filter_action == "Hanya SELL (Haki)":
    ticks = [t for t in ticks if t["action"] == "Sell"]

if min_lot > 0:
    ticks = [t for t in ticks if t["lot"] >= min_lot]

# ── Summary Metrics ───────────────────────────────────────
col_m1, col_m2, col_m3, col_m4 = st.columns(4)
total_ticks = len(ticks)
buy_count = sum(1 for t in ticks if t["action"] == "Buy")
sell_count = sum(1 for t in ticks if t["action"] == "Sell")
total_vol_lot = sum(t["lot"] for t in ticks)

with col_m1:
    st.metric("Total Transaksi Terpantau", f"{total_ticks} Ticks")
with col_m2:
    st.metric("Aksi BUY (HAKA)", f"{buy_count} Ticks", f"{(buy_count/total_ticks*100):.1f}%" if total_ticks else "0%")
with col_m3:
    st.metric("Aksi SELL (HAKI)", f"{sell_count} Ticks", f"{(sell_count/total_ticks*100):.1f}%" if total_ticks else "0%")
with col_m4:
    st.metric("Total Volume Lot", f"{total_vol_lot:,.0f} Lot")

st.divider()

# ── Running Trade Feed Table ─────────────────────────────
if not ticks:
    st.info("Belum ada data transaksi yang sesuai filter saat ini.")
else:
    # Header Tabel ala Stockbit
    st.markdown("""
    <div style="display:flex; justify-content:space-between; padding:8px 12px; background:#121722; font-weight:bold; color:#8892b0; border-radius:6px; margin-bottom:6px;">
        <span style="width:12%;">TIME</span>
        <span style="width:15%;">CODE</span>
        <span style="width:18%;">PRICE</span>
        <span style="width:15%;">ACTION</span>
        <span style="width:15%;">LOT</span>
        <span style="width:15%;">VAL</span>
        <span style="width:10%;">MARKET</span>
    </div>
    """, unsafe_allow_html=True)

    rows_html = []
    for t in ticks:
        color_class = "text-green" if t["change"] > 0 else ("text-red" if t["change"] < 0 else "text-gray")
        badge_class = "badge-buy" if t["action"] == "Buy" else "badge-sell"
        sign = "+" if t["change"] > 0 else ""

        # Hindari leading indentation agar Streamlit markdown tidak menganggapnya kode teks <pre><code>
        row = (
            f'<div class="rt-row">'
            f'<span style="width:12%; color:#8892b0;">{t["time"]}</span>'
            f'<span style="width:15%; font-weight:bold; color:#ffffff;">{t["code"]}</span>'
            f'<span style="width:18%;" class="{color_class}">{t["price"]:,.0f} ({sign}{t["change"]}%)</span>'
            f'<span style="width:15%;"><span class="{badge_class}">{t["action"].upper()}</span></span>'
            f'<span style="width:15%; font-weight:bold; color:#e6edf3;">{t["lot"]:,}</span>'
            f'<span style="width:15%; color:#82aaff;">{t["val"]}</span>'
            f'<span style="width:10%; color:#546e7a;">RG</span>'
            f'</div>'
        )
        rows_html.append(row)

    container_html = f'<div class="rt-container">{"".join(rows_html)}</div>'
    st.markdown(container_html, unsafe_allow_html=True)

st.caption("Data diperbarui berdasarkan pergerakan tick real-time bursa IDX. Klik **Refresh Data Tiket** untuk update terbaru.")

st.markdown("---")

with st.expander("📚 Glosarium Istilah Running Trade & Pasar Saham", expanded=False):
    st.markdown("""
    Berikut panduan istilah yang digunakan pada Running Trade pasar saham bursa:

    | Istilah / Kolom | Kepanjangan / Arti | Penjelasan Detail |
    | :--- | :--- | :--- |
    | **TIME** | Waktu Eksekusi | Jam, menit, dan detik saat order beli dan jual saling cocok (*matched*) di sistem bursa. |
    | **CODE** | Kode Ticker Emiten | 4 huruf unik kode saham perusahaan tercatat di BEI (contoh: BBCA, GOTO, MEJA, BTEK). |
    | **PRICE** | Harga Transaksi | Harga per lembar saham pada saat transaksi tersebut terjadi beserta persentase kenaikan/penurunannya dibanding penutupan kemarin (*Previous Close*). |
    | **ACTION** | Aksi Perdagangan | • **BUY (HAKA - Hajar Kanan)**: Pembeli langsung membeli di harga antrean jual (*Ask/Offer*). Tanda agresi beli.<br>• **SELL (HAKI - Hajar Kiri)**: Penjual langsung membuang saham di harga antrean beli (*Bid*). Tanda agresi jual. |
    | **LOT** | Jumlah Volume Lot | Volume transaksi dalam satuan lot (1 Lot = 100 lembar saham). |
    | **VAL** | *Transaction Value* | Total nominal nilai transaksi uang dalam rupiah:<br>• **K** = Ribu (*Thousand*)<br>• **M** = Juta (*Million*)<br>• **B** = Miliar (*Billion*). |
    | **RG / MARKET** | Pasar Reguler | Pasar reguler bursa tempat perdagangan saham dengan mekanisme lelang tawar-menawar secara berkelanjutan (satuan minimum 1 lot dengan penyelesaian T+2). |
    """)
