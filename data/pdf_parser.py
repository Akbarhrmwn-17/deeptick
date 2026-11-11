"""data/pdf_parser.py — Parser PDF Stockbit Sekuritas

Mendukung 2 jenis PDF resmi Stockbit:
1. Trade Confirmation (TC_xxxx.pdf)   — dikirim per transaksi via email
2. Statement of Account (SOA) bulanan — dikirim tiap awal bulan

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


# ── Helpers ──────────────────────────────────────────────────────────────────

def _parse_date(text: str) -> Optional[str]:
    """Normalisasi berbagai format tanggal ke YYYY-MM-DD."""
    text = str(text).strip()
    # DD/MM/YYYY atau DD-MM-YYYY
    m = re.search(r'(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})', text)
    if m:
        d, mo, y = m.groups()
        return f"{y}-{int(mo):02d}-{int(d):02d}"
    # YYYY-MM-DD
    m = re.search(r'(\d{4})[/\-](\d{2})[/\-](\d{2})', text)
    if m:
        y, mo, d = m.groups()
        return f"{y}-{mo}-{d}"
    # DD Mon YYYY
    _MONTH = {'jan':1,'feb':2,'mar':3,'apr':4,'mei':5,'may':5,'jun':6,
               'jul':7,'agu':8,'aug':8,'sep':9,'okt':10,'oct':10,'nov':11,'des':12,'dec':12}
    m = re.search(r'(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})', text)
    if m:
        d, mon, y = m.groups()
        mn = _MONTH.get(mon.lower())
        if mn:
            return f"{y}-{mn:02d}-{int(d):02d}"
    return None


def _parse_number(text: str) -> float:
    """Konversi string angka format Indonesia ke float."""
    text = str(text).strip().replace(" ", "")
    if not text or text in ['-', '', '0']:
        return 0.0
    # Hapus karakter non-numerik kecuali titik dan koma
    text = re.sub(r'[^\d.,]', '', text)
    if not text:
        return 0.0
    # Deteksi format ribuan: 1.234.567 atau 1,234,567
    if '.' in text and ',' in text:
        if text.rindex('.') < text.rindex(','):
            # Indo: 1.234,56
            text = text.replace('.', '').replace(',', '.')
        else:
            # Inggris: 1,234.56
            text = text.replace(',', '')
    elif '.' in text:
        parts = text.split('.')
        if len(parts) > 2 or len(parts[-1]) != 2:
            text = text.replace('.', '')  # ribuan
    elif ',' in text:
        parts = text.split(',')
        if len(parts) > 2 or len(parts[-1]) != 2:
            text = text.replace(',', '')  # ribuan
        else:
            text = text.replace(',', '.')
    try:
        return float(text)
    except ValueError:
        return 0.0


def _extract_ticker_from_share_name(share_name: str) -> Optional[str]:
    """
    Ambil kode ticker 4 huruf dari nama saham lengkap.
    Contoh: "MEJA Harta Djaya Karya Tbk" → "MEJA"
    """
    share_name = share_name.strip()
    # Kata pertama yang 4 huruf kapital
    words = share_name.split()
    exclude = {'BELI', 'JUAL', 'SELL', 'SAHAM', 'DARI', 'PADA', 'NULL', 'TRUE'}
    for w in words:
        clean = re.sub(r'[^A-Za-z]', '', w).upper()
        if 3 <= len(clean) <= 5 and clean not in exclude:
            return clean[:4]  # ambil 4 huruf pertama
    return None


# ── Parser 1: Trade Confirmation (TC) ────────────────────────────────────────

def _parse_trade_confirmation(pdf) -> Tuple[List[Dict], List[str], Dict]:
    """
    Parse PDF Trade Confirmation Stockbit.
    Format:  TC_<clientID>-<YYYYMMDD>_<id>.pdf

    Tabel transaksi:
    REF# | Board | Share | Lot | Quantity | Price | Buy | Sell
    """
    transactions = []
    errors = []
    meta = {}

    full_text = ""
    for page in pdf.pages:
        full_text += (page.extract_text() or "") + "\n"

    # ── Metadata dari header ──────────────────────────────
    # Nama nasabah
    name_m = re.search(r'To\s+\d+\s+([A-Z\s]+)\n', full_text)
    if name_m:
        meta["client_name"] = name_m.group(1).strip()

    # Tanggal transaksi
    tx_date_m = re.search(r'Transaction Date\s+(\d{1,2}/\d{1,2}/\d{4})', full_text)
    tx_date = _parse_date(tx_date_m.group(1)) if tx_date_m else datetime.now().strftime("%Y-%m-%d")
    meta["tx_date"] = tx_date

    # Tipe dokumen
    meta["doc_type"] = "Trade Confirmation"

    # ── Parse tabel transaksi ─────────────────────────────
    # Coba via pdfplumber tables dulu
    for page in pdf.pages:
        tables = page.extract_tables()
        for table in tables:
            if not table:
                continue
            # Cari header baris: REF# | Board | Share | Lot | Quantity | Price | Buy | Sell
            header_idx = None
            for i, row in enumerate(table):
                row_txt = " ".join(str(c or "")).lower()
                if ("ref" in row_txt or "share" in row_txt) and ("lot" in row_txt or "price" in row_txt):
                    header_idx = i
                    break

            if header_idx is None:
                continue

            headers = [str(h or "").lower().strip() for h in table[header_idx]]
            # Mapping kolom
            col_share    = next((i for i, h in enumerate(headers) if "share" in h), None)
            col_lot      = next((i for i, h in enumerate(headers) if h == "lot"), None)
            col_price    = next((i for i, h in enumerate(headers) if "price" in h), None)
            col_buy      = next((i for i, h in enumerate(headers) if h == "buy"), None)
            col_sell     = next((i for i, h in enumerate(headers) if h == "sell"), None)

            for row in table[header_idx + 1:]:
                if not row or all(c is None or str(c).strip() == "" for c in row):
                    continue
                try:
                    share_name = str(row[col_share] or "").strip() if col_share is not None else ""
                    if not share_name or share_name.lower() in ["share", ""]:
                        continue

                    ticker = _extract_ticker_from_share_name(share_name)
                    if not ticker:
                        continue

                    lot_val   = int(_parse_number(row[col_lot]))   if col_lot   is not None else 0
                    price_val = _parse_number(row[col_price])      if col_price is not None else 0.0
                    buy_val   = _parse_number(row[col_buy])        if col_buy   is not None else 0.0
                    sell_val  = _parse_number(row[col_sell])       if col_sell  is not None else 0.0

                    if lot_val <= 0 or price_val <= 0:
                        continue

                    # BUY jika ada nilai di kolom Buy, SELL jika di kolom Sell
                    if sell_val > 0 and buy_val == 0:
                        side = "SELL"
                        gross = sell_val
                    elif buy_val > 0:
                        side = "BUY"
                        gross = buy_val
                    else:
                        # Fallback: estimasi dari lot & price
                        gross = lot_val * 100 * price_val
                        side = "BUY"  # default

                    transactions.append({
                        "ticker": ticker,
                        "type":   side,
                        "date":   tx_date,
                        "lot":    lot_val,
                        "price":  price_val,
                        "fee":    0.0,  # akan diisi dari summary section
                        "tax":    0.0,
                        "notes":  f"TC Import — {share_name[:50]}",
                        "source": "trade_confirmation",
                        "_gross": gross,
                    })
                except Exception as e:
                    errors.append(f"Parse baris tabel TC gagal: {str(e)}")

    # ── Fallback: regex dari full text ───────────────────
    if not transactions:
        # Cari pola: REF Board Share Lot Quantity Price Buy Sell
        # Dari baris teks mentah
        lines = full_text.split('\n')
        for i, line in enumerate(lines):
            # Cari baris yang mengandung angka lot dan harga
            # Format TC: "0236672 RG MEJA Harta Djaya Karya Tbk 120 12,000.00 84.00 0.00 1,008,000.00"
            m = re.match(
                r'^(\d{5,8})\s+(RG|NG|TN)\s+(.+?)\s+(\d+)\s+([\d,\.]+)\s+([\d,\.]+)\s+([\d,\.]+)\s+([\d,\.]+)',
                line.strip()
            )
            if m:
                try:
                    ref, board, share_name, lot_str, qty_str, price_str, buy_str, sell_str = m.groups()
                    ticker   = _extract_ticker_from_share_name(share_name)
                    lot_val  = int(lot_str.replace(',', '').replace('.', ''))
                    price_val = _parse_number(price_str)
                    buy_val  = _parse_number(buy_str)
                    sell_val = _parse_number(sell_str)

                    if not ticker or lot_val <= 0 or price_val <= 0:
                        continue

                    if sell_val > buy_val:
                        side, gross = "SELL", sell_val
                    else:
                        side, gross = "BUY", buy_val

                    transactions.append({
                        "ticker": ticker,
                        "type":   side,
                        "date":   tx_date,
                        "lot":    lot_val,
                        "price":  price_val,
                        "fee":    0.0,
                        "tax":    0.0,
                        "notes":  f"TC Import — {share_name[:50]}",
                        "source": "trade_confirmation_text",
                        "_gross": gross,
                    })
                except Exception as e:
                    errors.append(f"Regex parse baris gagal: {str(e)}")

    # ── Ekstrak Fee & Tax dari bagian Summary ─────────────
    # Cari Commission, Income Tax, IDX Fee dari teks
    if transactions:
        commission_m  = re.search(r'Commission\s+([\d,\.]+)\s+([\d,\.]+)', full_text)
        income_tax_m  = re.search(r'Income Tax\s+[\d,\.]+\s+([\d,\.]+)', full_text)
        total_cost_m  = re.search(r'Total Cost\s+([\d,\.]+)\s+([\d,\.]+)', full_text)
        payment_m     = re.search(r'Payment due to you IDR\s+([\d,\.]+)\s+([\d,\.]+)', full_text)
        stamp_duty_m  = re.search(r'Stamp Duty\s+([\d,\.]+)\s+([\d,\.]+)', full_text)

        for tx in transactions:
            gross = tx.get("_gross", tx["lot"] * 100 * tx["price"])
            if tx["type"] == "SELL":
                # Fee = Commission + VAT + IDX Fee + VAT Levy
                comm  = _parse_number(commission_m.group(2))  if commission_m  else 0
                tax   = _parse_number(income_tax_m.group(1))  if income_tax_m  else 0
                tx["fee"] = comm
                tx["tax"] = tax
            else:
                comm  = _parse_number(commission_m.group(1)) if commission_m else round(gross * 0.0015, 0)
                tx["fee"] = comm
                tx["tax"] = 0.0
            del tx["_gross"]

    return transactions, errors, meta


# ── Parser 2: Statement of Account (SOA) bulanan ─────────────────────────────

def _parse_soa(pdf) -> Tuple[List[Dict], List[str], Dict]:
    """
    Parse PDF Statement of Account (SOA) bulanan Stockbit.
    Kolom: Tr.Date | Due Date | Reference | Description | Db | Cr | Ending Balance
    """
    transactions = []
    errors = []
    meta = {"doc_type": "Statement of Account"}

    _SKIP = ["setor dana", "tarik dana", "deposit", "withdraw", "dividen",
             "dividend", "bunga", "interest", "pajak dividen", "rights", "split"]

    full_text = ""
    for page in pdf.pages:
        full_text += (page.extract_text() or "") + "\n"

    # Periode
    period_m = re.search(r'(\d{2}[/\-]\d{2}[/\-]\d{4})\s*[-–]\s*(\d{2}[/\-]\d{2}[/\-]\d{4})', full_text)
    if period_m:
        meta["period"] = f"{period_m.group(1)} s/d {period_m.group(2)}"

    for page_num, page in enumerate(pdf.pages, 1):
        tables = page.extract_tables()
        for table in tables:
            if not table:
                continue
            header_idx = None
            for i, row in enumerate(table):
                row_txt = " ".join(str(c or "")).lower()
                if ("date" in row_txt or "tanggal" in row_txt) and ("desc" in row_txt or "keterangan" in row_txt):
                    header_idx = i
                    break
            if header_idx is None:
                continue

            headers = [str(h or "").lower().strip() for h in table[header_idx]]
            col_date = next((i for i, h in enumerate(headers) if "tr" in h and "date" in h), None)
            if col_date is None:
                col_date = next((i for i, h in enumerate(headers) if "tanggal" in h or ("date" in h and "due" not in h)), None)
            col_desc = next((i for i, h in enumerate(headers) if "desc" in h or "keterangan" in h), None)
            col_db   = next((i for i, h in enumerate(headers) if h in ["db", "debit", "db amount"]), None)
            col_cr   = next((i for i, h in enumerate(headers) if h in ["cr", "credit", "cr amount"]), None)

            if col_desc is None:
                continue

            for row in table[header_idx + 1:]:
                try:
                    desc = str(row[col_desc] or "").strip() if col_desc < len(row) else ""
                    if not desc:
                        continue
                    desc_lower = desc.lower()
                    if any(kw in desc_lower for kw in _SKIP):
                        continue
                    if "beli" not in desc_lower and "jual" not in desc_lower and \
                       "buy" not in desc_lower and "sell" not in desc_lower:
                        continue

                    side = "SELL" if any(k in desc_lower for k in ["jual", "sell"]) else "BUY"
                    ticker_m = re.search(r'\b([A-Z]{4})\b', desc.upper())
                    ticker = ticker_m.group(1) if ticker_m else None
                    if not ticker:
                        continue

                    date_raw = str(row[col_date] or "") if col_date is not None and col_date < len(row) else ""
                    parsed_date = _parse_date(date_raw) or datetime.now().strftime("%Y-%m-%d")

                    db_val = _parse_number(row[col_db]) if col_db is not None and col_db < len(row) else 0.0
                    cr_val = _parse_number(row[col_cr]) if col_cr is not None and col_cr < len(row) else 0.0
                    amount = db_val if side == "BUY" else cr_val
                    if amount <= 0:
                        continue

                    # Cari lot & harga dari deskripsi
                    lot_m   = re.search(r'(\d+)\s*lot', desc, re.I)
                    price_m = re.search(r'@\s*([\d.,]+)', desc)
                    lot_val   = int(lot_m.group(1)) if lot_m else None
                    price_val = _parse_number(price_m.group(1)) if price_m else None

                    if lot_val and not price_val:
                        price_val = round(amount / (lot_val * 100))
                    elif price_val and not lot_val:
                        lot_val = max(1, round(amount / (price_val * 100)))
                    elif not lot_val and not price_val:
                        errors.append(f"SOA: {ticker} {side} {parsed_date} — tidak bisa deteksi lot/harga dari deskripsi, skip.")
                        continue

                    gross = lot_val * 100 * price_val
                    transactions.append({
                        "ticker": ticker,
                        "type":   side,
                        "date":   parsed_date,
                        "lot":    int(lot_val),
                        "price":  float(price_val),
                        "fee":    round(gross * 0.0015, 0) if side == "BUY" else round(gross * 0.0025, 0),
                        "tax":    round(gross * 0.001, 0) if side == "SELL" else 0.0,
                        "notes":  f"SOA Import — {desc[:60]}",
                        "source": "soa",
                    })
                except Exception as e:
                    errors.append(f"SOA halaman {page_num}: {str(e)}")

    return transactions, errors, meta


# ── Public API ────────────────────────────────────────────────────────────────

def parse_stockbit_pdf(file_input) -> Tuple[List[Dict], List[str], Dict]:
    """
    Parse file PDF Stockbit (Trade Confirmation atau Statement of Account).

    Parameters
    ----------
    file_input : bytes | BytesIO | str (path)

    Returns
    -------
    transactions : list[dict]   ticker, type, date, lot, price, fee, tax, notes
    errors       : list[str]    pesan error/warning
    meta         : dict         info dokumen (doc_type, client_name, period, dsb.)
    """
    if not PDF_AVAILABLE:
        return [], ["Library 'pdfplumber' belum terinstall. Jalankan: pip install pdfplumber"], {}

    if isinstance(file_input, bytes):
        file_input = io.BytesIO(file_input)
    elif isinstance(file_input, str):
        file_input = open(file_input, 'rb')

    try:
        with pdfplumber.open(file_input) as pdf:
            meta = {"pages": len(pdf.pages)}

            # Deteksi tipe dokumen dari teks halaman pertama
            first_text = (pdf.pages[0].extract_text() or "").lower() if pdf.pages else ""

            if "trade confirmation" in first_text:
                transactions, errors, doc_meta = _parse_trade_confirmation(pdf)
            else:
                transactions, errors, doc_meta = _parse_soa(pdf)

            meta.update(doc_meta)
            meta["parsed_count"] = len(transactions)
            meta["error_count"]  = len(errors)

    except Exception as e:
        return [], [f"Gagal membuka PDF: {str(e)}"], {}

    return transactions, errors, meta
