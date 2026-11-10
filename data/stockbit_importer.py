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


def parse_pasted_text(raw_text: str) -> Tuple[List[Dict], List[str]]:
    """
    Parser untuk teks bebas hasil copy-paste dari layar Stockbit / chat / catatan.
    Mendukung format baris seperti:
    - BBCA 10 lot 5900
    - BELI MIKA 5 lot 1700
    - GOTO 50 26
    - TLKM BUY 15 @ 3100
    Atau baris tabel hasil copy-paste dari web (dipisahkan spasi/tab).
    """
    parsed = []
    errors = []
    lines = [l.strip() for l in raw_text.strip().split("\n") if l.strip()]

    for idx, line in enumerate(lines):
        try:
            # Lewati baris header jika ada
            if any(h in line.lower() for h in ["ticker", "saham", "emiten", "kode"]) and any(h in line.lower() for h in ["harga", "price", "lot", "qty"]):
                continue

            # Cari Kode Saham (4 huruf, abaikan kata BELI/JUAL)
            raw_words = re.findall(r"\b[A-Za-z]{4}\b", line)
            ticker_candidates = [w.upper() for w in raw_words if w.upper() not in ["BELI", "JUAL", "SELL", "LOTS"]]
            if not ticker_candidates:
                continue
            ticker = ticker_candidates[0]

            # Deteksi Action (BUY/SELL)
            line_upper = line.upper()
            if any(w in line_upper for w in ["SELL", "JUAL", " S "]):
                tx_type = "SELL"
            else:
                tx_type = "BUY"

            lot_val = 0
            price_val = 0.0

            # Pola 1: Mencari format 'X lot' secara eksplisit
            explicit_lot = re.search(r"(\d+)\s*(?:lot|lembar)", line, re.I)
            if explicit_lot:
                lot_val = int(clean_currency(explicit_lot.group(1)))
                remain = line.replace(explicit_lot.group(0), "")
                remain = re.sub(r"(?i)\b(buy|sell|beli|jual|rp|harga|@)\b", " ", remain).replace(ticker, " ")
                prices = re.findall(r"\b\d+(?:[.,]\d+)?\b", remain)
                if prices:
                    price_val = float(clean_currency(prices[0]))

            # Pola 2: Angka biasa (misal: BBCA 10 5900)
            if lot_val <= 0 or price_val <= 0:
                cleaned_line = re.sub(r"(?i)\b(lot|lembar|rp|shares?|buy|sell|beli|jual|harga|@)\b", " ", line)
                cleaned_line = cleaned_line.replace(ticker, " ")
                numbers = re.findall(r"\b\d+(?:[.,]\d+)?\b", cleaned_line)
                clean_nums = [clean_currency(n) for n in numbers if clean_currency(n) > 0]
                if len(clean_nums) >= 2:
                    lot_val = int(clean_nums[0])
                    price_val = float(clean_nums[1])

            if lot_val > 0 and price_val > 0:
                parsed.append({
                    "ticker": ticker,
                    "type": tx_type,
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "lot": lot_val,
                    "price": price_val,
                    "fee": 0.0,
                    "tax": 0.0,
                    "notes": "Input Cepat",
                })
        except Exception as e:
            errors.append(f"Baris '{line}': {str(e)}")

    return parsed, errors

