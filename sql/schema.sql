-- VantaStonk 95v2 — Database Schema
-- SQLite-compatible

-- Core ticker registry
CREATE TABLE IF NOT EXISTS tickers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT UNIQUE NOT NULL,
    company_name TEXT,
    sector TEXT,
    market_cap_millions REAL,
    has_options BOOLEAN DEFAULT 1,
    added_at TEXT DEFAULT (datetime('now')),
    active BOOLEAN DEFAULT 1
);

-- Price snapshots for filter evaluation
CREATE TABLE IF NOT EXISTS price_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL REFERENCES tickers(ticker),
    price REAL NOT NULL,
    volume INTEGER,
    snapshot_date TEXT NOT NULL,
    snapshot_time TEXT,
    source TEXT,  -- e.g. 'api', 'manual'
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(ticker, snapshot_date, snapshot_time)
);

-- Catalyst events driving scoring
CREATE TABLE IF NOT EXISTS catalyst_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL REFERENCES tickers(ticker),
    event_type TEXT NOT NULL,  -- 'earnings', 'fda', 'contract', 'macro', etc.
    description TEXT,
    event_date TEXT,
    is_priced_in BOOLEAN DEFAULT 0,
    source TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Computed signal scores (one row per scoring run per ticker)
CREATE TABLE IF NOT EXISTS signal_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL REFERENCES tickers(ticker),
    run_date TEXT NOT NULL,
    total_score REAL NOT NULL,
    raw_score REAL NOT NULL,
    grade TEXT,  -- A/B/C/D/F
    catalyst_score REAL,
    prompt_pulse_score REAL,
    freshness_score REAL,
    peer_score REAL,
    volume_score REAL,
    macro_score REAL,
    penalties TEXT,  -- JSON array of applied penalties
    created_at TEXT DEFAULT (datetime('now'))
);

-- Final recommendations output
CREATE TABLE IF NOT EXISTS recommendations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL REFERENCES tickers(ticker),
    run_date TEXT NOT NULL,
    module TEXT NOT NULL,  -- 'glance', 'shadowlist', 'shorties'
    category TEXT,  -- 'momentum', 'pair_trade', 'macro_tilt', 'lotto', 'fade', etc.
    setup TEXT,
    why_now TEXT,
    catalyst TEXT,
    not_priced_in TEXT,
    risk TEXT,
    score_total REAL,
    created_at TEXT DEFAULT (datetime('now'))
);

-- ShadowList tracking
CREATE TABLE IF NOT EXISTS shadowlist_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL REFERENCES tickers(ticker),
    why_interesting TEXT,
    why_not_ready TEXT,
    trigger_condition TEXT,
    added_date TEXT NOT NULL,
    graduated_date TEXT,
    expired_date TEXT,
    status TEXT DEFAULT 'active',  -- 'active', 'graduated', 'expired'
    created_at TEXT DEFAULT (datetime('now'))
);

-- Near misses (candidates that scored close but didn't make Glance)
CREATE TABLE IF NOT EXISTS near_misses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL REFERENCES tickers(ticker),
    run_date TEXT NOT NULL,
    total_score REAL,
    miss_reason TEXT,  -- 'chasing', 'below_threshold', 'slot_full', etc.
    created_at TEXT DEFAULT (datetime('now'))
);

-- Trade journal for tracking outcomes
CREATE TABLE IF NOT EXISTS trade_journal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL REFERENCES tickers(ticker),
    direction TEXT NOT NULL,  -- 'long', 'short'
    entry_date TEXT NOT NULL,
    entry_price REAL NOT NULL,
    exit_date TEXT,
    exit_price REAL,
    shares INTEGER,
    pnl REAL,
    pnl_pct REAL,
    module TEXT,  -- which module sourced this trade
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_price_snapshots_ticker_date ON price_snapshots(ticker, snapshot_date);
CREATE INDEX IF NOT EXISTS idx_signal_scores_ticker_date ON signal_scores(ticker, run_date);
CREATE INDEX IF NOT EXISTS idx_recommendations_date_module ON recommendations(run_date, module);
CREATE INDEX IF NOT EXISTS idx_shadowlist_status ON shadowlist_entries(status);
CREATE INDEX IF NOT EXISTS idx_trade_journal_ticker ON trade_journal(ticker);
CREATE INDEX IF NOT EXISTS idx_catalyst_events_ticker ON catalyst_events(ticker, event_date);
