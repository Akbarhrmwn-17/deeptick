"""data/fundamental.py — Scraping data fundamental dari IDX dan sumber publik"""

import requests
from bs4 import BeautifulSoup
from typing import Optional, Dict
import re


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


def _safe_float(val) -> Optional[float]:
    if val is None:
        return None
    try:
        v = str(val).replace(",", "").replace("%", "").strip()
        return float(v)
    except (ValueError, TypeError):
        return None


def fetch_idx_profile(ticker: str) -> Dict:
    """
    Scrape profil perusahaan dari IDX.
    Returns dict dengan nama dan sektor.
    """
    url = f"https://www.idx.co.id/en/listed-companies/company-profiles/?kodeEmiten={ticker.upper()}"
    result = {}
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "lxml")
            # IDX menggunakan JSON di dalam script tag
            import json
            scripts = soup.find_all("script", type="application/json")
            for s in scripts:
                try:
                    data = json.loads(s.string)
                    # Cari nama dan sektor
                    if isinstance(data, dict):
                        result["name"] = data.get("CompanyName", "")
                        result["sector"] = data.get("SubIndustry", "")
                        break
                except Exception:
                    pass
    except Exception as e:
        print(f"[Fundamental] IDX profile error for {ticker}: {e}")
    return result


def fetch_stockbit_summary(ticker: str) -> Dict:
    """
    Scrape ringkasan fundamental dari halaman publik Stockbit.
    Hanya mengambil data yang tersedia tanpa login.
    """
    url = f"https://stockbit.com/symbol/{ticker.upper()}"
    result = {}
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "lxml")
            # Cari elemen data fundamental (PE, PBV, dll)
            meta_items = soup.find_all("div", class_=re.compile(r"fundamental|summary|ratio", re.I))
            for item in meta_items:
                text = item.get_text(separator=" ", strip=True)
                # Parse PE
                pe_match = re.search(r"P/E\s*[\:\s]+([0-9.,]+)", text, re.I)
                if pe_match:
                    result["pe_ratio"] = _safe_float(pe_match.group(1))
                # Parse PBV
                pb_match = re.search(r"P/B\s*[\:\s]+([0-9.,]+)", text, re.I)
                if pb_match:
                    result["pb_ratio"] = _safe_float(pb_match.group(1))
    except Exception as e:
        print(f"[Fundamental] Stockbit scrape error for {ticker}: {e}")
    return result


def get_all_fundamental(ticker: str) -> Dict:
    """
    Gabungkan data fundamental dari semua sumber.
    Primary: yfinance (sudah dihandle di fetcher.py)
    Fallback: IDX scraping
    """
    from data.fetcher import fetch_fundamental_yf
    data = fetch_fundamental_yf(ticker)

    # Coba tambah data dari Stockbit jika PE kosong
    if not data.get("pe_ratio"):
        stockbit_data = fetch_stockbit_summary(ticker)
        data.update({k: v for k, v in stockbit_data.items() if v is not None})

    return data
