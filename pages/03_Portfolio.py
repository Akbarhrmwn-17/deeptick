"""pages/02_Portfolio.py — Catatan transaksi beli/jual + kalkulasi P&L"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime

from database.models import (
    add_transaction, delete_transaction,
    get_all_transactions, get_portfolio_summary, get_realized_pl,
    get_watchlist, get_latest_price,
)
from config import LOT_SIZE, DEFAULT_BUY_FEE_PCT, DEFAULT_SELL_FEE_PCT, SELL_TAX_PCT, TZ
from data.fetcher import fetch_price_history, fetch_realtime_price

st.set_page_config(page_title="Portfolio — Saham Monitor", page_icon="💼", layout="wide")

holdings = get_portfolio_summary()
realized = get_realized_pl()

# ── Header & Tombol Refresh ───────────────────────────────
col_title, col_btn = st.columns([3, 1])
with col_title:
    st.title("💼 Portfolio & Buku Kas")
with col_btn:
    st.write("")
    if st.button("🔄 Refresh Harga Pasar", type="primary", use_container_width=True):
        with st.spinner("Mengambil harga terkini dari bursa..."):
            for h in holdings:
                fetch_price_history(h["ticker"], period="5d", save_to_db=True)
        st.success("Harga pasar berhasil diperbarui!")
        st.rerun()


# ════════════════════════════════════════════════════════
# SUMMARY METRICS
# ════════════════════════════════════════════════════════
now_jkt = datetime.now(TZ)
today_str = now_jkt.strftime("%Y-%m-%d")
is_market_day = now_jkt.weekday() < 5

total_invested = 0
total_market_value = 0

rows_hold = []
for h in holdings:
    ticker = h["ticker"]
    latest = get_latest_price(ticker)

    # Auto-fetch jika data di DB belum mencakup hari ini pada hari bursa aktif
    if (latest is None or str(latest.get("date"))[:10] != today_str) and is_market_day:
        try:
            fetch_price_history(ticker, period="5d", save_to_db=True)
            latest = get_latest_price(ticker)
        except Exception:
            pass

    current_price = latest["close"] if latest else h["avg_price"]
    price_date = str(latest["date"])[:10] if latest else "N/A"
    shares = h["net_lot"] * LOT_SIZE
    cost_value = h["avg_price"] * shares
    market_value = current_price * shares
    unrealized_pl = market_value - cost_value
    unrealized_pct = (unrealized_pl / cost_value * 100) if cost_value else 0

    total_invested += cost_value
    total_market_value += market_value

    rows_hold.append({
        "Ticker":         ticker,
        "Lot":            h["net_lot"],
        "Lembar":         shares,
        "Avg Price":      h["avg_price"],
        "Harga Sekarang": current_price,
        "Nilai Modal":    cost_value,
        "Nilai Pasar":    market_value,
        "Unrealized P&L": unrealized_pl,
        "Return %":       unrealized_pct,
        "Tanggal Harga":  price_date,
    })

total_unrealized = total_market_value - total_invested
total_realized = sum(r["realized_pl"] for r in realized)

st.subheader("📊 Ringkasan Portfolio")
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("💵 Total Modal", f"Rp {total_invested:,.0f}")
with col2:
    st.metric("📈 Nilai Pasar", f"Rp {total_market_value:,.0f}",
              f"{((total_market_value/total_invested - 1)*100):+.2f}%" if total_invested else "—")
with col3:
    st.metric("📊 Unrealized P&L",
              f"Rp {total_unrealized:,.0f}",
              delta=f"{'↑' if total_unrealized >= 0 else '↓'} {abs(total_unrealized):,.0f}")
with col4:
    st.metric("✅ Realized P&L", f"Rp {total_realized:,.0f}")

st.divider()


# ════════════════════════════════════════════════════════
# HOLDINGS TABLE
# ════════════════════════════════════════════════════════
if rows_hold:
    st.subheader("📋 Posisi Saat Ini (Holdings)")
    df_hold = pd.DataFrame(rows_hold)

    def color_pl(val):
        if isinstance(val, float):
            color = "#00C853" if val >= 0 else "#D50000"
            return f"color: {color}"
        return ""

    # Gunakan .map (Pandas >= 2.1) atau fallback .applymap
    styler_obj = df_hold.style.format({
        "Avg Price": "Rp {:,.2f}",
        "Harga Sekarang": "Rp {:,.0f}",
        "Nilai Modal": "Rp {:,.0f}",
        "Nilai Pasar": "Rp {:,.0f}",
        "Unrealized P&L": "Rp {:+,.0f}",
        "Return %": "{:+.2f}%",
    })
    if hasattr(styler_obj, "map"):
        styled = styler_obj.map(color_pl, subset=["Unrealized P&L", "Return %"])
    else:
        styled = styler_obj.applymap(color_pl, subset=["Unrealized P&L", "Return %"])

    st.dataframe(styled, use_container_width=True, hide_index=True)

    # Pie Chart Komposisi
    col_pie1, col_pie2 = st.columns(2)
    with col_pie1:
        fig_pie = px.pie(
            df_hold, values="Nilai Pasar", names="Ticker",
            title="Komposisi Portfolio (Nilai Pasar)",
            color_discrete_sequence=px.colors.qualitative.Set3,
            hole=0.35,
        )
        fig_pie.update_layout(template="plotly_dark", height=350, margin=dict(t=40, b=0))
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_pie2:
        fig_bar = px.bar(
            df_hold, x="Ticker", y="Return %",
            title="Return % per Saham",
            color="Return %",
            color_continuous_scale=["#D50000", "#FFD740", "#00C853"],
            text_auto=".2f",
        )
        fig_bar.update_layout(template="plotly_dark", height=350, margin=dict(t=40, b=0))
        st.plotly_chart(fig_bar, use_container_width=True)

else:
    st.info("Belum ada posisi terbuka. Tambah transaksi BUY di bawah.")


st.divider()


# ════════════════════════════════════════════════════════
# TAMBAH / IMPORT TRANSAKSI
# ════════════════════════════════════════════════════════
st.subheader("➕ Catat Transaksi (Input Cepat / Import)")

tab_paste, tab_pdf, tab_manual, tab_import = st.tabs([
    "📋 1. Sinkron Porto Aktif (Copy-Paste Stockbit)",
    "📧 2. Import PDF Transaksi (Trade Confirmation)",
    "✍️ 3. Input Manual (Form)",
    "📥 4. Upload File (CSV / Excel)"
])

# ─────────────────────────────────────────────────────────
# TAB 1: Sinkron Porto Aktif (Copy-Paste dari Layar Stockbit)
# ─────────────────────────────────────────────────────────
with tab_paste:
    st.markdown("""
    ### 📋 Sinkronisasi Posisi Portofolio Saat Ini (Paling Praktis! ⭐)
    
    Tab ini khusus untuk menyinkronkan **posisi kepemilikan sahammu yang sedang aktif saat ini** (Holdings) langsung dari layar web Stockbit, tanpa perlu file atau tombol export!
    
    **Langkah-langkah mudah:**
    1. Buka tab browser **Stockbit** kamu (halaman Portfolio yang sedang terbuka)
    2. **Blok / sorot** tabel sahammu dengan mouse (mulai dari emiten pertama sampai baris terakhir)
    3. Tekan **Ctrl + C** (Copy)
    4. Klik kotak di bawah lalu tekan **Ctrl + V** (Paste) ➔ Data langsung terdeteksi otomatis!
    
    *💡 Format singkat seperti `BBCA 10 lot 5900` atau `GOTO 50 25` juga didukung.*
    """)
    pasted_text = st.text_area(
        "Tempel (Paste) Tabel Portofolio Stockbit di sini:",
        height=160,
        placeholder="Tempel tabel hasil copy dari Stockbit di sini...\nContoh:\nBTEK    75    75    16.69    11    125,187    82,500    -42,687    -34.10%\nGOTO    16    16    65.09    25    104,156    40,000    -64,156    -61.60%"
    )

    if pasted_text.strip():
        from data.stockbit_importer import parse_pasted_text
        from database.models import add_to_watchlist
        
        parsed_items, parse_errs = parse_pasted_text(pasted_text)
        
        if parsed_items:
            st.success(f"🎉 Terdeteksi **{len(parsed_items)} saham** dari data yang kamu tempel!")
            
            # Format preview
            preview_rows = []
            for item in parsed_items:
                modal = item["lot"] * 100 * item["price"]
                preview_rows.append({
                    "Saham": item["ticker"],
                    "Tipe": item["type"],
                    "Jumlah (Lot)": f"{item['lot']:,}",
                    "Harga Rata-Rata": f"Rp {item['price']:,.2f}",
                    "Estimasi Modal": f"Rp {modal:,.0f}",
                    "Catatan": item.get("notes", "Input Cepat")
                })
            
            st.dataframe(pd.DataFrame(preview_rows), use_container_width=True, hide_index=True)
            
            if parse_errs:
                with st.expander(f"⚠️ {len(parse_errs)} catatan kecil"):
                    for e in parse_errs:
                        st.caption(e)
            
            col_save_p, col_clear_p = st.columns([2, 1])
            with col_save_p:
                if st.button("🚀 Konfirmasi & Simpan ke Portofolio", type="primary", use_container_width=True):
                    saved = 0
                    for item in parsed_items:
                        add_transaction(
                            ticker=item["ticker"],
                            tx_type=item["type"],
                            date=item["date"],
                            lot=item["lot"],
                            price=item["price"],
                            fee=item.get("fee", 0.0),
                            tax=item.get("tax", 0.0),
                            notes=item.get("notes", "Input Cepat")
                        )
                        add_to_watchlist(item["ticker"], item["ticker"])
                        saved += 1
                    st.success(f"🎉 Sukses! {saved} saham berhasil dimasukkan ke Portofolio & Watchlist!")
                    st.balloons()
                    st.rerun()
            with col_clear_p:
                st.caption("Data akan otomatis masuk ke perhitungan P&L dan grafik portofolio.")
        else:
            st.warning("""
            ⚠️ **Belum ada saham yang terdeteksi.**
            
            Di dalam kotak teks saat ini baru ada **judul/header tabel saja** (`Symbol, Balance Lot, Invested...`).
            Pastikan kamu menyalin (copy) **baris nama sahamnya juga** (seperti `BTEK`, `GOTO`, `MEJA`, `PJHB`, `TAYS`) dari layar Stockbit.
            """)


# ─────────────────────────────────────────────────────────
# TAB 2: PDF Trade Confirmation / e-Statement
# ─────────────────────────────────────────────────────────
with tab_pdf:
    st.markdown("""
    ### 📧 Import dari PDF Bukti Transaksi (Trade Confirmation)
    
    Tab ini khusus untuk mengunggah file **PDF Trade Confirmation (TC)** atau **e-Statement bulanan** yang dikirimkan Stockbit ke email kamu sebagai bukti riwayat eksekusi jual/beli.
    
    **Langkah-langkah:**
    1. Buka **Gmail** kamu → cari email pengirim **Stockbit** (lampiran `TC_xxxx.pdf`)
    2. Download file PDF-nya ke laptop
    3. Upload di kotak bawah ini → sistem membaca otomatis rincian lot, harga, fee broker, dan pajak!
    """)

    st.divider()
    uploaded_pdf = st.file_uploader(
        "📂 Pilih file PDF Trade Confirmation / e-Statement Stockbit",
        type=["pdf"],
        help="File PDF bukti transaksi yang dikirim Stockbit via email"
    )

    if uploaded_pdf is not None:
        from data.pdf_parser import parse_stockbit_pdf
        from database.models import add_to_watchlist

        pdf_bytes = uploaded_pdf.read()
        file_size_kb = len(pdf_bytes) / 1024

        st.info(f"📄 File: **{uploaded_pdf.name}** ({file_size_kb:.1f} KB) — Sedang diproses...")

        with st.spinner("🔍 Membaca & menganalisis isi PDF..."):
            transactions, errors, meta = parse_stockbit_pdf(pdf_bytes)

        # Tampilkan metadata PDF
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            st.metric("📄 Tipe Dokumen", meta.get("doc_type", "Trade Confirmation"))
        with col_m2:
            st.metric("✅ Transaksi Ditemukan", len(transactions))
        with col_m3:
            st.metric("⚠️ Peringatan", len(errors))

        if meta.get("client_name"):
            st.caption(f"👤 Nasabah: **{meta['client_name']}**")
        if meta.get("tx_date"):
            st.caption(f"📅 Tanggal Transaksi: **{meta['tx_date']}**")

        if errors:
            with st.expander(f"⚠️ {len(errors)} peringatan (klik untuk lihat detail)", expanded=False):
                for err in errors:
                    st.warning(err)

        if not transactions:
            st.error("❌ Tidak ada transaksi saham yang berhasil terbaca dari PDF ini.")
        else:
            st.success(f"🎉 Berhasil membaca **{len(transactions)} transaksi** dari PDF!")

            # Preview tabel transaksi
            df_pdf = pd.DataFrame(transactions)[["date", "ticker", "type", "lot", "price", "fee", "tax", "notes"]]
            df_pdf.columns = ["Tanggal", "Saham", "Tipe", "Lot", "Harga (Rp)", "Fee (Rp)", "Pajak (Rp)", "Keterangan"]
            df_pdf["Harga (Rp)"] = df_pdf["Harga (Rp)"].apply(lambda x: f"Rp {x:,.0f}")
            df_pdf["Fee (Rp)"] = df_pdf["Fee (Rp)"].apply(lambda x: f"Rp {x:,.0f}")
            df_pdf["Pajak (Rp)"] = df_pdf["Pajak (Rp)"].apply(lambda x: f"Rp {x:,.0f}")

            st.dataframe(df_pdf, use_container_width=True, hide_index=True)

            col_save, col_cancel = st.columns([2, 1])
            with col_save:
                if st.button("🚀 Konfirmasi & Simpan Transaksi ke Buku Kas", type="primary", use_container_width=True):
                    saved_count = 0
                    for row in transactions:
                        try:
                            add_transaction(
                                ticker=row["ticker"],
                                tx_type=row["type"],
                                date=row["date"],
                                lot=row["lot"],
                                price=row["price"],
                                fee=row.get("fee", 0.0),
                                tax=row.get("tax", 0.0),
                                notes=row.get("notes", "Import PDF Trade Confirmation")
                            )
                            add_to_watchlist(row["ticker"], row["ticker"])
                            saved_count += 1
                        except Exception as e:
                            st.error(f"Gagal simpan {row['ticker']}: {str(e)}")
                    if saved_count > 0:
                        st.success(f"✅ {saved_count} transaksi berhasil dicatat ke Buku Kas!")
                        st.balloons()
                        st.rerun()
            with col_cancel:
                st.info("💡 PDF asli dapat dihapus setelah import selesai — data sudah tersimpan di database lokal.")


with tab_import:
    st.markdown("""
    **Cara Import dari Stockbit:**
    1. Buka aplikasi/web Stockbit ➔ Masuk ke menu **Portofolio** atau **Order History / Trade Confirmation**.
    2. Klik **Export / Download** file laporan (.csv atau .xlsx).
    3. Upload filenya di kotak bawah ini:
    """)
    uploaded_file = st.file_uploader(
        "Pilih file laporan Stockbit / Catatan Portofolio",
        type=["csv", "xlsx", "xls"],
        help="Sistem otomatis mengenali kolom Ticker, Buy/Sell, Lot, dan Harga."
    )

    if uploaded_file is not None:
        from data.stockbit_importer import parse_stockbit_file
        from database.models import add_to_watchlist
        from data.fetcher import fetch_price_history

        parsed_rows, parse_errors = parse_stockbit_file(uploaded_file, uploaded_file.name)
        if parse_errors and not parsed_rows:
            st.error("Terjadi kendala saat membaca file:")
            for err in parse_errors:
                st.write(f"- {err}")
        elif parsed_rows:
            st.success(f"🎉 Berhasil membaca **{len(parsed_rows)} transaksi** dari file!")
            df_preview = pd.DataFrame(parsed_rows)[["date", "ticker", "type", "lot", "price", "fee"]]
            st.dataframe(df_preview, use_container_width=True, hide_index=True)

            if st.button("🚀 Konfirmasi & Simpan Semua Transaksi ke Portofolio", type="primary"):
                saved_count = 0
                for row in parsed_rows:
                    add_transaction(
                        ticker=row["ticker"],
                        tx_type=row["type"],
                        date=row["date"],
                        lot=row["lot"],
                        price=row["price"],
                        fee=row["fee"],
                        tax=row["tax"],
                        notes=row["notes"]
                    )
                    # Otomatis tambahkan ke watchlist jika belum ada
                    add_to_watchlist(row["ticker"], row["ticker"])
                    saved_count += 1
                st.success(f"✅ Berhasil memasukkan {saved_count} transaksi ke dalam database!")
                st.rerun()

with tab_manual:
    watchlist = get_watchlist()
    ticker_options = [s["ticker"] for s in watchlist]

    with st.form("form_transaksi", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            tx_ticker = st.selectbox("Saham", ticker_options)
            tx_type = st.radio("Tipe", ["BUY", "SELL"], horizontal=True)
        with col2:
            tx_date = st.date_input("Tanggal", value=date.today())
            tx_lot = st.number_input("Jumlah Lot", min_value=1, value=1, step=1)
        with col3:
            tx_price = st.number_input("Harga per Lembar (Rp)", min_value=1, value=1000, step=10)
            tx_notes = st.text_input("Catatan (opsional)")

        # Kalkulasi preview
        total_val = tx_lot * LOT_SIZE * tx_price
        fee_pct = DEFAULT_BUY_FEE_PCT if tx_type == "BUY" else DEFAULT_SELL_FEE_PCT
        fee = round(total_val * fee_pct, 0)
        tax = round(total_val * SELL_TAX_PCT, 0) if tx_type == "SELL" else 0
        total_net = total_val + fee + tax

        st.markdown(f"""
        **Preview:**
        - Nilai transaksi: `Rp {total_val:,.0f}`  ({tx_lot} lot × {LOT_SIZE} lembar × Rp {tx_price:,.0f})
        - Fee broker ({fee_pct*100:.2f}%): `Rp {fee:,.0f}`
        - Pajak jual (0.1%): `Rp {tax:,.0f}`
        - **Total bersih: `Rp {total_net:,.0f}`**
        """)

        submitted = st.form_submit_button(
            f"✅ Simpan Transaksi {tx_type}",
            use_container_width=True,
            type="primary",
        )

        if submitted:
            if not tx_ticker:
                st.error("Pilih saham terlebih dahulu.")
            else:
                add_transaction(
                    ticker=tx_ticker,
                    tx_type=tx_type,
                    date=str(tx_date),
                    lot=tx_lot,
                    price=tx_price,
                    fee=fee,
                    tax=tax,
                    notes=tx_notes,
                )
                try:
                    fetch_price_history(tx_ticker, period="5d", save_to_db=True)
                except Exception:
                    pass
                st.success(f"✅ Transaksi {tx_type} {tx_lot} lot {tx_ticker} @ Rp {tx_price:,.0f} berhasil disimpan!")
                st.rerun()



st.divider()


# ════════════════════════════════════════════════════════
# RIWAYAT TRANSAKSI
# ════════════════════════════════════════════════════════
st.subheader("📜 Riwayat Transaksi")

all_tx = get_all_transactions()
if all_tx:
    df_tx = pd.DataFrame(all_tx)
    df_tx["total_value"] = df_tx["lot"] * LOT_SIZE * df_tx["price"]
    df_tx["net_value"] = df_tx["total_value"] + df_tx["fee"] + df_tx["tax"]

    # Filter
    col_f1, col_f2 = st.columns([1, 3])
    with col_f1:
        filter_type = st.selectbox("Filter Tipe", ["Semua", "BUY", "SELL"])
    with col_f2:
        filter_ticker = st.multiselect("Filter Saham", options=sorted(df_tx["ticker"].unique()))

    if filter_type != "Semua":
        df_tx = df_tx[df_tx["type"] == filter_type]
    if filter_ticker:
        df_tx = df_tx[df_tx["ticker"].isin(filter_ticker)]

    display_cols = {
        "id": "ID", "date": "Tanggal", "ticker": "Saham",
        "type": "Tipe", "lot": "Lot", "price": "Harga",
        "fee": "Fee", "tax": "Pajak", "net_value": "Total Bersih", "notes": "Catatan"
    }
    df_display = df_tx[[c for c in display_cols if c in df_tx.columns]].copy()
    df_display.rename(columns=display_cols, inplace=True)

    st.dataframe(
        df_display.style.format({
            "Harga": "Rp {:,.0f}",
            "Fee": "Rp {:,.0f}",
            "Pajak": "Rp {:,.0f}",
            "Total Bersih": "Rp {:,.0f}",
        }),
        use_container_width=True, hide_index=True,
    )

    # Export CSV
    csv = df_tx.to_csv(index=False).encode("utf-8")
    st.download_button(
        "📥 Export ke CSV", csv,
        file_name=f"transaksi_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
    )

    # Hapus transaksi
    with st.expander("🗑️ Hapus Transaksi"):
        del_id = st.number_input("Masukkan ID transaksi yang ingin dihapus", min_value=1, step=1)
        if st.button("Hapus", type="secondary"):
            delete_transaction(int(del_id))
            st.success(f"Transaksi ID {del_id} dihapus.")
            st.rerun()
else:
    st.info("Belum ada transaksi tercatat.")

st.markdown("---")

with st.expander("📚 Glosarium & Penjelasan Istilah Portofolio / Buku Kas", expanded=False):
    st.markdown("""
    Berikut panduan memahami istilah dan singkatan yang ada di halaman Portofolio:

    | Istilah / Singkatan | Kepanjangan / Arti | Penjelasan Detail |
    | :--- | :--- | :--- |
    | **Lot** | Satuan Perdagangan Saham | Di Bursa Efek Indonesia (IDX), 1 Lot setara dengan **100 lembar saham**. Jumlah di bawah 100 lembar disebut *Odd Lot*. |
    | **Avg Price** | *Average Price* (Harga Rata-Rata) | Rata-rata modal per lembar saham yang kamu bayarkan (termasuk biaya transaksi/fee broker jika dicatat). Rumus: *(Total Modal Dibeli + Fee) ÷ Total Lembar Dimiliki*. |
    | **Harga Sekarang** | *Current / Last Market Price* | Harga penutupan terkini dari saham tersebut di bursa. |
    | **Nilai Modal (Cost Value)** | *Total Invested / Capital* | Total uang yang kamu keluarkan untuk membeli posisi saham yang masih dipegang saat ini. Rumus: *Avg Price × Total Lembar*. |
    | **Nilai Pasar (Market Value)** | *Current Position Value* | Nilai uang jika seluruh saham yang kamu miliki saat ini dicairkan/dijual pada harga sekarang. Rumus: *Harga Sekarang × Total Lembar*. |
    | **Unrealized P&L** | *Unrealized Profit & Loss (Floating)* | Potensi keuntungan atau kerugian berjalan (belum terealisasi karena sahamnya belum dijual). Berwarna **Hijau (+)** jika untung, dan **Merah (-)** jika rugi (*floating loss*). |
    | **Realized P&L** | *Realized Profit & Loss (Nett)* | Keuntungan atau kerugian nyata yang sudah dikunci dari transaksi penjualan saham yang telah selesai (dikurangi fee broker dan pajak). |
    | **Return %** | Persentase Keuntungan/Kerugian | Performa imbal hasil posisi sahammu. Rumus: *(Unrealized P&L ÷ Nilai Modal) × 100%*. |
    | **Broker Fee** | Komisi Pialang / Sekuritas | Biaya jasa sekuritas (Stockbit dll). Rata-rata beli: ~0.10% - 0.15%, jual: ~0.20% - 0.25%. |
    | **Pajak Jual (PPh Final)** | Pajak Penjualan Saham | Pajak penghasilan final yang ditetapkan pemerintah sebesar **0.1%** dari total nilai transaksi penjualan. |
    """)
