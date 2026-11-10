# config.py — Konfigurasi global aplikasi

import pytz

# ── App ──────────────────────────────────────────────────
APP_NAME = "Deeptick Terminal ⚡"
APP_VERSION = "1.0.0"
DB_PATH = "stock.db"

# ── Timezone ─────────────────────────────────────────────
TZ = pytz.timezone("Asia/Jakarta")

# ── Market Hours (WIB) ───────────────────────────────────
MARKET_OPEN_HOUR = 9
MARKET_CLOSE_HOUR = 16

# ── Yahoo Finance ─────────────────────────────────────────
YF_SUFFIX = ".JK"           # Suffix untuk saham IDX
YF_DEFAULT_PERIOD = "1y"    # Periode historis default

# ── Broker Defaults (bisa diubah di Settings) ────────────
DEFAULT_BUY_FEE_PCT = 0.0015    # 0.15%
DEFAULT_SELL_FEE_PCT = 0.0025   # 0.25%
SELL_TAX_PCT = 0.001            # 0.1% pajak jual
LOT_SIZE = 100                  # 1 lot = 100 lembar

# ── Technical Analysis Defaults ───────────────────────────
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
MA_SHORT = 20
MA_MID = 50
MA_LONG = 200
BB_PERIOD = 20
BB_STD = 2
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# ── Scheduler ─────────────────────────────────────────────
FETCH_INTERVAL_MINUTES = 30   # Refresh setiap 30 menit saat market buka

# ── Saham IDX Populer (untuk autocomplete) ───────────────
POPULAR_STOCKS = [
    {"ticker": "BBCA", "name": "Bank Central Asia Tbk", "sector": "Keuangan"},
    {"ticker": "BBRI", "name": "Bank Rakyat Indonesia Tbk", "sector": "Keuangan"},
    {"ticker": "BMRI", "name": "Bank Mandiri Tbk", "sector": "Keuangan"},
    {"ticker": "TLKM", "name": "Telkom Indonesia Tbk", "sector": "Telekomunikasi"},
    {"ticker": "ASII", "name": "Astra International Tbk", "sector": "Manufaktur"},
    {"ticker": "GOTO", "name": "GoTo Gojek Tokopedia Tbk", "sector": "Teknologi"},
    {"ticker": "ANTM", "name": "Aneka Tambang Tbk", "sector": "Pertambangan"},
    {"ticker": "PTBA", "name": "Bukit Asam Tbk", "sector": "Pertambangan"},
    {"ticker": "UNVR", "name": "Unilever Indonesia Tbk", "sector": "Konsumer"},
    {"ticker": "INDF", "name": "Indofood Sukses Makmur Tbk", "sector": "Konsumer"},
    {"ticker": "ICBP", "name": "Indofood CBP Sukses Makmur Tbk", "sector": "Konsumer"},
    {"ticker": "KLBF", "name": "Kalbe Farma Tbk", "sector": "Kesehatan"},
    {"ticker": "SIDO", "name": "Industri Jamu dan Farmasi Sido Muncul Tbk", "sector": "Kesehatan"},
    {"ticker": "PGAS", "name": "Perusahaan Gas Negara Tbk", "sector": "Energi"},
    {"ticker": "ADRO", "name": "Adaro Energy Indonesia Tbk", "sector": "Pertambangan"},
    {"ticker": "ITMG", "name": "Indo Tambangraya Megah Tbk", "sector": "Pertambangan"},
    {"ticker": "MDKA", "name": "Merdeka Copper Gold Tbk", "sector": "Pertambangan"},
    {"ticker": "SMGR", "name": "Semen Indonesia Tbk", "sector": "Industri Dasar"},
    {"ticker": "CPIN", "name": "Charoen Pokphand Indonesia Tbk", "sector": "Konsumer"},
    {"ticker": "JPFA", "name": "Japfa Comfeed Indonesia Tbk", "sector": "Konsumer"},
]

# ── Warna Signal ──────────────────────────────────────────
SIGNAL_COLORS = {
    "STRONG_BUY": "#00C853",
    "BUY": "#69F0AE",
    "HOLD": "#FFD740",
    "HOLD / ILLIQUID": "#FFB300",
    "SELL": "#FF6D00",
    "STRONG_SELL": "#D50000",
    "AVOID / HIGH_RISK": "#E91E63",
}

