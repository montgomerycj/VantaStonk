"""
VantaStonk — Database Layer

SQLite connection manager and query helpers.
Wires up the schema from sql/schema.sql.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

DB_PATH = "data/vantastonk.db"
SCHEMA_PATH = "sql/schema.sql"


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Get a SQLite connection with row factory enabled."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: str = DB_PATH):
    """Initialize the database from schema.sql."""
    conn = get_connection(db_path)
    schema = Path(SCHEMA_PATH).read_text()
    conn.executescript(schema)
    conn.commit()
    conn.close()
    print(f"Database initialized at {db_path}")


# --- Tickers ---

def upsert_ticker(conn: sqlite3.Connection, ticker: str, company_name: str = None,
                  sector: str = None, market_cap_millions: float = None, has_options: bool = True):
    """Insert or update a ticker in the registry."""
    conn.execute("""
        INSERT INTO tickers (ticker, company_name, sector, market_cap_millions, has_options)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(ticker) DO UPDATE SET
            company_name = COALESCE(excluded.company_name, company_name),
            sector = COALESCE(excluded.sector, sector),
            market_cap_millions = COALESCE(excluded.market_cap_millions, market_cap_millions),
            has_options = excluded.has_options
    """, (ticker, company_name, sector, market_cap_millions, has_options))
    conn.commit()


# --- Price Snapshots ---

def save_price_snapshot(conn: sqlite3.Connection, ticker: str, price: float,
                        volume: int = None, source: str = "schwab"):
    """Save a price snapshot."""
    now = datetime.now()
    conn.execute("""
        INSERT OR IGNORE INTO price_snapshots (ticker, price, volume, snapshot_date, snapshot_time, source)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (ticker, price, volume, now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"), source))
    conn.commit()


def get_price_history(conn: sqlite3.Connection, ticker: str, days: int = 10) -> list[dict]:
    """Get recent price snapshots for a ticker."""
    rows = conn.execute("""
        SELECT price, volume, snapshot_date, snapshot_time
        FROM price_snapshots
        WHERE ticker = ?
        ORDER BY snapshot_date DESC, snapshot_time DESC
        LIMIT ?
    """, (ticker, days)).fetchall()
    return [dict(r) for r in rows]


# --- Signal Scores ---

def save_score(conn: sqlite3.Connection, ticker: str, score_result) -> int:
    """Save a ScoreResult to signal_scores. Returns the row id."""
    cursor = conn.execute("""
        INSERT INTO signal_scores
            (ticker, run_date, total_score, raw_score, grade,
             catalyst_score, prompt_pulse_score, freshness_score,
             peer_score, volume_score, macro_score, penalties)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        ticker,
        datetime.now().strftime("%Y-%m-%d"),
        score_result.total,
        score_result.raw_total,
        score_result.grade,
        score_result.breakdown.get("catalyst", 0),
        score_result.breakdown.get("prompt_pulse", 0),
        score_result.breakdown.get("freshness", 0),
        score_result.breakdown.get("peer", 0),
        score_result.breakdown.get("volume", 0),
        score_result.breakdown.get("macro", 0),
        json.dumps(score_result.penalties_applied),
    ))
    conn.commit()
    return cursor.lastrowid


# --- Recommendations ---

def save_recommendation(conn: sqlite3.Connection, ticker: str, module: str,
                        category: str = None, setup: str = None, why_now: str = None,
                        catalyst: str = None, not_priced_in: str = None,
                        risk: str = None, score_total: float = None):
    """Save a recommendation (Glance, ShadowList, or Shorties pick)."""
    conn.execute("""
        INSERT INTO recommendations
            (ticker, run_date, module, category, setup, why_now, catalyst, not_priced_in, risk, score_total)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (ticker, datetime.now().strftime("%Y-%m-%d"), module, category, setup, why_now,
          catalyst, not_priced_in, risk, score_total))
    conn.commit()


# --- ShadowList ---

def save_shadowlist_entry(conn: sqlite3.Connection, ticker: str, why_interesting: str,
                          why_not_ready: str, trigger_condition: str):
    """Save a new ShadowList entry."""
    conn.execute("""
        INSERT INTO shadowlist_entries
            (ticker, why_interesting, why_not_ready, trigger_condition, added_date, status)
        VALUES (?, ?, ?, ?, ?, 'active')
    """, (ticker, why_interesting, why_not_ready, trigger_condition, datetime.now().strftime("%Y-%m-%d")))
    conn.commit()


def get_active_shadowlist(conn: sqlite3.Connection) -> list[dict]:
    """Get all active ShadowList entries."""
    rows = conn.execute("""
        SELECT * FROM shadowlist_entries WHERE status = 'active' ORDER BY added_date DESC
    """).fetchall()
    return [dict(r) for r in rows]


def graduate_shadowlist(conn: sqlite3.Connection, ticker: str):
    """Graduate a ShadowList entry (triggered → ready for Glance)."""
    conn.execute("""
        UPDATE shadowlist_entries SET status = 'graduated', graduated_date = ?
        WHERE ticker = ? AND status = 'active'
    """, (datetime.now().strftime("%Y-%m-%d"), ticker))
    conn.commit()


# --- Near Misses ---

def save_near_miss(conn: sqlite3.Connection, ticker: str, total_score: float, miss_reason: str):
    """Log a near miss (scored close but didn't make the cut)."""
    conn.execute("""
        INSERT INTO near_misses (ticker, run_date, total_score, miss_reason)
        VALUES (?, ?, ?, ?)
    """, (ticker, datetime.now().strftime("%Y-%m-%d"), total_score, miss_reason))
    conn.commit()


# --- Trade Journal ---

def log_trade(conn: sqlite3.Connection, ticker: str, direction: str,
              entry_date: str, entry_price: float, shares: int = None,
              module: str = None, notes: str = None) -> int:
    """Log a trade entry. Returns the row id."""
    cursor = conn.execute("""
        INSERT INTO trade_journal (ticker, direction, entry_date, entry_price, shares, module, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (ticker, direction, entry_date, entry_price, shares, module, notes))
    conn.commit()
    return cursor.lastrowid


def close_trade(conn: sqlite3.Connection, trade_id: int, exit_date: str,
                exit_price: float):
    """Close an open trade with exit info. Auto-calculates P&L."""
    row = conn.execute("SELECT entry_price, shares FROM trade_journal WHERE id = ?", (trade_id,)).fetchone()
    if not row:
        return

    entry_price = row["entry_price"]
    shares = row["shares"] or 0
    pnl = (exit_price - entry_price) * shares
    pnl_pct = ((exit_price - entry_price) / entry_price * 100) if entry_price else 0

    conn.execute("""
        UPDATE trade_journal SET exit_date = ?, exit_price = ?, pnl = ?, pnl_pct = ?
        WHERE id = ?
    """, (exit_date, exit_price, round(pnl, 2), round(pnl_pct, 2), trade_id))
    conn.commit()


def get_open_trades(conn: sqlite3.Connection) -> list[dict]:
    """Get all trades that haven't been closed yet."""
    rows = conn.execute("""
        SELECT * FROM trade_journal WHERE exit_date IS NULL ORDER BY entry_date DESC
    """).fetchall()
    return [dict(r) for r in rows]


def get_trade_stats(conn: sqlite3.Connection) -> dict:
    """Get aggregate trade statistics."""
    total = conn.execute("SELECT COUNT(*) as n FROM trade_journal WHERE exit_date IS NOT NULL").fetchone()
    wins = conn.execute("SELECT COUNT(*) as n FROM trade_journal WHERE pnl > 0").fetchone()
    total_pnl = conn.execute("SELECT COALESCE(SUM(pnl), 0) as total FROM trade_journal").fetchone()

    total_n = total["n"] if total else 0
    win_n = wins["n"] if wins else 0

    return {
        "total_trades": total_n,
        "wins": win_n,
        "losses": total_n - win_n,
        "win_rate": round(win_n / total_n * 100, 1) if total_n > 0 else 0,
        "total_pnl": total_pnl["total"] if total_pnl else 0,
    }
