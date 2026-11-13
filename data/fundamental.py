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


# ════════════════════════════════════════════════════════════════
# QUARTERLY FINANCIAL STATEMENTS & PIOTROSKI F-SCORE ENGINE
# ════════════════════════════════════════════════════════════════

_QUARTERLY_CACHE = {}
_CACHE_TTL_SEC = 3600 * 6  # 6 jam TTL karena laporan kuartalan dirilis 3 bulan sekali


def fetch_quarterly_financials(ticker: str, use_cache: bool = True) -> Dict:
    """
    Ekstraksi Laporan Keuangan Kuartalan (Income Statement, Balance Sheet, Cash Flow),
    menghitung pertumbuhan YoY/QoQ, Kualitas Laba (OCF vs Net Income),
    serta Piotroski F-Score (0 - 9).
    """
    import yfinance as yf
    import pandas as pd
    import time
    from config import YF_SUFFIX

    clean_t = ticker.upper().replace(".JK", "").strip()
    cache_key = clean_t
    now = time.time()

    if use_cache and cache_key in _QUARTERLY_CACHE:
        cached_time, cached_val = _QUARTERLY_CACHE[cache_key]
        if now - cached_time < _CACHE_TTL_SEC:
            return cached_val

    yf_symbol = f"{clean_t}{YF_SUFFIX}"
    empty_result = {
        "available": False,
        "ticker": clean_t,
        "latest_quarter": "-",
        "revenue": None,
        "revenue_yoy_pct": None,
        "revenue_qoq_pct": None,
        "net_income": None,
        "net_income_yoy_pct": None,
        "net_income_qoq_pct": None,
        "operating_cash_flow": None,
        "f_score": 0,
        "f_criteria": {},
        "quality_of_earnings": "Data Tidak Tersedia",
        "quality_status": "UNKNOWN",
        "historical_quarters": [],
    }

    try:
        t_obj = yf.Ticker(yf_symbol)
        inc = t_obj.quarterly_income_stmt
        bs = t_obj.quarterly_balance_sheet
        cf = t_obj.quarterly_cashflow

        if inc is None or inc.empty:
            # Fallback ke t_obj.info untuk emiten IPO baru / Papan Akselerasi / Small-cap
            info = t_obj.info or {}
            rev_val = info.get("totalRevenue")
            rev_growth = info.get("revenueGrowth")
            rev_yoy_pct = round(rev_growth * 100, 2) if rev_growth is not None else None

            ni_val = info.get("netIncomeToCommon")
            earn_growth = info.get("earningsGrowth")
            ni_yoy_pct = round(earn_growth * 100, 2) if earn_growth is not None else None

            ocf_val = info.get("operatingCashflow")
            roa_val = info.get("returnOnAssets")
            cr_val = info.get("currentRatio")
            der_val = info.get("debtToEquity")
            gm_val = info.get("grossMargins")

            if rev_val is not None or ni_val is not None or ocf_val is not None:
                f_crit = {
                    "ROA Positif": bool(roa_val is not None and roa_val > 0),
                    "Arus Kas Operasional Positif": bool(ocf_val is not None and ocf_val > 0),
                    "Pertumbuhan Laba Positif": bool(ni_val is not None and ni_val > 0),
                    "Kualitas Kas (CFO > Laba Bersih)": bool(ocf_val is not None and ni_val is not None and ocf_val > ni_val),
                    "Rasio Utang Aman (DER < 100)": bool(der_val is not None and der_val < 100),
                    "Likuiditas Lancar Aman (CR > 1.2)": bool(cr_val is not None and cr_val > 1.2),
                    "Tanpa Dilusi Saham (Stabil)": True,
                    "Margin Laba Kotor Positif": bool(gm_val is not None and gm_val > 0),
                    "Perputaran Aset Positif": bool(rev_val is not None and rev_val > 0),
                }
                f_score_val = sum(1 for v in f_crit.values() if v)

                if ocf_val is not None and ocf_val < 0:
                    q_stat = "NEGATIVE_CFO"
                    q_str = f"BAHAYA: Arus Kas Operasional Negatif (Bakar Kas Rp {abs(ocf_val)/1e9:,.1f} M)"
                elif ocf_val and ni_val and ocf_val > ni_val:
                    q_stat = "HEALTHY"
                    q_str = "SANGAT SEHAT: Uang Kas Riil > Laba Akuntansi"
                else:
                    q_stat = "ACCRUAL_WARNING"
                    q_str = "WASPADA: Laba Didorong Akrual / Piutang Belum Cair"

                fallback_res = {
                    "available": True,
                    "ticker": clean_t,
                    "latest_quarter": "TTM / Berjalan (Papan Akselerasi / IPO Baru)",
                    "revenue": rev_val,
                    "revenue_yoy_pct": rev_yoy_pct,
                    "revenue_qoq_pct": None,
                    "net_income": ni_val,
                    "net_income_yoy_pct": ni_yoy_pct,
                    "net_income_qoq_pct": None,
                    "operating_cash_flow": ocf_val,
                    "f_score": f_score_val,
                    "f_criteria": f_crit,
                    "quality_of_earnings": q_str,
                    "quality_status": q_stat,
                    "historical_quarters": [],
                }
                _QUARTERLY_CACHE[cache_key] = (now, fallback_res)
                return fallback_res

            _QUARTERLY_CACHE[cache_key] = (now, empty_result)
            return empty_result

        def _get_row(df, candidate_list):
            if df is None or df.empty:
                return None
            # 1. Exact match
            for c in candidate_list:
                for idx in df.index:
                    if str(idx).strip().lower() == c.strip().lower():
                        return df.loc[idx]
            # 2. Substring match
            for c in candidate_list:
                for idx in df.index:
                    idx_clean = str(idx).strip().lower()
                    if c.strip().lower() in idx_clean:
                        if "non" in idx_clean and "non" not in c.strip().lower():
                            continue
                        return df.loc[idx]
            return None

        rev_row = _get_row(inc, ["Total Revenue", "Operating Revenue", "Net Interest Income", "Interest Income"])
        net_inc_row = _get_row(inc, ["Net Income Common Stockholders", "Net Income", "Net Income From Continuing Operation Net Minority Interest"])
        gross_row = _get_row(inc, ["Gross Profit", "Net Interest Income"])
        ocf_row = _get_row(cf, ["Operating Cash Flow", "Cash Flowsfromusedin Operating Activities Direct", "Cash Flow From Continuing Operating Activities"])
        assets_row = _get_row(bs, ["Total Assets"])
        debt_row = _get_row(bs, ["Total Debt", "Long Term Debt", "Total Liabilities Net Minority Interest"])
        ca_row = _get_row(bs, ["Current Assets"])
        cl_row = _get_row(bs, ["Current Liabilities"])
        shares_row = _get_row(bs, ["Ordinary Shares Number", "Share Issued"])

        dates = [str(c)[:10] for c in inc.columns]

        def _safe_val(series, idx=0):
            if series is None:
                return None
            try:
                if idx < len(series):
                    val = series.iloc[idx]
                    if pd.isna(val):
                        return None
                    return float(val)
                return None
            except Exception:
                return None

        rev_0 = _safe_val(rev_row, 0)
        rev_1 = _safe_val(rev_row, 1) if len(inc.columns) > 1 else None
        rev_yoy = _safe_val(rev_row, 4) if len(inc.columns) > 4 else None

        ni_0 = _safe_val(net_inc_row, 0)
        ni_1 = _safe_val(net_inc_row, 1) if len(inc.columns) > 1 else None
        ni_yoy = _safe_val(net_inc_row, 4) if len(inc.columns) > 4 else None

        ocf_0 = _safe_val(ocf_row, 0)
        assets_0 = _safe_val(assets_row, 0)
        assets_1 = _safe_val(assets_row, 1) if bs is not None and len(bs.columns) > 1 else None
        debt_0 = _safe_val(debt_row, 0)
        debt_1 = _safe_val(debt_row, 1) if bs is not None and len(bs.columns) > 1 else None

        # Growth metrics
        rev_yoy_pct = round(((rev_0 - rev_yoy) / abs(rev_yoy)) * 100, 2) if rev_0 and rev_yoy and rev_yoy != 0 else None
        rev_qoq_pct = round(((rev_0 - rev_1) / abs(rev_1)) * 100, 2) if rev_0 and rev_1 and rev_1 != 0 else None

        ni_yoy_pct = round(((ni_0 - ni_yoy) / abs(ni_yoy)) * 100, 2) if ni_0 and ni_yoy and ni_yoy != 0 else None
        ni_qoq_pct = round(((ni_0 - ni_1) / abs(ni_1)) * 100, 2) if ni_0 and ni_1 and ni_1 != 0 else None

        # Piotroski F-Score (9 Items)
        f_criteria = {}

        # 1. ROA > 0
        roa_0 = (ni_0 / assets_0) if ni_0 and assets_0 and assets_0 > 0 else 0
        f_criteria["ROA Positif"] = bool(roa_0 > 0)

        # 2. CFO > 0
        f_criteria["Arus Kas Operasional Positif"] = bool(ocf_0 is not None and ocf_0 > 0)

        # 3. Delta ROA > 0
        roa_1 = (ni_1 / assets_1) if ni_1 and assets_1 and assets_1 > 0 else 0
        f_criteria["Pertumbuhan ROA (ΔROA > 0)"] = bool(roa_0 > roa_1)

        # 4. Accrual: CFO > Net Income
        cfo_gt_ni = bool(ocf_0 is not None and ni_0 is not None and ocf_0 > ni_0)
        f_criteria["Kualitas Kas (CFO > Laba Bersih)"] = cfo_gt_ni

        # 5. Delta Leverage <= 0
        lev_0 = (debt_0 / assets_0) if debt_0 and assets_0 and assets_0 > 0 else 0
        lev_1 = (debt_1 / assets_1) if debt_1 and assets_1 and assets_1 > 0 else 0
        f_criteria["Rasio Utang Menurun (ΔLeverage ≤ 0)"] = bool(lev_0 <= lev_1 if lev_1 > 0 else True)

        # 6. Delta Current Ratio > 0
        ca_0 = _safe_val(ca_row, 0)
        cl_0 = _safe_val(cl_row, 0)
        ca_1 = _safe_val(ca_row, 1) if bs is not None and len(bs.columns) > 1 else None
        cl_1 = _safe_val(cl_row, 1) if bs is not None and len(bs.columns) > 1 else None
        if ca_0 and cl_0 and ca_1 and cl_1 and cl_0 > 0 and cl_1 > 0:
            f_criteria["Likuiditas Lancar Naik (ΔCR > 0)"] = bool((ca_0 / cl_0) > (ca_1 / cl_1))
        else:
            f_criteria["Likuiditas Lancar Naik (ΔCR > 0)"] = bool(assets_0 >= assets_1 if assets_1 else True)

        # 7. No Dilution
        sh_0 = _safe_val(shares_row, 0)
        sh_1 = _safe_val(shares_row, 1) if bs is not None and len(bs.columns) > 1 else None
        f_criteria["Tanpa Dilusi Saham (Saham Beredar Stabil)"] = bool(sh_0 <= sh_1 if sh_0 and sh_1 else True)

        # 8. Delta Gross Margin > 0
        gp_0 = _safe_val(gross_row, 0)
        gp_1 = _safe_val(gross_row, 1) if inc is not None and len(inc.columns) > 1 else None
        gm_0 = (gp_0 / rev_0) if gp_0 and rev_0 and rev_0 > 0 else 0
        gm_1 = (gp_1 / rev_1) if gp_1 and rev_1 and rev_1 > 0 else 0
        f_criteria["Margin Laba Kotor Naik (ΔMargin > 0)"] = bool(gm_0 > gm_1)

        # 9. Delta Asset Turnover > 0
        at_0 = (rev_0 / assets_0) if rev_0 and assets_0 and assets_0 > 0 else 0
        at_1 = (rev_1 / assets_1) if rev_1 and assets_1 and assets_1 > 0 else 0
        f_criteria["Perputaran Aset Naik (ΔTurnover > 0)"] = bool(at_0 > at_1)

        f_score = sum(1 for v in f_criteria.values() if v)

        # Quality status
        if ocf_0 is not None and ocf_0 < 0:
            quality_status = "NEGATIVE_CFO"
            quality_str = "BAHAYA: Arus Kas Operasional Negatif (Bakar Uang)"
        elif cfo_gt_ni:
            quality_status = "HEALTHY"
            quality_str = "SANGAT SEHAT: Uang Kas Riil > Laba Akuntansi"
        else:
            quality_status = "ACCRUAL_WARNING"
            quality_str = "WASPADA: Laba Didorong Akrual / Piutang Belum Cair"

        # Historical quarterly series (chronological for charts)
        hist_cols = list(inc.columns)[:6]
        hist_cols.reverse()
        historical_quarters = []
        for d in hist_cols:
            d_str = str(d)[:10]
            r_v = float(rev_row[d]) if (rev_row is not None and d in rev_row and not pd.isna(rev_row[d])) else 0.0
            ni_v = float(net_inc_row[d]) if (net_inc_row is not None and d in net_inc_row and not pd.isna(net_inc_row[d])) else 0.0
            ocf_v = float(ocf_row[d]) if (ocf_row is not None and d in ocf_row and not pd.isna(ocf_row[d])) else 0.0
            historical_quarters.append({
                "date": d_str,
                "revenue": r_v,
                "net_income": ni_v,
                "operating_cash_flow": ocf_v,
            })

        result = {
            "available": True,
            "ticker": clean_t,
            "latest_quarter": dates[0] if dates else "-",
            "revenue": rev_0,
            "revenue_yoy_pct": rev_yoy_pct,
            "revenue_qoq_pct": rev_qoq_pct,
            "net_income": ni_0,
            "net_income_yoy_pct": ni_yoy_pct,
            "net_income_qoq_pct": ni_qoq_pct,
            "operating_cash_flow": ocf_0,
            "f_score": f_score,
            "f_criteria": f_criteria,
            "quality_of_earnings": quality_str,
            "quality_status": quality_status,
            "historical_quarters": historical_quarters,
        }

        _QUARTERLY_CACHE[cache_key] = (now, result)
        return result

    except Exception as e:
        print(f"[Fundamental] Error fetching quarterly financials for {clean_t}: {e}")
        _QUARTERLY_CACHE[cache_key] = (now, empty_result)
        return empty_result


def classify_tri_factor_grade(ticker: str, quarterly_data: Dict, cmf_value: float = 0.0) -> Dict:
    """
    Klasifikasi rating institusional berbasis Tri-Factor Convergence:
    1. Kualitas Fundamental & Pertumbuhan Laba Kuartalan (Piotroski F-Score & YoY EPS)
    2. Aliran Dana Smart Money (Chaikin Money Flow & Akumulasi)
    3. Keamanan Kas (Cash Flow vs Accounting Profit)
    """
    f_score = quarterly_data.get("f_score", 0)
    ni_yoy = quarterly_data.get("net_income_yoy_pct")
    rev_yoy = quarterly_data.get("revenue_yoy_pct")
    quality = quarterly_data.get("quality_status", "UNKNOWN")
    available = quarterly_data.get("available", False)

    if not available:
        return {
            "grade": "C",
            "title": "⚠️ GRADE C: SPEKULATIF (DATA LAPKEU MINIM)",
            "color": "#f59e0b",
            "badge": "⚠️ GRADE C (SPEKULATIF)",
            "desc": "Laporan keuangan kuartalan belum terindeks penuh di feed publik.",
            "action": "Gunakan sinyal teknikal dengan batasan risiko lot ketat.",
            "f_score": f_score,
        }

    ni_val = quarterly_data.get("net_income")
    is_burning_cash = quality == "NEGATIVE_CFO"
    is_losing_money = ni_val is not None and ni_val < 0
    is_rev_crashing = rev_yoy is not None and rev_yoy < -15.0

    # Grade D: Toxic / Trap Alert
    if f_score <= 3 or (is_burning_cash and (is_losing_money or is_rev_crashing or cmf_value < 0)):
        loss_text = f"rugi bersih Rp {abs(ni_val)/1e9:,.1f} M" if (ni_val is not None and ni_val < 0) else "arus kas minus"
        rev_text = f"omzet anjlok {rev_yoy:+.1f}% YoY" if rev_yoy else "kinerja rapuh"
        return {
            "grade": "D",
            "title": "☠️ GRADE D: TOXIC / JEBAKAN BANDAR",
            "color": "#ef4444",
            "badge": "☠️ GRADE D (RISIKO TINGGI)",
            "desc": f"Fundamental berisiko tinggi ({f_score}/9 poin). {loss_text.capitalize()}, {rev_text}, dan defisit kas operasional. Rawan kena guyuran bandar.",
            "action": "DILARANG SWING. Hanya untuk scalping cepat dengan batas Cut Loss kilat.",
            "f_score": f_score,
        }

    # Grade A: Institutional Prime
    if f_score >= 7 and (ni_yoy is not None and ni_yoy >= 0) and cmf_value >= -0.02:
        return {
            "grade": "A",
            "title": "🌟 GRADE A: INSTITUTIONAL PRIME",
            "color": "#22c55e",
            "badge": "🌟 GRADE A (INSTITUSIONAL)",
            "desc": f"Kesehatan finansial prima ({f_score}/9), laba bertumbuh positif ({ni_yoy:+.1f}% YoY), dan didukung aliran dana institusi.",
            "action": "Sangat aman untuk Swing & Position Trading. Masuk saat pullback di area support.",
            "f_score": f_score,
        }

    # Grade B: Super Growth & Momentum
    if f_score >= 5 and ((ni_yoy is not None and ni_yoy >= 15.0) or (rev_yoy is not None and rev_yoy >= 15.0)) and cmf_value >= -0.08:
        return {
            "grade": "B",
            "title": "🚀 GRADE B: SUPER GROWTH & MOMENTUM",
            "color": "#38bdf8",
            "badge": "🚀 GRADE B (SUPER GROWTH)",
            "desc": f"Percepatan laba/omzet kuartalan agresif (> +15% YoY) ala CANSLIM / Minervini. F-Score: {f_score}/9.",
            "action": "Ideal untuk Swing Momentum saat breakout pola atau retest support.",
            "f_score": f_score,
        }

    # Grade C: Spekulatif / Trading Only
    return {
        "grade": "C",
        "title": "⚠️ GRADE C: SPEKULATIF (TRADING ONLY)",
        "color": "#f59e0b",
        "badge": "⚠️ GRADE C (SPEKULATIF)",
        "desc": f"Kualitas fundamental moderat ({f_score}/9). Pergerakan harga lebih didorong oleh momentum teknikal.",
        "action": "Trading jangka pendek. Wajib pasang Stop Loss disiplin via kalkulator lot.",
        "f_score": f_score,
    }


