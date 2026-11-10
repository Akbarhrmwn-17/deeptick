"""data/idx_universe.py — Daftar Saham Paling Aktif, Likuid & Trending di Bursa Efek Indonesia (BEI)

Mencakup ~85 emiten dari:
- LQ45 & IDX30 (Saham penggerak IHSG & paling likuid)
- Saham komoditas & energi favorit trader
- Saham teknologi, perbankan, & konsumer
- Saham dengan volatilitas tinggi & momentum kuat (scalp & swing friendly)
"""

IDX_UNIVERSE = [
    # ── Perbankan & Finansial (Blue Chips & Digital) ──────
    {"ticker": "BBCA", "name": "Bank Central Asia Tbk", "sector": "Keuangan", "tags": ["LQ45", "IDX30", "SWING"]},
    {"ticker": "BBRI", "name": "Bank Rakyat Indonesia Tbk", "sector": "Keuangan", "tags": ["LQ45", "IDX30", "SWING"]},
    {"ticker": "BMRI", "name": "Bank Mandiri Tbk", "sector": "Keuangan", "tags": ["LQ45", "IDX30", "SWING"]},
    {"ticker": "BBNI", "name": "Bank Negara Indonesia Tbk", "sector": "Keuangan", "tags": ["LQ45", "IDX30", "SWING"]},
    {"ticker": "BRIS", "name": "Bank Syariah Indonesia Tbk", "sector": "Keuangan", "tags": ["LQ45", "MOMENTUM", "SWING"]},
    {"ticker": "BBTN", "name": "Bank Tabungan Negara Tbk", "sector": "Keuangan", "tags": ["LQ45", "SWING"]},
    {"ticker": "BDMN", "name": "Bank Danamon Indonesia Tbk", "sector": "Keuangan", "tags": ["SWING"]},
    {"ticker": "ARTO", "name": "Bank Jago Tbk", "sector": "Keuangan", "tags": ["MOMENTUM", "SCALP_FRIENDLY"]},
    {"ticker": "BBYB", "name": "Bank Neo Commerce Tbk", "sector": "Keuangan", "tags": ["SCALP_FRIENDLY"]},

    # ── Energi, Batubara, & Gas ──────────────────────────
    {"ticker": "ADRO", "name": "Adaro Energy Indonesia Tbk", "sector": "Energi", "tags": ["LQ45", "IDX30", "SWING"]},
    {"ticker": "PTBA", "name": "Bukit Asam Tbk", "sector": "Energi", "tags": ["LQ45", "SWING"]},
    {"ticker": "ITMG", "name": "Indo Tambangraya Megah Tbk", "sector": "Energi", "tags": ["LQ45", "SWING"]},
    {"ticker": "PGAS", "name": "Perusahaan Gas Negara Tbk", "sector": "Energi", "tags": ["LQ45", "SWING"]},
    {"ticker": "MEDC", "name": "Medco Energi Internasional Tbk", "sector": "Energi", "tags": ["LQ45", "MOMENTUM", "SCALP_FRIENDLY"]},
    {"ticker": "BUMI", "name": "Bumi Resources Tbk", "sector": "Energi", "tags": ["MOMENTUM", "SCALP_FRIENDLY"]},
    {"ticker": "INDY", "name": "Indika Energy Tbk", "sector": "Energi", "tags": ["SWING"]},
    {"ticker": "AKRA", "name": "AKR Corporindo Tbk", "sector": "Energi", "tags": ["LQ45", "SWING"]},
    {"ticker": "ENRG", "name": "Energi Mega Persada Tbk", "sector": "Energi", "tags": ["SCALP_FRIENDLY"]},
    {"ticker": "ELSA", "name": "Elnusa Tbk", "sector": "Energi", "tags": ["SCALP_FRIENDLY"]},
    {"ticker": "DOID", "name": "Delta Dunia Makmur Tbk", "sector": "Energi", "tags": ["SCALP_FRIENDLY"]},

    # ── Mineral, Logam, & Emas ───────────────────────────
    {"ticker": "ANTM", "name": "Aneka Tambang Tbk", "sector": "Pertambangan", "tags": ["LQ45", "MOMENTUM", "SCALP_FRIENDLY"]},
    {"ticker": "MDKA", "name": "Merdeka Copper Gold Tbk", "sector": "Pertambangan", "tags": ["LQ45", "MOMENTUM", "SCALP_FRIENDLY"]},
    {"ticker": "INCO", "name": "Vale Indonesia Tbk", "sector": "Pertambangan", "tags": ["LQ45", "SWING"]},
    {"ticker": "TINS", "name": "Timah Tbk", "sector": "Pertambangan", "tags": ["MOMENTUM", "SCALP_FRIENDLY"]},
    {"ticker": "AMMN", "name": "Amman Mineral Internasional Tbk", "sector": "Pertambangan", "tags": ["LQ45", "IDX30", "MOMENTUM"]},
    {"ticker": "MBMA", "name": "Merdeka Battery Materials Tbk", "sector": "Pertambangan", "tags": ["MOMENTUM", "SCALP_FRIENDLY"]},
    {"ticker": "NCKL", "name": "Trimegah Bangun Persada Tbk", "sector": "Pertambangan", "tags": ["SWING"]},
    {"ticker": "PSAB", "name": "J Resources Asia Pasifik Tbk", "sector": "Pertambangan", "tags": ["MOMENTUM", "SCALP_FRIENDLY"]},

    # ── Konglomerasi, Industri Dasar & Kimia ─────────────
    {"ticker": "ASII", "name": "Astra International Tbk", "sector": "Manufaktur", "tags": ["LQ45", "IDX30", "SWING"]},
    {"ticker": "UNTR", "name": "United Tractors Tbk", "sector": "Manufaktur", "tags": ["LQ45", "SWING"]},
    {"ticker": "BREN", "name": "Barito Renewables Energy Tbk", "sector": "Industri Dasar", "tags": ["MOMENTUM", "SWING"]},
    {"ticker": "CUAN", "name": "Petrindo Jaya Kreasi Tbk", "sector": "Industri Dasar", "tags": ["MOMENTUM", "SCALP_FRIENDLY"]},
    {"ticker": "TPIA", "name": "Chandra Asri Pacific Tbk", "sector": "Industri Dasar", "tags": ["MOMENTUM", "SWING"]},
    {"ticker": "BRPT", "name": "Barito Pacific Tbk", "sector": "Industri Dasar", "tags": ["LQ45", "MOMENTUM", "SCALP_FRIENDLY"]},
    {"ticker": "PGEO", "name": "Pertamina Geothermal Energy Tbk", "sector": "Industri Dasar", "tags": ["LQ45", "SWING"]},
    {"ticker": "SMGR", "name": "Semen Indonesia Tbk", "sector": "Industri Dasar", "tags": ["LQ45", "SWING"]},
    {"ticker": "INTP", "name": "Indocement Tunggal Prakarsa Tbk", "sector": "Industri Dasar", "tags": ["LQ45", "SWING"]},
    {"ticker": "ESSA", "name": "Essence Indonesia Tbk", "sector": "Industri Dasar", "tags": ["MOMENTUM", "SCALP_FRIENDLY"]},

    # ── Teknologi, Telekomunikasi & Media ────────────────
    {"ticker": "GOTO", "name": "GoTo Gojek Tokopedia Tbk", "sector": "Teknologi", "tags": ["LQ45", "MOMENTUM", "SCALP_FRIENDLY"]},
    {"ticker": "TLKM", "name": "Telkom Indonesia Tbk", "sector": "Telekomunikasi", "tags": ["LQ45", "IDX30", "SWING"]},
    {"ticker": "ISAT", "name": "Indosat Ooredoo Hutchison Tbk", "sector": "Telekomunikasi", "tags": ["LQ45", "SWING"]},
    {"ticker": "EXCL", "name": "XL Axiata Tbk", "sector": "Telekomunikasi", "tags": ["LQ45", "SWING"]},
    {"ticker": "EMTK", "name": "Elang Mahkota Teknologi Tbk", "sector": "Teknologi", "tags": ["MOMENTUM", "SCALP_FRIENDLY"]},
    {"ticker": "BUKA", "name": "Bukalapak.com Tbk", "sector": "Teknologi", "tags": ["SCALP_FRIENDLY"]},
    {"ticker": "MNCN", "name": "Media Nusantara Citra Tbk", "sector": "Media", "tags": ["SWING"]},
    {"ticker": "SCMA", "name": "Surya Citra Media Tbk", "sector": "Media", "tags": ["SWING"]},
    {"ticker": "WIRG", "name": "WIR Asia Tbk", "sector": "Teknologi", "tags": ["SCALP_FRIENDLY"]},

    # ── Konsumer, Retail & Pangan ────────────────────────
    {"ticker": "ICBP", "name": "Indofood CBP Sukses Makmur Tbk", "sector": "Konsumer", "tags": ["LQ45", "IDX30", "SWING"]},
    {"ticker": "INDF", "name": "Indofood Sukses Makmur Tbk", "sector": "Konsumer", "tags": ["LQ45", "SWING"]},
    {"ticker": "UNVR", "name": "Unilever Indonesia Tbk", "sector": "Konsumer", "tags": ["LQ45", "SWING"]},
    {"ticker": "MYOR", "name": "Mayora Indah Tbk", "sector": "Konsumer", "tags": ["SWING"]},
    {"ticker": "AMRT", "name": "Sumber Alfaria Trijaya Tbk", "sector": "Konsumer", "tags": ["LQ45", "SWING"]},
    {"ticker": "CPIN", "name": "Charoen Pokphand Indonesia Tbk", "sector": "Konsumer", "tags": ["LQ45", "SWING"]},
    {"ticker": "JPFA", "name": "Japfa Comfeed Indonesia Tbk", "sector": "Konsumer", "tags": ["SWING"]},
    {"ticker": "ACES", "name": "Aspirasi Hidup Indonesia Tbk", "sector": "Konsumer", "tags": ["SWING"]},
    {"ticker": "MAPI", "name": "Mitra Adiperkasa Tbk", "sector": "Konsumer", "tags": ["SWING"]},

    # ── Kesehatan & Farmasi ──────────────────────────────
    {"ticker": "KLBF", "name": "Kalbe Farma Tbk", "sector": "Kesehatan", "tags": ["LQ45", "SWING"]},
    {"ticker": "MIKA", "name": "Mitra Keluarga Karyasehat Tbk", "sector": "Kesehatan", "tags": ["LQ45", "SWING"]},
    {"ticker": "HEAL", "name": "Medikaloka Hermina Tbk", "sector": "Kesehatan", "tags": ["SWING"]},
    {"ticker": "SIDO", "name": "Industri Jamu Sido Muncul Tbk", "sector": "Kesehatan", "tags": ["SWING"]},
    {"ticker": "SILO", "name": "Siloam International Hospitals Tbk", "sector": "Kesehatan", "tags": ["SWING"]},

    # ── Properti, Real Estate & Konstruksi ───────────────
    {"ticker": "BSDE", "name": "Bumi Serpong Damai Tbk", "sector": "Properti", "tags": ["LQ45", "SWING"]},
    {"ticker": "PWON", "name": "Pakuwon Jati Tbk", "sector": "Properti", "tags": ["SWING"]},
    {"ticker": "CTRA", "name": "Ciputra Development Tbk", "sector": "Properti", "tags": ["SWING"]},
    {"ticker": "SMRA", "name": "Summarecon Agung Tbk", "sector": "Properti", "tags": ["SWING"]},
    {"ticker": "PTPP", "name": "PP (Persero) Tbk", "sector": "Konstruksi", "tags": ["SCALP_FRIENDLY"]},
    {"ticker": "WIKA", "name": "Wijaya Karya Tbk", "sector": "Konstruksi", "tags": ["SCALP_FRIENDLY"]},
    {"ticker": "ADHI", "name": "Adhi Karya Tbk", "sector": "Konstruksi", "tags": ["SCALP_FRIENDLY"]},

    # ── Infrastruktur, Transportasi & Menara ─────────────
    {"ticker": "JSMR", "name": "Jasa Marga Tbk", "sector": "Infrastruktur", "tags": ["LQ45", "SWING"]},
    {"ticker": "TOWR", "name": "Sarana Menara Nusantara Tbk", "sector": "Infrastruktur", "tags": ["LQ45", "SWING"]},
    {"ticker": "TBIG", "name": "Tower Bersama Infrastructure Tbk", "sector": "Infrastruktur", "tags": ["SWING"]},
    {"ticker": "BIRD", "name": "Blue Bird Tbk", "sector": "Transportasi", "tags": ["SWING"]},
    {"ticker": "GIAA", "name": "Garuda Indonesia Tbk", "sector": "Transportasi", "tags": ["SCALP_FRIENDLY"]},

    # ── Saham Volatilitas Tinggi & Favorit Ritel ──────────
    {"ticker": "MEJA", "name": "Harta Djaya Karya Tbk", "sector": "Konsumer", "tags": ["MOMENTUM", "SCALP_FRIENDLY"]},
    {"ticker": "PJHB", "name": "Panca Jaya Hanurata Tbk", "sector": "Energi", "tags": ["SCALP_FRIENDLY"]},
    {"ticker": "RANS", "name": "RANS Nusantara Tbk", "sector": "Media", "tags": ["SCALP_FRIENDLY"]},
    {"ticker": "TAYS", "name": "Jaya Swarasa Agung Tbk", "sector": "Konsumer", "tags": ["SCALP_FRIENDLY"]},
    {"ticker": "BTEK", "name": "Bumi Teknokultura Tbk", "sector": "Agrikultur", "tags": ["SCALP_FRIENDLY"]},
    {"ticker": "FILM", "name": "MD Pictures Tbk", "sector": "Media", "tags": ["MOMENTUM", "SCALP_FRIENDLY"]},
    {"ticker": "AUTO", "name": "Astra Otoparts Tbk", "sector": "Manufaktur", "tags": ["SWING"]},
]


def get_all_universe_tickers() -> list:
    """Return all unique tickers in the universe."""
    return [s["ticker"] for s in IDX_UNIVERSE]


def get_universe_by_category(category: str = "ALL") -> list:
    """Filter universe by category: ALL, LQ45, SCALP_FRIENDLY, SWING, MOMENTUM."""
    if category == "ALL":
        return IDX_UNIVERSE
    return [s for s in IDX_UNIVERSE if category in s.get("tags", [])]
