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


def fetch_dividend_info(ticker: str) -> Dict:
    """
    Ambil data dividen dan aksi korporasi untuk emiten tertentu via yfinance.
    """
    import yfinance as yf
    from datetime import datetime
    from config import YF_SUFFIX
    
    clean_t = ticker.upper().replace(".JK", "").strip()
    yf_symbol = f"{clean_t}{YF_SUFFIX}"
    try:
        t_obj = yf.Ticker(yf_symbol)
        info = t_obj.info or {}
        
        # Ex-Dividend Date
        ex_div_ts = info.get("exDividendDate")
        ex_div_str = None
        if ex_div_ts:
            try:
                ex_div_str = datetime.fromtimestamp(ex_div_ts).strftime("%Y-%m-%d")
            except Exception:
                ex_div_str = str(ex_div_ts)[:10]
                
        # Dividend yield & rate
        div_yield = info.get("dividendYield")
        if div_yield is not None:
            div_yield_pct = div_yield * 100.0 if div_yield < 1.0 else float(div_yield)
        else:
            div_yield_pct = 0.0
            
        div_rate = float(info.get("trailingAnnualDividendRate") or info.get("dividendRate") or 0.0)
        payout_ratio = float((info.get("payoutRatio") or 0.0) * 100.0)
        
        # Recent dividends from history
        div_series = t_obj.dividends
        last_div_amount = float(div_series.iloc[-1]) if not div_series.empty else div_rate
        last_div_date = str(div_series.index[-1])[:10] if not div_series.empty else ex_div_str
        
        return {
            "ticker": clean_t,
            "dividend_yield": round(div_yield_pct, 2),
            "dividend_rate": round(div_rate, 2),
            "last_dividend": round(last_div_amount, 2),
            "last_div_date": last_div_date or "-",
            "ex_dividend_date": ex_div_str or last_div_date or "-",
            "payout_ratio": round(payout_ratio, 2),
        }
    except Exception:
        return {
            "ticker": clean_t,
            "dividend_yield": 0.0,
            "dividend_rate": 0.0,
            "last_dividend": 0.0,
            "last_div_date": "-",
            "ex_dividend_date": "-",
            "payout_ratio": 0.0,
        }


def get_dividend_calendar(tickers: list = None) -> list:
    """
    Ambil kalender dividen terstruktur untuk daftar emiten, diurutkan berdasarkan yield terbesar.
    """
    from data.idx_universe import IDX_UNIVERSE
    idx_map = {item["ticker"]: item for item in IDX_UNIVERSE}

    if not tickers:
        # Default fokus ke emiten pembagi dividen populer & emiten LQ45
        tickers = ["PTBA", "ITMG", "ADRO", "BBCA", "BBRI", "BMRI", "BBNI", "TLKM", "ASII", "UNTR", "ICBP", "INDF", "PGAS", "SMGR", "CPIN"]

    results = []
    for t in tickers:
        d = fetch_dividend_info(t)
        meta = idx_map.get(t, {})
        d["name"] = meta.get("name", t)
        d["sector"] = meta.get("sector", "Umum")
        results.append(d)

    # Sort descending by dividend yield
    results.sort(key=lambda x: x.get("dividend_yield", 0.0), reverse=True)
    return results

