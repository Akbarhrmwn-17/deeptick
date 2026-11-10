"""pages/05_Settings.py — Kelola watchlist, alert rules, dan konfigurasi broker"""

import streamlit as st
import pandas as pd

from database.models import (
    get_watchlist, add_to_watchlist, remove_from_watchlist,
    get_alert_rules, add_alert_rule, delete_alert_rule,
    get_setting, set_setting,
)
from data.fetcher import fetch_price_history, update_all_watchlist, fetch_fundamental_yf
from database.models import upsert_fundamental
from data.scheduler import get_scheduler_status
from config import POPULAR_STOCKS

st.set_page_config(page_title="Settings — Saham Monitor", page_icon="⚙️", layout="wide")
st.title("⚙️ Pengaturan")


tab_watch, tab_alert, tab_broker, tab_data = st.tabs([
    "📋 Watchlist", "🔔 Alert Rules", "🏦 Broker", "⚡ Data & Scheduler"
])


# ════════════════════════════════════════════════════════
# TAB WATCHLIST
# ════════════════════════════════════════════════════════
with tab_watch:
    st.subheader("📋 Kelola Watchlist")

    # Tambah dari daftar populer
    st.markdown("**Tambah dari daftar saham populer:**")
    watchlist_tickers = {s["ticker"] for s in get_watchlist()}
    popular_options = [
        f"{s['ticker']} — {s['name']}"
        for s in POPULAR_STOCKS
        if s["ticker"] not in watchlist_tickers
    ]

    if popular_options:
        selected_popular = st.selectbox("Pilih saham", ["— pilih saham —"] + popular_options)
        if st.button("➕ Tambahkan ke Watchlist", use_container_width=False):
            if selected_popular != "— pilih saham —":
                ticker = selected_popular.split(" — ")[0]
                stock_data = next((s for s in POPULAR_STOCKS if s["ticker"] == ticker), None)
                if stock_data:
                    added = add_to_watchlist(ticker, stock_data["name"], stock_data["sector"])
                    if added:
                        with st.spinner(f"Mengambil data historis {ticker}..."):
                            fetch_price_history(ticker, period="1y", save_to_db=True)
                            fund = fetch_fundamental_yf(ticker)
                            if fund:
                                upsert_fundamental(ticker, fund)
                        st.success(f"✅ {ticker} berhasil ditambahkan!")
                        st.rerun()
                    else:
                        st.warning(f"{ticker} sudah ada di watchlist.")

    st.divider()

    # Tambah manual
    with st.expander("✏️ Tambah Saham Manual"):
        col1, col2, col3 = st.columns(3)
        with col1:
            manual_ticker = st.text_input("Kode Saham (e.g. BBCA)").upper().strip()
        with col2:
            manual_name = st.text_input("Nama Perusahaan")
        with col3:
            manual_sector = st.text_input("Sektor (opsional)")

        if st.button("➕ Tambah Manual"):
            if manual_ticker and manual_name:
                added = add_to_watchlist(manual_ticker, manual_name, manual_sector)
                if added:
                    with st.spinner(f"Mengambil data {manual_ticker}..."):
                        fetch_price_history(manual_ticker, period="1y", save_to_db=True)
                    st.success(f"✅ {manual_ticker} ditambahkan!")
                    st.rerun()
                else:
                    st.warning(f"{manual_ticker} sudah ada di watchlist.")
            else:
                st.error("Isi kode saham dan nama perusahaan.")

    st.divider()

    # Daftar watchlist saat ini
    st.markdown("**Watchlist saat ini:**")
    watchlist = get_watchlist()

    if not watchlist:
        st.info("Watchlist kosong. Tambahkan saham di atas.")
    else:
        for stock in watchlist:
            col_a, col_b, col_c, col_d = st.columns([1, 3, 2, 1])
            with col_a:
                st.markdown(f"**{stock['ticker']}**")
            with col_b:
                st.markdown(stock["name"])
            with col_c:
                st.caption(stock["sector"] or "—")
            with col_d:
                if st.button("🗑️", key=f"del_{stock['ticker']}", help=f"Hapus {stock['ticker']}"):
                    remove_from_watchlist(stock["ticker"])
                    st.success(f"{stock['ticker']} dihapus dari watchlist.")
                    st.rerun()


# ════════════════════════════════════════════════════════
# TAB ALERT RULES
# ════════════════════════════════════════════════════════
with tab_alert:
    st.subheader("🔔 Atur Alert Rules")
    st.caption("Sistem akan mengirim notifikasi saat kondisi terpenuhi.")

    watchlist = get_watchlist()
    ticker_options = [s["ticker"] for s in watchlist]

    if not ticker_options:
        st.warning("Tambah saham ke watchlist dulu.")
    else:
        with st.form("form_alert"):
            col1, col2, col3 = st.columns(3)
            with col1:
                alert_ticker = st.selectbox("Saham", ticker_options)
            with col2:
                rule_type = st.selectbox("Jenis Alert", [
                    "PRICE_BELOW",    # Notif kalau harga turun ke bawah X
                    "PRICE_ABOVE",    # Notif kalau harga naik ke atas X
                    "RSI_OVERSOLD",   # Notif kalau RSI < X
                    "RSI_OVERBOUGHT", # Notif kalau RSI > X
                ])
            with col3:
                rule_value = st.number_input("Nilai Threshold", min_value=0.0, value=1000.0, step=50.0)

            rule_desc = {
                "PRICE_BELOW":    f"Notif jika harga < {rule_value:,.0f}",
                "PRICE_ABOVE":    f"Notif jika harga > {rule_value:,.0f}",
                "RSI_OVERSOLD":   f"Notif jika RSI < {rule_value:.0f} (oversold)",
                "RSI_OVERBOUGHT": f"Notif jika RSI > {rule_value:.0f} (overbought)",
            }
            st.caption(f"📝 {rule_desc.get(rule_type, '')}")

            if st.form_submit_button("➕ Simpan Alert Rule", type="primary"):
                add_alert_rule(alert_ticker, rule_type, rule_value)
                st.success(f"Alert rule ditambahkan untuk {alert_ticker}!")
                st.rerun()

        st.divider()
        st.markdown("**Alert Rules aktif:**")
        rules = get_alert_rules()

        if rules:
            for rule in rules:
                col_a, col_b, col_c, col_d = st.columns([1, 2, 2, 1])
                with col_a:
                    st.markdown(f"**{rule['ticker']}**")
                with col_b:
                    st.markdown(rule["rule_type"])
                with col_c:
                    st.markdown(f"Threshold: `{rule['value']}`")
                with col_d:
                    if st.button("🗑️", key=f"del_rule_{rule['id']}"):
                        delete_alert_rule(rule["id"])
                        st.rerun()
        else:
            st.info("Belum ada alert rule.")


# ════════════════════════════════════════════════════════
# TAB BROKER
# ════════════════════════════════════════════════════════
with tab_broker:
    st.subheader("🏦 Konfigurasi Broker")
    st.caption("Fee digunakan untuk kalkulasi P&L di Portfolio.")

    col1, col2 = st.columns(2)
    with col1:
        broker_name = st.text_input(
            "Nama Broker",
            value=get_setting("broker_name", "Default"),
        )
        buy_fee = st.number_input(
            "Fee Beli (%)",
            min_value=0.0, max_value=1.0, step=0.01,
            value=float(get_setting("buy_fee_pct", "0.0015")) * 100,
            format="%.3f",
        )

    with col2:
        sell_fee = st.number_input(
            "Fee Jual (%)",
            min_value=0.0, max_value=1.0, step=0.01,
            value=float(get_setting("sell_fee_pct", "0.0025")) * 100,
            format="%.3f",
        )
        sell_tax = st.number_input(
            "Pajak Jual (%)",
            min_value=0.0, max_value=1.0,
            value=float(get_setting("sell_tax_pct", "0.001")) * 100,
            format="%.3f",
            disabled=True,  # Pajak tetap 0.1%, diatur pemerintah
            help="Pajak penjualan saham ditetapkan pemerintah sebesar 0.1%",
        )

    st.markdown("**Fee Broker Populer di Indonesia:**")
    broker_table = pd.DataFrame([
        {"Broker": "Stockbit", "Fee Beli": "0.10%", "Fee Jual": "0.20%"},
        {"Broker": "Mirae Asset", "Fee Beli": "0.15%", "Fee Jual": "0.25%"},
        {"Broker": "BNI Sekuritas", "Fee Beli": "0.17%", "Fee Jual": "0.27%"},
        {"Broker": "Mandiri Sekuritas", "Fee Beli": "0.18%", "Fee Jual": "0.28%"},
        {"Broker": "Indo Premier (IPOT)", "Fee Beli": "0.19%", "Fee Jual": "0.29%"},
        {"Broker": "Ajaib", "Fee Beli": "0.10%", "Fee Jual": "0.20%"},
        {"Broker": "Default (umum)", "Fee Beli": "0.15%", "Fee Jual": "0.25%"},
    ])
    st.dataframe(broker_table, use_container_width=True, hide_index=True)

    if st.button("💾 Simpan Konfigurasi Broker", type="primary"):
        set_setting("broker_name", broker_name)
        set_setting("buy_fee_pct", str(buy_fee / 100))
        set_setting("sell_fee_pct", str(sell_fee / 100))
        st.success("✅ Konfigurasi broker tersimpan!")


# ════════════════════════════════════════════════════════
# TAB DATA & SCHEDULER
# ════════════════════════════════════════════════════════
with tab_data:
    st.subheader("⚡ Manajemen Data")

    # Scheduler Status
    status = get_scheduler_status()
    if status["running"]:
        st.success("🟢 Scheduler aktif (auto-fetch setiap 30 menit saat market buka)")
        for job in status["jobs"]:
            st.caption(f"• Job `{job['id']}` — next run: {job['next_run']}")
    else:
        st.warning("🟡 Scheduler tidak aktif. Restart app untuk mengaktifkan.")

    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Update Data Sekarang**")
        period_opts = {"5 Hari": "5d", "1 Bulan": "1mo", "3 Bulan": "3mo",
                       "6 Bulan": "6mo", "1 Tahun": "1y", "2 Tahun": "2y"}
        fetch_period = st.selectbox("Periode fetch", list(period_opts.keys()), index=4)

        if st.button("🔄 Update Semua Saham", use_container_width=True, type="primary"):
            watchlist = get_watchlist()
            if not watchlist:
                st.warning("Watchlist kosong.")
            else:
                progress_bar = st.progress(0)
                status_text = st.empty()
                for i, s in enumerate(watchlist):
                    status_text.text(f"Fetching {s['ticker']}...")
                    fetch_price_history(s["ticker"], period=period_opts[fetch_period], save_to_db=True)
                    fund = fetch_fundamental_yf(s["ticker"])
                    if fund:
                        upsert_fundamental(s["ticker"], fund)
                    progress_bar.progress((i+1) / len(watchlist))
                status_text.text("✅ Selesai!")
                st.success(f"Data {len(watchlist)} saham berhasil diperbarui!")

    with col2:
        st.markdown("**Export Database**")
        watchlist = get_watchlist()

        if watchlist:
            # Export watchlist
            df_wl = pd.DataFrame(watchlist)
            st.download_button(
                "📥 Export Watchlist (CSV)",
                df_wl.to_csv(index=False).encode("utf-8"),
                file_name="watchlist.csv", mime="text/csv",
            )

            # Export all transactions
            from database.models import get_all_transactions
            txs = get_all_transactions()
            if txs:
                df_tx = pd.DataFrame(txs)
                st.download_button(
                    "📥 Export Transaksi (CSV)",
                    df_tx.to_csv(index=False).encode("utf-8"),
                    file_name="transaksi.csv", mime="text/csv",
                )

st.markdown("---")

with st.expander("📚 Glosarium Konfigurasi & Aturan Alert (Settings)", expanded=False):
    st.markdown("""
    Berikut penjelasan opsi pengaturan dan istilah alert rule:

    | Pengaturan / Opsi | Penjelasan & Cara Kerja |
    | :--- | :--- |
    | **PRICE_BELOW** | Peringatan jika harga saham turun menembus ke bawah target harga yang kamu tentukan (cocok untuk pasang target antrian beli murah). |
    | **PRICE_ABOVE** | Peringatan jika harga saham naik menembus ke atas target harga yang kamu tentukan (cocok untuk target take profit / jual). |
    | **RSI_OVERSOLD** | Notifikasi terpicu jika indikator RSI (14) turun di bawah nilai tertentu (misal < 30), menandakan harga sudah jenuh jual. |
    | **RSI_OVERBOUGHT** | Notifikasi terpicu jika indikator RSI (14) naik di atas nilai tertentu (misal > 70), menandakan harga sudah jenuh beli. |
    | **Fee Beli & Jual** | Persentase komisi broker sekuritas yang dipotong otomatis saat transaksi terjadi. Nilai ini dipakai untuk menghitung Average Price dan Net P&L riil di menu Portofolio. |
    | **Pajak Jual (0.1%)** | PPh Final Pasal 4 Ayat 2 yang wajib disetor ke negara atas setiap transaksi penjualan saham di bursa efek. |
    | **Scheduler (Auto-Fetch)** | Sistem otomatisasi background yang aktif pada hari kerja bursa (Senin - Jumat, 09:00 - 16:00 WIB) untuk memperbarui candle harga dan mengecek sinyal setiap 30 menit. |
    """)
