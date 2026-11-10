# 📊 Saham Monitor 🇮🇩

Aplikasi pemantau saham IDX (Bursa Efek Indonesia) yang berjalan **lokal** di komputermu.

## ✨ Fitur

- **📊 Dashboard** — Grafik candlestick interaktif + indikator teknikal (RSI, MA, MACD, Bollinger Bands)
- **💼 Portfolio** — Catat transaksi beli/jual, hitung P&L otomatis, pie chart komposisi
- **🔬 Research** — Analisis mendalam teknikal + fundamental (PE, PBV, ROE, DER) per saham
- **🚦 Signals** — Sinyal BUY/SELL otomatis berdasarkan multi-indikator scoring
- **⚙️ Settings** — Kelola watchlist, alert rules, konfigurasi broker
- **🔔 Notifikasi desktop** otomatis saat ada sinyal beli/jual

## 🚀 Cara Menjalankan

### 1. Install Dependencies

```bash
python3 -m pip install -r requirements.txt --user --break-system-packages
```

### 2. Jalankan App

```bash
bash run.sh
```

Atau langsung:

```bash
streamlit run app.py
```

Buka browser ke **http://localhost:8501**

## 📦 Tech Stack

| Komponen | Teknologi |
|---|---|
| UI | Streamlit |
| Database | SQLite (lokal, file `stock.db`) |
| Grafik | Plotly |
| Data Harga | Yahoo Finance (`yfinance`) — ticker format `BBCA.JK` |
| Indikator | pandas-ta |
| Scheduler | APScheduler |
| Notifikasi | plyer |

## 📁 Struktur

```
saham-monitor/
├── app.py              # Entry point
├── config.py           # Konfigurasi global
├── run.sh              # Script jalankan app
├── requirements.txt
├── stock.db            # Database SQLite (auto-created)
│
├── database/
│   ├── db.py           # Init & koneksi SQLite
│   └── models.py       # CRUD operations
│
├── data/
│   ├── fetcher.py      # Ambil data dari Yahoo Finance
│   ├── fundamental.py  # Scraping fundamental dari IDX
│   └── scheduler.py    # Auto-fetch background scheduler
│
├── analysis/
│   ├── technical.py    # RSI, MA, MACD, Bollinger Bands
│   └── signals.py      # Generate sinyal BUY/SELL
│
├── notifications/
│   └── notifier.py     # Desktop notification
│
└── pages/
    ├── 01_Dashboard.py
    ├── 02_Portfolio.py
    ├── 03_Research.py
    ├── 04_Signals.py
    └── 05_Settings.py
```

## ⚠️ Catatan

- Data harga dari **Yahoo Finance** (free, tidak butuh login)
- Data fundamental dari Yahoo Finance + scraping IDX publik
- Stockbit tidak punya public API resmi, jadi tidak digunakan secara langsung
- Semua data tersimpan **lokal** di file `stock.db`
- Auto-refresh setiap **30 menit** saat market buka (09:00–16:00 WIB, Senin–Jumat)

## 📊 Indikator Teknikal

| Indikator | Sinyal BUY | Sinyal SELL |
|---|---|---|
| RSI(14) | RSI < 30 (oversold) | RSI > 70 (overbought) |
| MA Crossover | MA20 > MA50 (golden cross) | MA20 < MA50 (death cross) |
| MACD | MACD > Signal, histogram positif | MACD < Signal, histogram negatif |
| Bollinger Bands | Harga ≤ Lower Band | Harga ≥ Upper Band |

> **Disclaimer**: Aplikasi ini hanya untuk referensi pribadi. Keputusan investasi sepenuhnya menjadi tanggung jawab pengguna.
