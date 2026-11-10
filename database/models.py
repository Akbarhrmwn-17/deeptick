"""database/models.py — Data access layer (queries & mutations)"""

import sqlite3
from typing import Optional, List, Dict, Any
from database.db import get_connection
from config import DEFAULT_BUY_FEE_PCT, DEFAULT_SELL_FEE_PCT, SELL_TAX_PCT, LOT_SIZE


# ════════════════════════════════════════════════════════
# WATCHLIST
# ════════════════════════════════════════════════════════

def add_to_watchlist(ticker: str, name: str, sector: str = "") -> bool:
    """Add a stock to the watchlist. Returns True if added, False if duplicate."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO watchlist(ticker, name, sector) VALUES (?,?,?)",
            (ticker.upper(), name, sector)
        )
        conn.commit()
        return conn.total_changes > 0
    finally:
        conn.close()


def remove_from_watchlist(ticker: str):
    conn = get_connection()
    conn.execute("UPDATE watchlist SET is_active=0 WHERE ticker=?", (ticker.upper(),))
    conn.commit()
    conn.close()


def get_watchlist() -> List[Dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM watchlist WHERE is_active=1 ORDER BY ticker"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ════════════════════════════════════════════════════════
# PRICE HISTORY
# ════════════════════════════════════════════════════════

def upsert_price_history(ticker: str, records: List[Dict]):
    """Bulk insert/update OHLCV records."""
    conn = get_connection()
    conn.executemany(
        """INSERT OR REPLACE INTO price_history(ticker, date, open, high, low, close, volume)
           VALUES (:ticker, :date, :open, :high, :low, :close, :volume)""",
        [{"ticker": ticker.upper(), **r} for r in records]
    )
    conn.commit()
    conn.close()


def get_price_history(ticker: str, limit: int = 365) -> List[Dict]:
    conn = get_connection()
    rows = conn.execute(
        """SELECT * FROM price_history WHERE ticker=?
           ORDER BY date DESC LIMIT ?""",
        (ticker.upper(), limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]


def get_latest_price(ticker: str) -> Optional[Dict]:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM price_history WHERE ticker=? ORDER BY date DESC LIMIT 1",
        (ticker.upper(),)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# ════════════════════════════════════════════════════════
# FUNDAMENTAL
# ════════════════════════════════════════════════════════

def upsert_fundamental(ticker: str, data: Dict):
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO fundamental
           (ticker, fetched_at, pe_ratio, pb_ratio, der, roe, eps,
            revenue, net_profit, market_cap, dividend_yield)
           VALUES (:ticker, datetime('now','localtime'), :pe_ratio, :pb_ratio, :der, :roe,
                   :eps, :revenue, :net_profit, :market_cap, :dividend_yield)""",
        {"ticker": ticker.upper(), **data}
    )
    conn.commit()
    conn.close()


def get_fundamental(ticker: str) -> Optional[Dict]:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM fundamental WHERE ticker=?", (ticker.upper(),)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# ════════════════════════════════════════════════════════
# TRANSACTIONS
# ════════════════════════════════════════════════════════

def add_transaction(
    ticker: str,
    tx_type: str,
    date: str,
    lot: float,
    price: float,
    fee: Optional[float] = None,
    tax: Optional[float] = None,
    notes: str = ""
) -> int:
    """Add a BUY or SELL transaction. Returns the new row id."""
    total_value = lot * LOT_SIZE * price
    if fee is None:
        pct = DEFAULT_BUY_FEE_PCT if tx_type == "BUY" else DEFAULT_SELL_FEE_PCT
        fee = round(total_value * pct, 2)
    if tax is None:
        tax = round(total_value * SELL_TAX_PCT, 2) if tx_type == "SELL" else 0.0

    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO transactions(ticker, type, date, lot, price, fee, tax, notes)
           VALUES (?,?,?,?,?,?,?,?)""",
        (ticker.upper(), tx_type, date, lot, price, fee, tax, notes)
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def delete_transaction(tx_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM transactions WHERE id=?", (tx_id,))
    conn.commit()
    conn.close()


def get_all_transactions(ticker: Optional[str] = None) -> List[Dict]:
    conn = get_connection()
    if ticker:
        rows = conn.execute(
            "SELECT * FROM transactions WHERE ticker=? ORDER BY date DESC, id DESC",
            (ticker.upper(),)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM transactions ORDER BY date DESC, id DESC"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_portfolio_summary() -> List[Dict]:
    """
    Calculate current holdings: average price, total lot, unrealized P&L placeholder.
    Returns list of dicts per ticker.
    """
    conn = get_connection()
    rows = conn.execute("""
        SELECT
            ticker,
            SUM(CASE WHEN type='BUY'  THEN lot ELSE -lot END)  AS net_lot,
            SUM(CASE WHEN type='BUY'  THEN lot*price ELSE 0 END) AS total_buy_value,
            SUM(CASE WHEN type='BUY'  THEN lot ELSE 0 END)       AS total_buy_lot,
            SUM(CASE WHEN type='SELL' THEN lot*price ELSE 0 END) AS total_sell_value,
            SUM(CASE WHEN type='SELL' THEN lot ELSE 0 END)       AS total_sell_lot,
            SUM(CASE WHEN type='BUY'  THEN fee ELSE 0 END)       AS total_buy_fee,
            SUM(CASE WHEN type='SELL' THEN fee+tax ELSE 0 END)   AS total_sell_cost
        FROM transactions
        GROUP BY ticker
        HAVING net_lot > 0
        ORDER BY ticker
    """).fetchall()
    conn.close()

    result = []
    for r in rows:
        d = dict(r)
        if d["total_buy_lot"] > 0:
            # Nilai beli total dibagi total lembar (lot * 100)
            # Karena total_buy_value = lot * price, maka total uang = lot * 100 * price
            # Maka avg_price per lembar = (total_uang + fee) / (lot * 100) = price + (fee/(lot*100))
            total_shares = d["total_buy_lot"] * LOT_SIZE
            total_cost = (d["total_buy_value"] * LOT_SIZE) + d["total_buy_fee"]
            d["avg_price"] = round(total_cost / total_shares, 2)
        else:
            d["avg_price"] = 0
        result.append(d)
    return result


def get_realized_pl() -> List[Dict]:
    """Realized P&L per ticker using FIFO approximation via average cost."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT
            ticker,
            SUM(CASE WHEN type='SELL' THEN lot*price - fee - tax ELSE 0 END) AS sell_proceeds,
            SUM(CASE WHEN type='BUY'  THEN lot*price + fee ELSE 0 END)        AS total_cost,
            SUM(CASE WHEN type='BUY'  THEN lot ELSE 0 END)                    AS total_buy_lot,
            SUM(CASE WHEN type='SELL' THEN lot ELSE 0 END)                    AS total_sell_lot
        FROM transactions
        GROUP BY ticker
        HAVING total_sell_lot > 0
        ORDER BY ticker
    """).fetchall()
    conn.close()

    result = []
    for r in rows:
        d = dict(r)
        if d["total_buy_lot"] > 0:
            avg_cost = d["total_cost"] / (d["total_buy_lot"] * LOT_SIZE)
            cost_of_sold = avg_cost * d["total_sell_lot"] * LOT_SIZE
            d["realized_pl"] = round(d["sell_proceeds"] - cost_of_sold, 2)
        else:
            d["realized_pl"] = 0
        result.append(d)
    return result


# ════════════════════════════════════════════════════════
# SIGNALS
# ════════════════════════════════════════════════════════

def save_signal(ticker: str, signal_type: str, strength: int, reason: str):
    conn = get_connection()
    conn.execute(
        """INSERT INTO signals(ticker, signal_type, strength, reason)
           VALUES (?,?,?,?)""",
        (ticker.upper(), signal_type, strength, reason)
    )
    conn.commit()
    conn.close()


def get_signals(limit: int = 50) -> List[Dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM signals ORDER BY generated_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_unnotified_signals() -> List[Dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM signals WHERE is_notified=0 ORDER BY generated_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_signal_notified(signal_id: int):
    conn = get_connection()
    conn.execute("UPDATE signals SET is_notified=1 WHERE id=?", (signal_id,))
    conn.commit()
    conn.close()


# ════════════════════════════════════════════════════════
# ALERT RULES
# ════════════════════════════════════════════════════════

def add_alert_rule(ticker: str, rule_type: str, value: float):
    conn = get_connection()
    conn.execute(
        "INSERT INTO alert_rules(ticker, rule_type, value) VALUES (?,?,?)",
        (ticker.upper(), rule_type, value)
    )
    conn.commit()
    conn.close()


def get_alert_rules(ticker: Optional[str] = None) -> List[Dict]:
    conn = get_connection()
    if ticker:
        rows = conn.execute(
            "SELECT * FROM alert_rules WHERE ticker=? AND is_active=1",
            (ticker.upper(),)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM alert_rules WHERE is_active=1 ORDER BY ticker"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_alert_rule(rule_id: int):
    conn = get_connection()
    conn.execute("UPDATE alert_rules SET is_active=0 WHERE id=?", (rule_id,))
    conn.commit()
    conn.close()


# ════════════════════════════════════════════════════════
# SETTINGS
# ════════════════════════════════════════════════════════

def get_setting(key: str, default: str = "") -> str:
    conn = get_connection()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key: str, value: str):
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO settings(key, value) VALUES (?,?)", (key, value)
    )
    conn.commit()
    conn.close()
