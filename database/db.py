"""database/db.py — SQLite connection & schema initialization"""

import sqlite3
import os
from config import DB_PATH


def get_connection() -> sqlite3.Connection:
    """Return a SQLite connection with row_factory set for dict-like access."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create all tables if they don't exist."""
    conn = get_connection()
    cur = conn.cursor()

    # ── Watchlist ──────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS watchlist (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker      TEXT    NOT NULL UNIQUE,
            name        TEXT    NOT NULL,
            sector      TEXT    DEFAULT '',
            added_at    TEXT    DEFAULT (datetime('now','localtime')),
            is_active   INTEGER DEFAULT 1
        )
    """)

    # ── Price History ─────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS price_history (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker  TEXT    NOT NULL,
            date    TEXT    NOT NULL,
            open    REAL,
            high    REAL,
            low     REAL,
            close   REAL,
            volume  INTEGER,
            UNIQUE(ticker, date)
        )
    """)

    # ── Fundamental Data ──────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS fundamental (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker          TEXT    NOT NULL,
            fetched_at      TEXT    DEFAULT (datetime('now','localtime')),
            pe_ratio        REAL,
            pb_ratio        REAL,
            der             REAL,
            roe             REAL,
            eps             REAL,
            revenue         REAL,
            net_profit      REAL,
            market_cap      REAL,
            dividend_yield  REAL,
            UNIQUE(ticker)
        )
    """)

    # ── Transactions ──────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker      TEXT    NOT NULL,
            type        TEXT    NOT NULL CHECK(type IN ('BUY','SELL')),
            date        TEXT    NOT NULL,
            lot         REAL    NOT NULL,
            price       REAL    NOT NULL,
            fee         REAL    DEFAULT 0,
            tax         REAL    DEFAULT 0,
            notes       TEXT    DEFAULT '',
            created_at  TEXT    DEFAULT (datetime('now','localtime'))
        )
    """)

    # ── Signals ───────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker          TEXT    NOT NULL,
            signal_type     TEXT    NOT NULL,
            strength        INTEGER DEFAULT 0,
            reason          TEXT    DEFAULT '',
            generated_at    TEXT    DEFAULT (datetime('now','localtime')),
            is_notified     INTEGER DEFAULT 0
        )
    """)

    # ── Alert Rules ───────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS alert_rules (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker      TEXT    NOT NULL,
            rule_type   TEXT    NOT NULL,
            value       REAL,
            is_active   INTEGER DEFAULT 1,
            created_at  TEXT    DEFAULT (datetime('now','localtime'))
        )
    """)

    # ── App Settings ──────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key     TEXT PRIMARY KEY,
            value   TEXT
        )
    """)

    # ── Default Settings ──────────────────────────────────
    defaults = [
        ("buy_fee_pct",  "0.0015"),
        ("sell_fee_pct", "0.0025"),
        ("sell_tax_pct", "0.001"),
        ("broker_name",  "Default"),
    ]
    cur.executemany(
        "INSERT OR IGNORE INTO settings(key, value) VALUES (?,?)", defaults
    )

    conn.commit()
    conn.close()
    print("[DB] Database initialized.")


if __name__ == "__main__":
    init_db()
