"""data/stockbit_importer.py — Parser otomatis untuk file export laporan Stockbit & format umum CSV/Excel"""

import pandas as pd
from datetime import datetime
import re
from typing import List, Dict, Tuple


def clean_currency(val) -> float:
    """Bersihkan nilai angka/rupiah (contoh: 'Rp 10.500', '10,500', '(500)')."""
    if pd.isna(val):
        return 0.0
    val_str = str(val).strip()
    # Deteksi negatif tanda kurung
    is_negative = val_str.startswith("(") and val_str.endswith(")")
    clean = re.sub(r"[^\d.]", "", val_str.replace(",", "."))
    # Jika ada lebih dari 1 titik desimal karena tanda ribuan, tangani dengan cermat
    parts = clean.split(".")
    if len(parts) > 2:
        clean = "".join(parts[:-1]) + "." + parts[-1]
    try:
        num = float(clean)
        return -num if is_negative else num
    except Exception:
        return 0.0


def parse_stockbit_file(file_content, filename: str) -> Tuple[List[Dict], List[str]]:
    """
    Menerima file upload (CSV / Excel) dari Stockbit atau template transaksi.
    Mendeteksi kolom secara pintar:
    - Date / Tanggal
    - Stock / Ticker / Symbol / Emiten / Saham
    - Action / Type / Side / Beli-Jual (Buy/Sell)
    - Lot / Quantity / Qty / Volume
    - Price / Average Price / Harga
    - Fee / Broker Fee / Komisi
    """
    errors = []
    parsed_rows = []

    try:
        if filename.lower().endswith((".xlsx", ".xls")):
            df = pd.read_excel(file_content)
        else:
            # Coba deteksi delimiter koma atau titik koma
            try:
                df = pd.read_csv(file_content)
            except Exception:
                file_content.seek(0)
                df = pd.read_csv(file_content, sep=";")
    except Exception as e:
        return [], [f"Gagal membaca file: {str(e)}"]

    if df.empty:
        return [], ["File yang diunggah kosong."]

    # Normalisasi nama kolom (lowercase & strip spasi/simbol)
    col_map = {}
    for col in df.columns:
        norm = re.sub(r"[^a-z0-9]", "", str(col).lower())
        col_map[norm] = col

    def find_col(*candidates):
        for c in candidates:
            for k, original in col_map.items():
                if c in k:
                    return original
        return None

    c_date = find_col("date", "tgl", "tanggal", "time", "waktu")
    c_ticker = find_col("stock", "ticker", "symbol", "emiten", "saham", "code", "kode")
    c_side = find_col("side", "action", "type", "tipe", "transaksi", "status", "bs")
    c_lot = find_col("lot", "quantity", "qty", "volume", "lembar", "jumlah")
    c_price = find_col("price", "harga", "avgprice", "rate", "execprice")
    c_fee = find_col("fee", "komisi", "biaya")

    if not (c_ticker and c_side and c_lot and c_price):
        missing = []
        if not c_ticker: missing.append("Ticker/Saham")
        if not c_side: missing.append("Tipe Transaksi (Buy/Sell)")
        if not c_lot: missing.append("Lot/Jumlah")
        if not c_price: missing.append("Harga")
        return [], [f"Kolom wajib tidak ditemukan: {', '.join(missing)}. Kolom yang terbaca di file: {list(df.columns)}"]

    for idx, row in df.iterrows():
        try:
            ticker_val = str(row[c_ticker]).upper().strip()
            # Bersihkan ticker dari .JK atau spasi
            ticker_val = re.sub(r"[^A-Z]", "", ticker_val.replace(".JK", ""))
            if not ticker_val or len(ticker_val) < 4:
                continue

            # Parsing Tipe Transaksi (BUY / SELL)
            side_raw = str(row[c_side]).upper().strip()
            if any(w in side_raw for w in ["BUY", "BELI", "B"]):
                tx_type = "BUY"
            elif any(w in side_raw for w in ["SELL", "JUAL", "S"]):
                tx_type = "SELL"
            else:
                continue

            # Parsing Lot & Price
            lot_raw = clean_currency(row[c_lot])
            # Jika dalam lembar dan besar (> 100), cek apakah kolomnya lembar/shares
            if "lembar" in str(c_lot).lower() or "share" in str(c_lot).lower():
                lot_val = int(lot_raw // 100)
            else:
                lot_val = int(lot_raw)

            if lot_val <= 0:
                continue

            price_val = clean_currency(row[c_price])
            if price_val <= 0:
                continue

            # Tanggal
            date_val = str(datetime.now().strftime("%Y-%m-%d"))
            if c_date and not pd.isna(row[c_date]):
                try:
                    dt = pd.to_datetime(row[c_date])
                    date_val = dt.strftime("%Y-%m-%d")
                except Exception:
                    date_val = str(row[c_date])[:10]

            # Fee
            fee_val = clean_currency(row[c_fee]) if c_fee and not pd.isna(row[c_fee]) else 0.0

            parsed_rows.append({
                "ticker": ticker_val,
                "type": tx_type,
                "date": date_val,
                "lot": lot_val,
                "price": price_val,
                "fee": fee_val,
                "tax": 0.0,
                "notes": "Imported dari Stockbit / File",
            })
        except Exception as err:
            errors.append(f"Baris {idx+1}: {str(err)}")

    return parsed_rows, errors


def parse_stockbit_portfolio_table(raw_text: str) -> Tuple[List[Dict], List[str]]:
    """
    Parser khusus untuk tabel porto Stockbit hasil Ctrl+C dari browser.

    Format kolom Stockbit Portfolio:
    Symbol | Balance Lot | Available Lot | Average Price | Current Price |
    Invested | Market Value | Potential P/L | Percentage | Action
    """
    parsed = []
    errors = []
    today = datetime.now().strftime("%Y-%m-%d")

    lines = [l.strip() for l in raw_text.strip().split("\n") if l.strip()]

    # Mapping kolom default
    col_sym = 0
    col_lot = 1
    col_avg = 3

    # Cek apakah ada baris header untuk deteksi kolom yang dinamis
    for line in lines[:3]:
        parts = re.split(r'\t|  +', line.strip())
        parts_low = [p.lower() for p in parts]
        if any("symbol" in p or "saham" in p or "emiten" in p for p in parts_low):
            for i, p in enumerate(parts_low):
                if any(k in p for k in ["symbol", "saham", "emiten"]):
                    col_sym = i
                elif any(k in p for k in ["balance", "bal lot", "lot", "qty"]):
                    col_lot = i
                elif any(k in p for k in ["average", "avg", "rata"]):
                    col_avg = i
            break

    HEADER_KEYWORDS = {"symbol", "balance", "lot", "average", "price", "invested",
                       "market", "potential", "percentage", "action", "saham",
                       "current", "available"}

    for line in lines:
        try:
            parts = re.split(r'\t|  +', line.strip())
            parts = [p.strip() for p in parts if p.strip()]

            if len(parts) < 3:
                continue

            # Skip baris header
            if any(p.lower() in HEADER_KEYWORDS for p in parts[:3]):
                continue

            # Kolom Symbol/Ticker
            sym_idx = col_sym if col_sym < len(parts) else 0
            ticker_raw = re.sub(r'[^A-Za-z]', '', parts[sym_idx]).upper()
            if len(ticker_raw) < 2 or len(ticker_raw) > 6:
                continue

            # Kolom Balance Lot
            lot_idx = col_lot if col_lot < len(parts) else 1
            lot_raw = clean_currency(parts[lot_idx])
            if lot_raw <= 0:
                continue

            if lot_raw < 1:
                lot_val = 1
                lot_note = f"Porto asli: {lot_raw} lot ({round(lot_raw*100)} lembar)"
            else:
                lot_val = int(lot_raw)
                lot_note = ""

            # Kolom Average Price
            avg_idx = col_avg if col_avg < len(parts) else (3 if len(parts) >= 4 else 2)
            avg_price = clean_currency(parts[avg_idx])

            if avg_price <= 0:
                # Coba fallback kolom lain
                for alt_idx in [3, 2, 4]:
                    if alt_idx < len(parts) and alt_idx != lot_idx:
                        alt_val = clean_currency(parts[alt_idx])
                        if alt_val > 0:
                            avg_price = alt_val
                            break

            if avg_price <= 0:
                errors.append(f"Baris '{line[:40]}': tidak bisa deteksi harga rata-rata")
                continue

            note = "Porto Snapshot Stockbit"
            if lot_note:
                note += f" | {lot_note}"

            parsed.append({
                "ticker": ticker_raw[:4],
                "type": "BUY",
                "date": today,
                "lot": lot_val,
                "price": avg_price,
                "fee": 0.0,
                "tax": 0.0,
                "notes": note,
            })

        except Exception as e:
            errors.append(f"Baris '{line[:40]}': {str(e)}")

    return parsed, errors


def _is_stockbit_portfolio_table(raw_text: str) -> bool:
    """
    Deteksi apakah teks ini hasil copy-paste tabel Portfolio Stockbit
    (tab-separated dengan banyak kolom numerik per baris).
    """
    lines = [l.strip() for l in raw_text.strip().split("\n") if l.strip()]
    # Ambil sampel baris non-kosong pertama
    for line in lines[:5]:
        parts = re.split(r'\t|  +', line.strip())
        parts = [p.strip() for p in parts if p.strip()]
        # Format porto Stockbit: minimal 4 kolom, kolom pertama = ticker 4 huruf
        if len(parts) >= 4:
            ticker_candidate = re.sub(r'[^A-Za-z]', '', parts[0]).upper()
            if 2 <= len(ticker_candidate) <= 6:
                # Cek apakah ada angka di kolom ke-2 dan ke-4 (lot & harga)
                has_lot   = re.match(r'^[\d.,]+$', parts[1]) is not None
                has_price = any(re.match(r'^[\d.,]+$', p) for p in parts[2:5])
                if has_lot and has_price:
                    return True
    return False


def parse_pasted_text(raw_text: str) -> Tuple[List[Dict], List[str]]:
    """
    Parser universal untuk teks hasil copy-paste.
    Auto-deteksi format:
    1. Tabel Portfolio Stockbit (Ctrl+C dari browser) → parse_stockbit_portfolio_table
    2. Format bebas: "BBCA 10 lot 5900", "BELI MIKA 5 lot 1700", dll.
    """
    # Auto-deteksi: kalau mirip tabel Stockbit, pakai parser khusus
    if _is_stockbit_portfolio_table(raw_text):
        return parse_stockbit_portfolio_table(raw_text)

    # ── Parser format bebas (original) ───────────────────
    parsed = []
    errors = []
    lines = [l.strip() for l in raw_text.strip().split("\n") if l.strip()]

    for idx, line in enumerate(lines):
        try:
            # Lewati baris header
            if any(h in line.lower() for h in ["ticker", "saham", "emiten", "kode"]) and \
               any(h in line.lower() for h in ["harga", "price", "lot", "qty"]):
                continue

            # Cari kode saham (4 huruf)
            raw_words = re.findall(r"\b[A-Za-z]{3,5}\b", line)
            exclude = {"BELI", "JUAL", "SELL", "LOTS", "LEMBAR", "SAHAM", "HARGA", "PRICE"}
            ticker_candidates = [w.upper() for w in raw_words if w.upper() not in exclude and len(w) >= 3]
            if not ticker_candidates:
                continue
            ticker = ticker_candidates[0][:4]

            # Deteksi BUY / SELL
            line_upper = line.upper()
            tx_type = "SELL" if any(w in line_upper for w in ["SELL", "JUAL"]) else "BUY"

            lot_val   = 0
            price_val = 0.0

            # Pola eksplisit: X lot @ harga
            explicit_lot = re.search(r"(\d+)\s*(?:lot|lembar)", line, re.I)
            if explicit_lot:
                lot_val = int(clean_currency(explicit_lot.group(1)))
                remain = line.replace(explicit_lot.group(0), "")
                remain = re.sub(r"(?i)\b(buy|sell|beli|jual|rp|harga|@)\b", " ", remain).replace(ticker, " ")
                prices = re.findall(r"\b\d+(?:[.,]\d+)?\b", remain)
                if prices:
                    price_val = float(clean_currency(prices[0]))

            # Fallback: 2 angka pertama = lot & harga
            if lot_val <= 0 or price_val <= 0:
                cleaned = re.sub(r"(?i)\b(lot|lembar|rp|shares?|buy|sell|beli|jual|harga|@)\b", " ", line)
                cleaned = cleaned.replace(ticker, " ")
                numbers = re.findall(r"\b\d+(?:[.,]\d+)?\b", cleaned)
                clean_nums = [clean_currency(n) for n in numbers if clean_currency(n) > 0]
                if len(clean_nums) >= 2:
                    lot_val   = int(clean_nums[0])
                    price_val = float(clean_nums[1])

            if lot_val > 0 and price_val > 0:
                parsed.append({
                    "ticker": ticker,
                    "type":   tx_type,
                    "date":   datetime.now().strftime("%Y-%m-%d"),
                    "lot":    lot_val,
                    "price":  price_val,
                    "fee":    0.0,
                    "tax":    0.0,
                    "notes":  "Input Cepat",
                })
        except Exception as e:
            errors.append(f"Baris '{line}': {str(e)}")

    return parsed, errors

