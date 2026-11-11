"""data/pdf_parser.py — Parser PDF e-Statement Stockbit Sekuritas

Mendukung 2 jenis PDF resmi Stockbit:
1. Statement of Account (SOA) bulanan — dikirim via email tiap bulan
2. Tax Report / Laporan Pajak Tahunan

Cara pakai:
    from data.pdf_parser import parse_stockbit_pdf
    transactions, errors, meta = parse_stockbit_pdf(file_bytes_or_path)
"""

import re
import io
from datetime import datetime
from typing import List, Dict, Tuple, Optional

try:
    import pdfplumber
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False


# ── Konstanta ────────────────────────────────────────────────────────────────

# Kata kunci yang menandakan baris transaksi beli saham di Description
_BUY_KEYWORDS  = ["beli saham", "pembelian", "buy", "beli"]
_SELL_KEYWORDS = ["jual saham", "penjualan", "sell", "jual"]

# Kata kunci non-transaksi yang harus diabaikan (setoran, bunga, dll)
_SKIP_KEYWORDS = [
    "setor dana", "tarik dana", "deposit", "withdraw", "dividen",
    "dividend", "bunga", "interest", "pajak dividen", "rights",
    "bonus saham", "stock split", "opening balance", "ending balance"
]

# Pola kode saham IDX: 4 huruf kapital (BBCA, TLKM, GOTO, dsb.)
_TICKER_RE = re.compile(r'\b([A-Z]{4})\b')

# Pola angka ribuan Indonesia: 1.234.567 atau 1,234,567 atau 1234567
_NUMBER_RE = re.compile(r'[\d]{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?')

# Pola tanggal berbagai format
_DATE_PATTERNS = [
    r'(\d{2})/(\d{2})/(\d{4})',   # 03/07/2025
    r'(\d{2})-(\d{2})-(\d{4})',   # 03-07-2025
    r'(\d{4})-(\d{2})-(\d{2})',   # 2025-07-03
    r'(\d{2})\s+([A-Za-z]{3})\s+(\d{4})',  # 03 Jul 2025
]

_MONTH_MAP = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'mei': 5, 'may': 5,
    'jun': 6, 'jul': 7, 'agu': 8, 'aug': 8, 'sep': 9, 'okt': 10,
    'oct': 10, 'nov': 11, 'des': 12, 'dec': 12
}


# ── Helper Functions ─────────────────────────────────────────────────────────

def _parse_date(text: str) -> Optional[str]:
    """Ekstrak dan normalisasi tanggal dari string teks ke format YYYY-MM-DD."""
    text = text.strip()
    # Format DD/MM/YYYY atau DD-MM-YYYY
    for pat in [r'(\d{2})[/\-](\d{2})[/\-](\d{4})', r'(\d{4})[/\-](\d{2})[/\-](\d{2})']:
        m = re.search(pat, text)
        if m:
            g = m.groups()
            # Deteksi apakah YYYY-MM-DD atau DD-MM-YYYY
            if int(g[0]) > 1900:  # Format YYYY-MM-DD
                return f"{g[0]}-{g[1]}-{g[2]}"
            else:  # Format DD-MM-YYYY
                return f"{g[2]}-{g[1]}-{g[0]}"
    # Format DD Mon YYYY (03 Jul 2025)
    m = re.search(r'(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})', text)
    if m:
        day, mon, year = m.groups()
        month_num = _MONTH_MAP.get(mon.lower())
        if month_num:
            return f"{year}-{month_num:02d}-{int(day):02d}"
    return None


def _parse_number(text: str) -> float:
    """Konversi angka format Indonesia (1.234.567 atau 1,234,567) ke float."""
    text = str(text).strip().replace(" ", "")
    if not text or text in ['-', '0', '']:
        return 0.0
    # Deteksi format: titik ribuan + koma desimal (Indonesia) vs koma ribuan + titik desimal
    # Jika ada titik DAN koma: titik sebelum koma = ribuan Indo
    if '.' in text and ',' in text:
        if text.rindex('.') < text.rindex(','):
            # Format Indo: 1.234.567,89
            text = text.replace('.', '').replace(',', '.')
        else:
            # Format Inggris: 1,234,567.89
            text = text.replace(',', '')
    elif '.' in text:
        parts = text.split('.')
        # Jika lebih dari 1 titik, atau bagian terakhir != 2 digit → ribuan
        if len(parts) > 2 or (len(parts) == 2 and len(parts[-1]) != 2):
            text = text.replace('.', '')
    elif ',' in text:
        parts = text.split(',')
        if len(parts) > 2 or (len(parts) == 2 and len(parts[-1]) != 2):
            text = text.replace(',', '')
        else:
            text = text.replace(',', '.')
    try:
        return float(text)
    except ValueError:
        return 0.0


def _extract_ticker(description: str) -> Optional[str]:
    """Ambil kode saham 4 huruf dari kolom Description."""
    # Cari semua kata 4 huruf kapital
    candidates = _TICKER_RE.findall(description.upper())
    # Filter kata umum bukan kode saham
    exclude = {
        'BELI', 'JUAL', 'SAHAM', 'DANA', 'DARI', 'PADA', 'ATAS',
        'NULL', 'TRUE', 'DATE', 'TIME', 'PAID', 'SELL', 'SLIP'
    }
    for c in candidates:
        if c not in exclude:
            return c
    return None


def _is_skip_row(description: str) -> bool:
    """True jika baris ini bukan transaksi saham (setoran, bunga, dsb.)"""
    desc_lower = description.lower()
    return any(kw in desc_lower for kw in _SKIP_KEYWORDS)


def _detect_side(description: str) -> Optional[str]:
    """Deteksi BUY atau SELL dari teks deskripsi."""
    desc_lower = description.lower()
    if any(kw in desc_lower for kw in _SELL_KEYWORDS):
        return "SELL"
    if any(kw in desc_lower for kw in _BUY_KEYWORDS):
        return "BUY"
    return None


# ── Core: Parser dari tabel pdfplumber ──────────────────────────────────────

def _parse_soa_tables(pdf) -> Tuple[List[Dict], List[str]]:
    """
    Parse Statement of Account (SOA) bulanan Stockbit.
    Struktur kolom: Tr.Date | Due Date | Reference | Description | Db Amount | Cr Amount | Ending Balance
    """
    transactions = []
    errors = []

    for page_num, page in enumerate(pdf.pages, 1):
        tables = page.extract_tables()
        for table in tables:
            if not table:
                continue
            # Deteksi baris header
            header_idx = None
            for i, row in enumerate(table):
                row_text = " ".join(str(c) for c in row if c).lower()
                if any(h in row_text for h in ["tr. date", "tr.date", "transaction date", "tanggal", "description", "deskripsi"]):
                    header_idx = i
                    break

            if header_idx is None:
                continue

            headers = [str(h).lower().strip() if h else "" for h in table[header_idx]]

            # Mapping kolom
            col_date = next((i for i, h in enumerate(headers) if "tr" in h and "date" in h), None)
            if col_date is None:
                col_date = next((i for i, h in enumerate(headers) if "tanggal" in h or "date" in h), None)
            col_desc = next((i for i, h in enumerate(headers) if "desc" in h or "keterangan" in h or "reference" in h), None)
            col_db   = next((i for i, h in enumerate(headers) if "db" in h or "debit" in h), None)
            col_cr   = next((i for i, h in enumerate(headers) if "cr" in h or "credit" in h), None)

            if col_desc is None:
                continue

            for row_i, row in enumerate(table[header_idx + 1:], 1):
                try:
                    if not row or all(c is None or str(c).strip() == "" for c in row):
                        continue

                    desc = str(row[col_desc] or "").strip() if col_desc < len(row) else ""
                    if not desc:
                        continue
                    if _is_skip_row(desc):
                        continue

                    side = _detect_side(desc)
                    if not side:
                        continue

                    ticker = _extract_ticker(desc)
                    if not ticker:
                        continue

                    # Tanggal
                    date_raw = str(row[col_date] or "") if col_date is not None and col_date < len(row) else ""
                    parsed_date = _parse_date(date_raw) or datetime.now().strftime("%Y-%m-%d")

                    # Nilai transaksi: BUY dari Debit, SELL dari Credit
                    db_val = _parse_number(row[col_db]) if col_db is not None and col_db < len(row) else 0.0
                    cr_val = _parse_number(row[col_cr]) if col_cr is not None and col_cr < len(row) else 0.0
                    amount = db_val if side == "BUY" else cr_val

                    if amount <= 0:
                        continue

                    # Estimasi harga & lot dari amount (hanya bisa estimasi dari SOA)
                    # SOA tidak menyertakan lot & harga per lembar secara eksplisit
                    # Kita coba ekstrak angka dari description
                    desc_numbers = [_parse_number(n) for n in _NUMBER_RE.findall(desc) if _parse_number(n) > 0]
                    lot_val = None
                    price_val = None

                    # Pola "X LOT @ HARGA" atau angka pertama=lot, kedua=harga
                    lot_match = re.search(r'(\d+)\s*lot', desc, re.I)
                    price_match = re.search(r'@\s*([\d.,]+)', desc, re.I)
                    if lot_match:
                        lot_val = int(lot_match.group(1))
                    if price_match:
                        price_val = _parse_number(price_match.group(1))

                    # Fallback: estimasi dari total amount
                    if lot_val and not price_val:
                        price_val = round(amount / (lot_val * 100), 0)
                    elif price_val and not lot_val:
                        lot_val = max(1, round(amount / (price_val * 100)))
                    elif not lot_val and not price_val:
                        # Tidak bisa parse → skip dengan warning
                        errors.append(
                            f"Halaman {page_num}, baris {row_i}: {ticker} {side} — "
                            f"tidak bisa deteksi lot/harga dari deskripsi. "
                            f"Gunakan tab 'Input Manual' untuk entry ini."
                        )
                        continue

                    transactions.append({
                        "ticker":   ticker,
                        "type":     side,
                        "date":     parsed_date,
                        "lot":      int(lot_val),
                        "price":    float(price_val),
                        "fee":      round(amount * 0.0015, 0) if side == "BUY" else round(amount * 0.0025, 0),
                        "tax":      round(amount * 0.001, 0) if side == "SELL" else 0.0,
                        "notes":    f"Import PDF e-Statement — {desc[:60]}",
                        "source":   "pdf_soa",
                    })

                except Exception as e:
                    errors.append(f"Halaman {page_num}, baris {row_i}: {str(e)}")

    return transactions, errors


def _parse_fulltext_fallback(pdf) -> Tuple[List[Dict], List[str]]:
    """
    Fallback: ekstrak teks mentah dari PDF jika tabel tidak terdeteksi.
    Cocok untuk PDF yang di-generate sebagai gambar atau layout tidak standar.
    Baca baris per baris dan cari pola transaksi.
    """
    transactions = []
    errors = []

    for page_num, page in enumerate(pdf.pages, 1):
        text = page.extract_text() or ""
        lines = [l.strip() for l in text.split('\n') if l.strip()]

        for line_i, line in enumerate(lines):
            try:
                if _is_skip_row(line):
                    continue
                side = _detect_side(line)
                if not side:
                    continue
                ticker = _extract_ticker(line)
                if not ticker:
                    continue

                # Cari tanggal di awal baris
                parsed_date = _parse_date(line[:20]) or datetime.now().strftime("%Y-%m-%d")

                # Cari lot dan harga
                lot_match = re.search(r'(\d+)\s*lot', line, re.I)
                price_match = re.search(r'[Rr][Pp]?\s*([\d.,]+)', line)
                at_match = re.search(r'@\s*([\d.,]+)', line)

                lot_val = int(lot_match.group(1)) if lot_match else None
                price_val = (
                    _parse_number(at_match.group(1)) if at_match
                    else _parse_number(price_match.group(1)) if price_match
                    else None
                )

                if not lot_val or not price_val or price_val <= 0:
                    continue

                gross = lot_val * 100 * price_val
                transactions.append({
                    "ticker": ticker,
                    "type":   side,
                    "date":   parsed_date,
                    "lot":    lot_val,
                    "price":  price_val,
                    "fee":    round(gross * 0.0015, 0) if side == "BUY" else round(gross * 0.0025, 0),
                    "tax":    round(gross * 0.001, 0) if side == "SELL" else 0.0,
                    "notes":  f"Import PDF (teks) — {line[:60]}",
                    "source": "pdf_text",
                })
            except Exception as e:
                errors.append(f"Halaman {page_num}, baris {line_i}: {str(e)}")

    return transactions, errors


# ── Public API ───────────────────────────────────────────────────────────────

def parse_stockbit_pdf(
    file_input,
) -> Tuple[List[Dict], List[str], Dict]:
    """
    Parse file PDF e-Statement Stockbit menjadi daftar transaksi.

    Parameters
    ----------
    file_input : bytes | BytesIO | str (path)
        File PDF dalam bentuk bytes, BytesIO, atau path string.

    Returns
    -------
    transactions : list[dict]
        Daftar transaksi dengan keys: ticker, type, date, lot, price, fee, tax, notes
    errors : list[str]
        Daftar pesan error/warning untuk baris yang gagal di-parse
    meta : dict
        Metadata PDF: jumlah halaman, periode, nama nasabah (jika terdeteksi)
    """
    if not PDF_AVAILABLE:
        return [], ["Library 'pdfplumber' belum terinstall. Jalankan: pip install pdfplumber"], {}

    # Normalisasi input
    if isinstance(file_input, bytes):
        file_input = io.BytesIO(file_input)
    elif isinstance(file_input, str):
        file_input = open(file_input, 'rb')

    meta = {}
    try:
        with pdfplumber.open(file_input) as pdf:
            meta["pages"] = len(pdf.pages)

            # Ekstrak metadata dari halaman pertama
            if pdf.pages:
                first_page_text = pdf.pages[0].extract_text() or ""
                # Cari nama nasabah
                name_match = re.search(r'(?:Nama|Name|Client)\s*[:\-]\s*(.+)', first_page_text, re.I)
                if name_match:
                    meta["client_name"] = name_match.group(1).strip()[:50]
                # Cari periode
                period_match = re.search(r'(\d{2}[/\-]\d{2}[/\-]\d{4})\s*[-–]\s*(\d{2}[/\-]\d{2}[/\-]\d{4})', first_page_text)
                if period_match:
                    meta["period"] = f"{period_match.group(1)} s/d {period_match.group(2)}"

            # Coba parse tabel dulu
            transactions, errors = _parse_soa_tables(pdf)

            # Jika tabel kosong, fallback ke parsing teks
            if not transactions:
                errors_fallback = ["⚠️ Tabel tidak terdeteksi, mencoba parsing teks mentah..."]
                tx_fallback, err_fallback = _parse_fulltext_fallback(pdf)
                transactions = tx_fallback
                errors = errors_fallback + err_fallback

            meta["parsed_count"] = len(transactions)
            meta["error_count"]  = len(errors)

    except Exception as e:
        return [], [f"Gagal membuka PDF: {str(e)}"], meta

    return transactions, errors, meta
