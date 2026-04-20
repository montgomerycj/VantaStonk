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

-- Prompt Pulse component scores (one row per ticker per scan)
CREATE TABLE IF NOT EXISTS prompt_pulse_components (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    captured_at TEXT NOT NULL,           -- ISO8601 datetime
    scan_type TEXT NOT NULL,             -- 'premarket' | 'postclose' | 'ondemand'
    ai_sampling REAL,
    social_velocity REAL,
    volume_anomaly REAL,
    composite REAL NOT NULL,
    UNIQUE(ticker, captured_at)
);
CREATE INDEX IF NOT EXISTS idx_ppc_ticker_time
    ON prompt_pulse_components(ticker, captured_at DESC);

-- Raw AI model responses (audit + prompt tuning)
CREATE TABLE IF NOT EXISTS ai_samples_raw (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    captured_at TEXT NOT NULL,
    model TEXT NOT NULL,                 -- 'grok' | 'gpt-5' | 'claude-4.7'
    prompt_id TEXT NOT NULL,
    prompt_text TEXT NOT NULL,
    response_text TEXT NOT NULL,
    tickers_extracted TEXT,              -- JSON array
    token_cost_usd REAL
);
CREATE INDEX IF NOT EXISTS idx_ai_samples_time
    ON ai_samples_raw(captured_at DESC);

-- Social mention snapshots (for 7-day velocity baseline)
CREATE TABLE IF NOT EXISTS social_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    captured_at TEXT NOT NULL,
    source TEXT NOT NULL,                -- 'apewisdom' | 'reddit_direct'
    ticker TEXT NOT NULL,
    mentions_count INTEGER NOT NULL,
    sentiment_score REAL,
    UNIQUE(captured_at, source, ticker)
);
CREATE INDEX IF NOT EXISTS idx_social_ticker_time
    ON social_snapshots(ticker, captured_at DESC);

-- Hit-rate tracking for Feeder entries
CREATE TABLE IF NOT EXISTS recommendation_outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    ring TEXT NOT NULL,                  -- 'feeder' | 'core' | 'promotion_queue'
    first_appeared_at TEXT NOT NULL,
    entry_price REAL NOT NULL,
    entry_price_source TEXT NOT NULL,    -- 'premarket_quote' | 'intraday_last' | 'postclose_last'
    composite_score_at_entry REAL NOT NULL,
    price_1d REAL,
    price_3d REAL,
    price_7d REAL,
    dropped_at TEXT,
    UNIQUE(ticker, first_appeared_at, ring)
);
CREATE INDEX IF NOT EXISTS idx_outcomes_ticker
    ON recommendation_outcomes(ticker);
CREATE INDEX IF NOT EXISTS idx_outcomes_entry
    ON recommendation_outcomes(first_appeared_at DESC);
