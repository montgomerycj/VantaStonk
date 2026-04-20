# VantaStonk Watchlist v2 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the fake `prompt_pulse` heuristic and the mega-cap starter watchlist with a signal-fed two-ring system (AI sampling + social velocity + volume anomalies → Core/Feeder rings), per spec `docs/superpowers/specs/2026-04-20-watchlist-v2-design.md`.

**Architecture:** New `src/signals/` package generates composite `prompt_pulse` scores from three sources and stores them in new SQLite tables. New `src/watchlist/` package manages Core (git-tracked, manually curated) and Feeder (gitignored, auto-regenerated) rings with universe bounds and promotion detection. `src/core/prompt_pulse.py` gets a real-signal path guarded by a config flag so cutover is reversible.

**Tech Stack:** Python 3.14 (system install) · schwab-py · openai · anthropic · httpx · python-dotenv · sqlite3 · pytest · vcrpy (new).

**Integration note discovered during planning:** Spec called the new component-score table `signal_scores`, but that name is already used in `sql/schema.sql` for overall scoring-engine results. Plan renames the new table to **`prompt_pulse_components`** (clearer purpose anyway). All references to "§8.1 signal_scores" in the spec map to `prompt_pulse_components` in code.

---

## File Structure

### New files
- `src/signals/__init__.py`
- `src/signals/prompts.py` — 5–7 rotating AI prompts
- `src/signals/ticker_validator.py` — validates extracted tickers against Schwab
- `src/signals/ai_sampling.py` — queries OpenAI / Anthropic / xAI, extracts tickers, scores convergence
- `src/signals/social_velocity.py` — Apewisdom fetcher + velocity computation + bucketed scoring
- `src/signals/volume_anomaly.py` — RVOL from Schwab + bucketed scoring
- `src/signals/composite.py` — blends three components into composite `prompt_pulse` (0.5/0.3/0.2)
- `src/watchlist/__init__.py`
- `src/watchlist/universe.py` — market-cap / liquidity bounds + micro-cap cap enforcement
- `src/watchlist/core.py` — Core ring JSON read/write + backup on edit
- `src/watchlist/feeder.py` — Feeder regeneration + pruning + first_seen tracking
- `src/watchlist/promotion.py` — promotion candidate detection
- `src/tracking/__init__.py`
- `src/tracking/outcomes.py` — writes `recommendation_outcomes` + fills price_1d/3d/7d
- `src/config.py` — env-based settings (USE_REAL_PROMPT_PULSE flag + API keys)
- `scripts/signal_refresh.py` — standalone entry point (pre-market/post-close run)
- `scripts/fill_outcomes.py` — scheduled job filling N-day returns
- `tests/test_signal_ticker_validator.py`
- `tests/test_signal_ai_sampling.py`
- `tests/test_signal_social_velocity.py`
- `tests/test_signal_volume_anomaly.py`
- `tests/test_signal_composite.py`
- `tests/test_watchlist_universe.py`
- `tests/test_watchlist_core.py`
- `tests/test_watchlist_feeder.py`
- `tests/test_watchlist_promotion.py`
- `tests/test_tracking_outcomes.py`
- `tests/fixtures/ai_responses/` — canned AI model responses for replay
- `tests/fixtures/apewisdom/apewisdom_sample.json`
- `data/watchlist_core.json` — git-tracked seed list (populated in Phase 2)

### Modified files
- `sql/schema.sql` — add 4 new tables (prompt_pulse_components, ai_samples_raw, social_snapshots, recommendation_outcomes)
- `src/db.py` — add access functions for each new table
- `src/core/prompt_pulse.py` — add `get_prompt_pulse_score()` function with flag-guarded real-signal path
- `scripts/morning_scan.py` — read Core ∪ Feeder instead of `watchlist.json`; add Promotion Queue rendering
- `src/workflows/run_glance.py` — render Promotion Queue section
- `requirements.txt` — add openai, anthropic, vcrpy
- `.gitignore` — add `data/watchlist_feeder.json`, `data/watchlist_core.json.bak-*`
- `tests/test_prompt_pulse.py` — add tests for new flag-guarded path; keep existing tests for old path

### Unchanged
- `src/core/scoring.py` — engine weights stay (0.28/0.24/0.18/0.12/0.08/0.10)
- `src/core/filters.py` — chasing filter unchanged
- `src/integrations/schwab_client.py` — consumed, not modified
- `src/workflows/run_shorties.py`
- `tests/test_scoring.py`, `tests/test_filters.py`

---

## Phase 1 — Signal pipeline (shadow build, ~3–4 days)

Build signals, write scores to DB. Do NOT wire into live scoring yet. Pipeline runs alongside the existing fake heuristic.

### Task 1: Add new SQLite tables

**Files:**
- Modify: `sql/schema.sql` (append 4 tables + indexes)
- Test: `tests/test_db_schema.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_db_schema.py
import sqlite3
from pathlib import Path
from src.db import init_db, get_connection

def test_new_tables_exist(tmp_path):
    db = tmp_path / "t.db"
    init_db(str(db))
    conn = get_connection(str(db))
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    names = {r["name"] for r in rows}
    assert "prompt_pulse_components" in names
    assert "ai_samples_raw" in names
    assert "social_snapshots" in names
    assert "recommendation_outcomes" in names
    conn.close()
```

- [ ] **Step 2: Run the test, verify it fails**

Run: `py -3.14 -m pytest tests/test_db_schema.py -v`
Expected: FAIL — tables don't exist.

- [ ] **Step 3: Append tables to sql/schema.sql**

Append to the bottom of `sql/schema.sql`:

```sql
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
```

- [ ] **Step 4: Re-run test, verify it passes**

Run: `py -3.14 -m pytest tests/test_db_schema.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sql/schema.sql tests/test_db_schema.py
git commit -m "feat(db): add 4 tables for signal pipeline and hit-rate tracking"
```

### Task 2: DB access for `prompt_pulse_components`

**Files:**
- Modify: `src/db.py` (add functions)
- Test: `tests/test_db_signals.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_db_signals.py
from datetime import datetime, timedelta
from src.db import (
    init_db, get_connection,
    save_prompt_pulse_components, get_recent_components,
)

def _setup(tmp_path):
    db = tmp_path / "t.db"
    init_db(str(db))
    return get_connection(str(db))

def test_save_and_retrieve_components(tmp_path):
    conn = _setup(tmp_path)
    now = datetime.now().isoformat(timespec="seconds")
    save_prompt_pulse_components(
        conn, ticker="ABCD", captured_at=now, scan_type="premarket",
        ai_sampling=0.8, social_velocity=0.4, volume_anomaly=0.6, composite=0.72,
    )
    rows = get_recent_components(conn, "ABCD", limit=5)
    assert len(rows) == 1
    assert rows[0]["composite"] == 0.72
    assert rows[0]["ai_sampling"] == 0.8
```

- [ ] **Step 2: Run test, verify it fails**

Run: `py -3.14 -m pytest tests/test_db_signals.py::test_save_and_retrieve_components -v`
Expected: FAIL — functions don't exist.

- [ ] **Step 3: Add functions to `src/db.py`**

Append to `src/db.py` in a new section:

```python
# --- Prompt Pulse components (new v2 signal) ---

def save_prompt_pulse_components(
    conn: sqlite3.Connection,
    ticker: str,
    captured_at: str,
    scan_type: str,
    ai_sampling: float,
    social_velocity: float,
    volume_anomaly: float,
    composite: float,
):
    """Save a single composite prompt_pulse measurement."""
    conn.execute("""
        INSERT OR REPLACE INTO prompt_pulse_components
            (ticker, captured_at, scan_type, ai_sampling, social_velocity,
             volume_anomaly, composite)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (ticker, captured_at, scan_type, ai_sampling, social_velocity,
          volume_anomaly, composite))
    conn.commit()


def get_recent_components(conn: sqlite3.Connection, ticker: str, limit: int = 10):
    rows = conn.execute("""
        SELECT * FROM prompt_pulse_components
        WHERE ticker = ?
        ORDER BY captured_at DESC
        LIMIT ?
    """, (ticker, limit)).fetchall()
    return [dict(r) for r in rows]


def get_latest_composite(conn: sqlite3.Connection, ticker: str):
    """Get the most recent composite score for a ticker, or None."""
    row = conn.execute("""
        SELECT composite, captured_at FROM prompt_pulse_components
        WHERE ticker = ?
        ORDER BY captured_at DESC
        LIMIT 1
    """, (ticker,)).fetchone()
    return dict(row) if row else None
```

- [ ] **Step 4: Run test, verify PASS**

Run: `py -3.14 -m pytest tests/test_db_signals.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/db.py tests/test_db_signals.py
git commit -m "feat(db): add prompt_pulse_components access functions"
```

### Task 3: DB access for `ai_samples_raw` and `social_snapshots` and `recommendation_outcomes`

**Files:**
- Modify: `src/db.py`
- Test: `tests/test_db_signals.py`

Bundled into one task because each table's access functions are symmetric and trivially parallel.

- [ ] **Step 1: Extend test file with three new tests**

Append to `tests/test_db_signals.py`:

```python
from src.db import (
    save_ai_sample_raw, get_ai_samples_since,
    save_social_snapshot, get_mentions_history,
    save_recommendation_outcome, get_outcome,
    update_outcome_price, mark_outcome_dropped,
)
import json

def test_save_and_query_ai_sample(tmp_path):
    conn = _setup(tmp_path)
    now = datetime.now().isoformat(timespec="seconds")
    save_ai_sample_raw(
        conn, captured_at=now, model="grok", prompt_id="p1",
        prompt_text="What small caps?", response_text="$ABCD, $WXYZ",
        tickers_extracted=["ABCD", "WXYZ"], token_cost_usd=0.02,
    )
    rows = get_ai_samples_since(conn, since=now)
    assert len(rows) == 1
    assert json.loads(rows[0]["tickers_extracted"]) == ["ABCD", "WXYZ"]

def test_save_and_query_social_snapshot(tmp_path):
    conn = _setup(tmp_path)
    now = datetime.now().isoformat(timespec="seconds")
    save_social_snapshot(conn, captured_at=now, source="apewisdom",
                         ticker="ABCD", mentions_count=42, sentiment_score=0.6)
    hist = get_mentions_history(conn, "ABCD", source="apewisdom", days=7)
    assert len(hist) == 1
    assert hist[0]["mentions_count"] == 42

def test_outcome_lifecycle(tmp_path):
    conn = _setup(tmp_path)
    now = datetime.now().isoformat(timespec="seconds")
    save_recommendation_outcome(
        conn, ticker="ABCD", ring="feeder", first_appeared_at=now,
        entry_price=10.0, entry_price_source="premarket_quote",
        composite_score_at_entry=0.72,
    )
    update_outcome_price(conn, "ABCD", now, "feeder", field="price_1d", price=11.0)
    row = get_outcome(conn, "ABCD", now, "feeder")
    assert row["price_1d"] == 11.0
    assert row["dropped_at"] is None
    mark_outcome_dropped(conn, "ABCD", now, "feeder", dropped_at=now)
    row = get_outcome(conn, "ABCD", now, "feeder")
    assert row["dropped_at"] == now
```

- [ ] **Step 2: Run, verify failures**

Run: `py -3.14 -m pytest tests/test_db_signals.py -v`
Expected: 3 FAILs.

- [ ] **Step 3: Add functions to `src/db.py`**

```python
# --- AI samples raw ---

def save_ai_sample_raw(conn, captured_at, model, prompt_id, prompt_text,
                       response_text, tickers_extracted, token_cost_usd):
    conn.execute("""
        INSERT INTO ai_samples_raw
            (captured_at, model, prompt_id, prompt_text, response_text,
             tickers_extracted, token_cost_usd)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (captured_at, model, prompt_id, prompt_text, response_text,
          json.dumps(tickers_extracted), token_cost_usd))
    conn.commit()


def get_ai_samples_since(conn, since: str):
    rows = conn.execute(
        "SELECT * FROM ai_samples_raw WHERE captured_at >= ? ORDER BY captured_at DESC",
        (since,)
    ).fetchall()
    return [dict(r) for r in rows]


# --- Social snapshots ---

def save_social_snapshot(conn, captured_at, source, ticker, mentions_count, sentiment_score=None):
    conn.execute("""
        INSERT OR REPLACE INTO social_snapshots
            (captured_at, source, ticker, mentions_count, sentiment_score)
        VALUES (?, ?, ?, ?, ?)
    """, (captured_at, source, ticker, mentions_count, sentiment_score))
    conn.commit()


def get_mentions_history(conn, ticker: str, source: str = "apewisdom", days: int = 7):
    rows = conn.execute("""
        SELECT * FROM social_snapshots
        WHERE ticker = ? AND source = ?
          AND captured_at >= datetime('now', '-' || ? || ' days')
        ORDER BY captured_at DESC
    """, (ticker, source, days)).fetchall()
    return [dict(r) for r in rows]


# --- Recommendation outcomes ---

def save_recommendation_outcome(conn, ticker, ring, first_appeared_at,
                                entry_price, entry_price_source,
                                composite_score_at_entry):
    conn.execute("""
        INSERT OR IGNORE INTO recommendation_outcomes
            (ticker, ring, first_appeared_at, entry_price, entry_price_source,
             composite_score_at_entry)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (ticker, ring, first_appeared_at, entry_price, entry_price_source,
          composite_score_at_entry))
    conn.commit()


def get_outcome(conn, ticker, first_appeared_at, ring):
    row = conn.execute("""
        SELECT * FROM recommendation_outcomes
        WHERE ticker = ? AND first_appeared_at = ? AND ring = ?
    """, (ticker, first_appeared_at, ring)).fetchone()
    return dict(row) if row else None


def update_outcome_price(conn, ticker, first_appeared_at, ring, field, price):
    if field not in ("price_1d", "price_3d", "price_7d"):
        raise ValueError(f"invalid field: {field}")
    conn.execute(
        f"UPDATE recommendation_outcomes SET {field} = ? "
        "WHERE ticker = ? AND first_appeared_at = ? AND ring = ?",
        (price, ticker, first_appeared_at, ring)
    )
    conn.commit()


def mark_outcome_dropped(conn, ticker, first_appeared_at, ring, dropped_at):
    conn.execute("""
        UPDATE recommendation_outcomes SET dropped_at = ?
        WHERE ticker = ? AND first_appeared_at = ? AND ring = ?
    """, (dropped_at, ticker, first_appeared_at, ring))
    conn.commit()
```

- [ ] **Step 4: Run, verify PASS**

Run: `py -3.14 -m pytest tests/test_db_signals.py -v`
Expected: 4/4 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/db.py tests/test_db_signals.py
git commit -m "feat(db): access functions for ai_samples, social_snapshots, outcomes"
```

### Task 4: `src/config.py` — env-based settings

**Files:**
- Create: `src/config.py`
- Modify: `.env.example`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_config.py
import os
from src.config import Settings

def test_defaults(monkeypatch):
    monkeypatch.delenv("USE_REAL_PROMPT_PULSE", raising=False)
    s = Settings.from_env()
    assert s.use_real_prompt_pulse is False
    assert s.openai_api_key == ""
    assert s.anthropic_api_key == ""
    assert s.xai_api_key == ""

def test_flag_true(monkeypatch):
    monkeypatch.setenv("USE_REAL_PROMPT_PULSE", "true")
    s = Settings.from_env()
    assert s.use_real_prompt_pulse is True
```

- [ ] **Step 2: Run, verify FAIL**

- [ ] **Step 3: Implement `src/config.py`**

```python
"""Environment-backed settings for VantaStonk v2 subsystems."""

import os
from dataclasses import dataclass


def _bool(val: str) -> bool:
    return str(val).lower() in ("1", "true", "yes", "on")


@dataclass
class Settings:
    use_real_prompt_pulse: bool
    openai_api_key: str
    anthropic_api_key: str
    xai_api_key: str
    schwab_app_key: str
    schwab_app_secret: str
    schwab_token_path: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            use_real_prompt_pulse=_bool(os.getenv("USE_REAL_PROMPT_PULSE", "false")),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            xai_api_key=os.getenv("XAI_API_KEY", ""),
            schwab_app_key=os.getenv("SCHWAB_APP_KEY", ""),
            schwab_app_secret=os.getenv("SCHWAB_APP_SECRET", ""),
            schwab_token_path=os.getenv("SCHWAB_TOKEN_PATH", "data/schwab_token.json"),
        )
```

- [ ] **Step 4: Update `.env.example`**

Append to `.env.example`:

```
# v2 signal pipeline
USE_REAL_PROMPT_PULSE=false
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
XAI_API_KEY=
```

- [ ] **Step 5: Run tests, verify PASS, commit**

```bash
py -3.14 -m pytest tests/test_config.py -v
git add src/config.py tests/test_config.py .env.example
git commit -m "feat(config): env-based settings with USE_REAL_PROMPT_PULSE flag"
```

### Task 5: `src/signals/ticker_validator.py`

Prevents AI hallucinated tickers from polluting the pipeline. Validates via Schwab quote lookup.

**Files:**
- Create: `src/signals/__init__.py`, `src/signals/ticker_validator.py`
- Test: `tests/test_signal_ticker_validator.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_signal_ticker_validator.py
from src.signals.ticker_validator import validate_tickers

class FakeClient:
    def __init__(self, valid_symbols):
        self._valid = set(valid_symbols)
    def has_quote(self, symbol):
        return symbol in self._valid

def test_filters_invalid():
    client = FakeClient({"AAPL", "XYZ"})
    candidates = ["AAPL", "XYZ", "FAKE123", "BLZR"]
    valid, rejected = validate_tickers(candidates, client)
    assert valid == ["AAPL", "XYZ"]
    assert set(rejected) == {"FAKE123", "BLZR"}

def test_dedup():
    client = FakeClient({"AAPL"})
    valid, _ = validate_tickers(["AAPL", "AAPL", "aapl"], client)
    assert valid == ["AAPL"]  # dedup + normalize case
```

- [ ] **Step 2: Run, verify FAIL**

- [ ] **Step 3: Implement**

`src/signals/__init__.py`: empty.

`src/signals/ticker_validator.py`:

```python
"""Validates candidate tickers (e.g. extracted from AI responses) against Schwab."""

from typing import Protocol


class QuoteLookup(Protocol):
    def has_quote(self, symbol: str) -> bool: ...


def validate_tickers(candidates: list[str], client: QuoteLookup) -> tuple[list[str], list[str]]:
    """Return (valid, rejected) after deduping, normalizing, and Schwab-validating."""
    seen: set[str] = set()
    valid: list[str] = []
    rejected: list[str] = []
    for raw in candidates:
        sym = raw.strip().upper()
        if not sym or sym in seen:
            continue
        seen.add(sym)
        if client.has_quote(sym):
            valid.append(sym)
        else:
            rejected.append(sym)
    return valid, rejected
```

- [ ] **Step 4: Run PASS, commit**

```bash
py -3.14 -m pytest tests/test_signal_ticker_validator.py -v
git add src/signals/__init__.py src/signals/ticker_validator.py tests/test_signal_ticker_validator.py
git commit -m "feat(signals): ticker validator rejects AI hallucinations"
```

### Task 6: `src/signals/prompts.py` — rotating prompt set

**Files:**
- Create: `src/signals/prompts.py`
- Test: `tests/test_signal_prompts.py`

Claude authors these 7 prompts; user reviews before Phase 3 cutover. Each prompt has an ID for audit-trail correlation.

- [ ] **Step 1: Write failing test**

```python
# tests/test_signal_prompts.py
from src.signals.prompts import ROTATING_PROMPTS, pick_prompts_for_run

def test_prompt_set_size():
    assert 5 <= len(ROTATING_PROMPTS) <= 7

def test_each_prompt_has_id_and_text():
    for p in ROTATING_PROMPTS:
        assert p.prompt_id
        assert len(p.text) > 20
        assert p.text.strip() == p.text

def test_pick_prompts_for_run_is_stable():
    """Given the same date, same prompts. Different dates, different subsets."""
    a = pick_prompts_for_run("2026-04-20")
    b = pick_prompts_for_run("2026-04-20")
    assert a == b
    c = pick_prompts_for_run("2026-04-21")
    # Subsets of the same pool but different selections (may still overlap).
    assert {p.prompt_id for p in a} | {p.prompt_id for p in c} <= {p.prompt_id for p in ROTATING_PROMPTS}

def test_pick_selects_5_per_run():
    picks = pick_prompts_for_run("2026-04-20")
    assert len(picks) == 5
```

- [ ] **Step 2: Run, verify FAIL**

- [ ] **Step 3: Implement**

```python
"""Rotating prompts for AI model sampling. Stable selection per run date."""

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class Prompt:
    prompt_id: str
    text: str


ROTATING_PROMPTS: list[Prompt] = [
    Prompt("undiscovered_weekly",
           "What under-the-radar small/mid-cap stocks (market cap $50M–$10B, US-listed) "
           "should retail traders watch this week? Give me 5–10 specific tickers with a "
           "one-line thesis each. Prioritize names that aren't yet widely discussed."),
    Prompt("sector_rotation",
           "Which sectors or sub-themes appear to be starting a rotation right now, and "
           "what specific small/mid-cap stocks would benefit? Give tickers."),
    Prompt("pre_catalyst_2wk",
           "Name 5 stocks with known catalysts in the next 2 weeks (earnings, FDA, product "
           "launch, partnership) that aren't already priced in. Be specific with tickers."),
    Prompt("squeezable_shorts",
           "Which small-cap stocks have high short interest (>15% of float) AND a recent "
           "positive catalyst that could trigger a squeeze? Tickers only."),
    Prompt("ai_adjacent_stealth",
           "What stealth AI-adjacent plays (companies benefiting from AI infrastructure, "
           "data, or applications) are not yet recognized as AI stocks by the market? Tickers."),
    Prompt("cannabis_biotech_catalyst",
           "In cannabis/MSO or small-cap biotech, which specific tickers have near-term "
           "regulatory or clinical catalysts that could re-rate the name 20%+?"),
    Prompt("overlooked_momentum",
           "What small-cap stocks are showing 3-month relative strength vs. their sector "
           "without having run more than 10% in the last week? List tickers."),
]


def pick_prompts_for_run(run_date: str, k: int = 5) -> list[Prompt]:
    """Deterministically pick k prompts for a given run date."""
    h = int(hashlib.sha256(run_date.encode()).hexdigest(), 16)
    n = len(ROTATING_PROMPTS)
    # Rotate start index by date hash, take k consecutive.
    start = h % n
    return [ROTATING_PROMPTS[(start + i) % n] for i in range(k)]
```

- [ ] **Step 4: Run PASS, commit**

```bash
py -3.14 -m pytest tests/test_signal_prompts.py -v
git add src/signals/prompts.py tests/test_signal_prompts.py
git commit -m "feat(signals): 7 rotating prompts with stable date-based selection"
```

### Task 7: Add `openai`, `anthropic`, `vcrpy` to requirements

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Append**

```
openai>=1.60.0
anthropic>=0.46.0
vcrpy>=7.0.0
```

- [ ] **Step 2: Install**

Run: `py -3.14 -m pip install -r requirements.txt`
Expected: installs new packages, no errors on existing ones.

- [ ] **Step 3: Verify imports**

Run: `py -3.14 -c "import openai; import anthropic; import vcr; print('ok')"`
Expected: `ok`.

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "deps: openai, anthropic, vcrpy for v2 signal pipeline"
```

### Task 8: `src/signals/ai_sampling.py` — model clients

Three thin client classes that wrap OpenAI, Anthropic, and xAI (OpenAI-compatible) and return a uniform `AiSampleResult`.

**Files:**
- Create: `src/signals/ai_sampling.py`
- Test: `tests/test_signal_ai_sampling.py`

- [ ] **Step 1: Write failing test — client abstraction**

```python
# tests/test_signal_ai_sampling.py
from src.signals.ai_sampling import AiSampleResult, MODEL_WEIGHTS, build_client

def test_model_weights_sum_to_one():
    assert abs(sum(MODEL_WEIGHTS.values()) - 1.0) < 1e-9

def test_grok_weight_is_highest():
    assert MODEL_WEIGHTS["grok"] > MODEL_WEIGHTS["gpt-5"]
    assert MODEL_WEIGHTS["grok"] > MODEL_WEIGHTS["claude-4.7"]

def test_build_client_returns_callable():
    client = build_client("grok", api_key="fake")
    assert callable(client.query)
```

- [ ] **Step 2: Run, verify FAIL**

- [ ] **Step 3: Implement client section**

```python
"""AI model sampling — query three frontier models, score convergence, feed prompt_pulse."""

import re
import time
from dataclasses import dataclass, field
from typing import Protocol

# Model-weighted convergence (sum = 1.0)
MODEL_WEIGHTS = {
    "grok": 0.45,      # real-time X access
    "gpt-5": 0.30,
    "claude-4.7": 0.25,
}


@dataclass
class AiSampleResult:
    model: str
    prompt_id: str
    prompt_text: str
    response_text: str
    tickers_extracted: list[str] = field(default_factory=list)
    token_cost_usd: float = 0.0


class _Client(Protocol):
    def query(self, prompt: str) -> AiSampleResult: ...


class _OpenAIClient:
    def __init__(self, api_key: str, model: str = "gpt-5", base_url: str | None = None):
        from openai import OpenAI
        self._openai = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
        self._model_id = model

    def query(self, prompt: str, prompt_id: str = "") -> AiSampleResult:
        resp = self._openai.chat.completions.create(
            model=self._model_id,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        text = resp.choices[0].message.content or ""
        # Rough cost estimate: GPT-5 ~$0.01/1k input + $0.03/1k output
        usage = getattr(resp, "usage", None)
        cost = 0.0
        if usage:
            cost = (usage.prompt_tokens * 0.00001) + (usage.completion_tokens * 0.00003)
        return AiSampleResult(
            model=self._model_id,
            prompt_id=prompt_id,
            prompt_text=prompt,
            response_text=text,
            token_cost_usd=round(cost, 5),
        )


class _AnthropicClient:
    def __init__(self, api_key: str, model: str = "claude-opus-4-7"):
        from anthropic import Anthropic
        self._anthropic = Anthropic(api_key=api_key)
        self._model_id = model

    def query(self, prompt: str, prompt_id: str = "") -> AiSampleResult:
        resp = self._anthropic.messages.create(
            model=self._model_id,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in resp.content if hasattr(b, "text"))
        cost = 0.0
        if resp.usage:
            cost = (resp.usage.input_tokens * 0.000015) + (resp.usage.output_tokens * 0.000075)
        return AiSampleResult(
            model=self._model_id,
            prompt_id=prompt_id,
            prompt_text=prompt,
            response_text=text,
            token_cost_usd=round(cost, 5),
        )


def build_client(name: str, api_key: str) -> _Client:
    """Build a client by canonical model name."""
    if name == "grok":
        # xAI uses OpenAI-compatible API at api.x.ai/v1
        return _OpenAIClient(api_key=api_key, model="grok-4", base_url="https://api.x.ai/v1")
    if name == "gpt-5":
        return _OpenAIClient(api_key=api_key, model="gpt-5")
    if name == "claude-4.7":
        return _AnthropicClient(api_key=api_key, model="claude-opus-4-7")
    raise ValueError(f"unknown model: {name}")
```

- [ ] **Step 4: Run PASS, commit**

```bash
py -3.14 -m pytest tests/test_signal_ai_sampling.py -v
git add src/signals/ai_sampling.py tests/test_signal_ai_sampling.py
git commit -m "feat(signals): AI sampling model clients (OpenAI, Anthropic, xAI)"
```

### Task 9: Ticker extraction from AI responses

**Files:**
- Modify: `src/signals/ai_sampling.py` (add function)
- Modify: `tests/test_signal_ai_sampling.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_signal_ai_sampling.py`:

```python
from src.signals.ai_sampling import extract_tickers

def test_cashtag_extraction():
    text = "My picks: $AAPL, $NVDA and $RKLB for space."
    assert set(extract_tickers(text)) == {"AAPL", "NVDA", "RKLB"}

def test_bareword_ticker_extraction():
    text = "1. AAPL - iPhone maker\n2. NVDA - GPU leader\n3. TSM (Taiwan Semi)"
    got = set(extract_tickers(text))
    assert "AAPL" in got
    assert "NVDA" in got
    assert "TSM" in got

def test_common_false_positives_excluded():
    text = "Here are MY TOP 5 AI PICKS NOW ASAP: $AAPL."
    got = set(extract_tickers(text))
    assert got == {"AAPL"}  # common English words filtered out

def test_dedupe():
    text = "$AAPL is great. AAPL trades at..."
    assert extract_tickers(text) == ["AAPL"]
```

- [ ] **Step 2: Run, FAIL**

- [ ] **Step 3: Implement**

Add to `src/signals/ai_sampling.py`:

```python
# Ticker extraction
_CASHTAG_RE = re.compile(r"\$([A-Z]{1,5})\b")
_BAREWORD_RE = re.compile(r"\b([A-Z]{2,5})\b")

# Words that look like tickers but aren't
_BLOCKLIST = {
    "I", "A", "AI", "US", "USA", "ETF", "IPO", "CEO", "CFO", "COO", "CTO",
    "SEC", "FDA", "FTC", "DOJ", "IRS", "EU", "UK", "FX", "PE", "PS",
    "NOW", "TOP", "BIG", "NEW", "ALL", "THE", "MY", "YOUR", "OUR",
    "Q1", "Q2", "Q3", "Q4", "H1", "H2", "YTD", "EOD", "EOM", "EOY",
    "ASAP", "FYI", "OMG", "WTF", "LOL", "ATH", "ATL", "FOMO", "FUD",
    "GDP", "CPI", "PCE", "PPI", "ISM", "PMI", "FOMC", "NFP", "ECB",
    "PICKS", "TRADE", "STOCK", "BUY", "SELL", "HOLD", "LONG", "SHORT",
}


def extract_tickers(text: str) -> list[str]:
    """Extract likely ticker symbols. Dedupes; preserves first-seen order."""
    seen: set[str] = set()
    out: list[str] = []
    for m in _CASHTAG_RE.finditer(text):
        sym = m.group(1).upper()
        if sym not in seen and sym not in _BLOCKLIST:
            seen.add(sym); out.append(sym)
    for m in _BAREWORD_RE.finditer(text):
        sym = m.group(1).upper()
        if sym not in seen and sym not in _BLOCKLIST:
            seen.add(sym); out.append(sym)
    return out
```

- [ ] **Step 4: Run PASS, commit**

```bash
py -3.14 -m pytest tests/test_signal_ai_sampling.py -v
git add src/signals/ai_sampling.py tests/test_signal_ai_sampling.py
git commit -m "feat(signals): extract tickers from AI responses (cashtag + bareword + blocklist)"
```

### Task 10: Rank-weighted position and freshness

Per §5.1 of spec: top-3 rank gets 1.5x multiplier; new-today mentions get +0.2 bonus; clamp last.

**Files:**
- Modify: `src/signals/ai_sampling.py`
- Modify: `tests/test_signal_ai_sampling.py`

- [ ] **Step 1: Write failing tests**

Append to test file:

```python
from src.signals.ai_sampling import (
    compute_rank_weight,
    extract_ranked_tickers,
    compute_ai_sampling_score,
    MentionRecord,
)

def test_rank_weight():
    assert compute_rank_weight(0) == 1.5  # position 0 is 1st
    assert compute_rank_weight(2) == 1.5  # position 2 is 3rd
    assert compute_rank_weight(3) == 1.0  # position 3 is 4th
    assert compute_rank_weight(99) == 1.0

def test_extract_ranked():
    text = "Here are 5 picks:\n1. AAPL — iPhone\n2. NVDA — GPUs\n3. AMD"
    ranked = extract_ranked_tickers(text)
    assert ranked[0] == ("AAPL", 0)
    assert ranked[1] == ("NVDA", 1)
    assert ranked[2] == ("AMD", 2)

def test_convergence_scoring_all_three_models():
    mentions = [
        MentionRecord(ticker="ABCD", model="grok", rank=0, is_fresh=False),
        MentionRecord(ticker="ABCD", model="gpt-5", rank=1, is_fresh=False),
        MentionRecord(ticker="ABCD", model="claude-4.7", rank=5, is_fresh=False),
    ]
    score = compute_ai_sampling_score("ABCD", mentions)
    # convergence = 0.45*1.5 + 0.30*1.5 + 0.25*1.0 = 0.675 + 0.45 + 0.25 = 1.375 → clamped to 1.0
    assert score == 1.0

def test_convergence_grok_only_not_fresh():
    mentions = [MentionRecord(ticker="ABCD", model="grok", rank=5, is_fresh=False)]
    score = compute_ai_sampling_score("ABCD", mentions)
    # grok weight 0.45 * rank_weight 1.0 = 0.45
    assert abs(score - 0.45) < 1e-9

def test_freshness_bonus_applied_after_rank():
    mentions = [MentionRecord(ticker="ABCD", model="grok", rank=0, is_fresh=True)]
    score = compute_ai_sampling_score("ABCD", mentions)
    # (0.45 * 1.5) + 0.2 = 0.675 + 0.2 = 0.875
    assert abs(score - 0.875) < 1e-9

def test_clamp_to_one():
    mentions = [
        MentionRecord(ticker="ABCD", model="grok", rank=0, is_fresh=True),
        MentionRecord(ticker="ABCD", model="gpt-5", rank=0, is_fresh=True),
        MentionRecord(ticker="ABCD", model="claude-4.7", rank=0, is_fresh=True),
    ]
    score = compute_ai_sampling_score("ABCD", mentions)
    assert score == 1.0
```

- [ ] **Step 2: Run, FAIL**

- [ ] **Step 3: Implement**

Add to `src/signals/ai_sampling.py`:

```python
@dataclass
class MentionRecord:
    ticker: str
    model: str
    rank: int          # 0-indexed position within response list
    is_fresh: bool     # True if ticker is newly mentioned today


def compute_rank_weight(rank: int) -> float:
    """1.5x for top-3 (rank 0-2), else 1.0x."""
    return 1.5 if rank < 3 else 1.0


_RANKED_LINE_RE = re.compile(r"^\s*\d+[\.\)]\s+(.*)", re.MULTILINE)


def extract_ranked_tickers(text: str) -> list[tuple[str, int]]:
    """Extract tickers with their numeric list position. Returns [(ticker, rank_0indexed), ...]."""
    seen: set[str] = set()
    out: list[tuple[str, int]] = []
    lines = _RANKED_LINE_RE.findall(text)
    for idx, line in enumerate(lines):
        ts = extract_tickers(line)
        if ts and ts[0] not in seen:
            seen.add(ts[0])
            out.append((ts[0], idx))
    # Fallback: if no numbered list, flat extraction with sequential ranks
    if not out:
        for idx, sym in enumerate(extract_tickers(text)):
            out.append((sym, idx))
    return out


def compute_ai_sampling_score(ticker: str, mentions: list[MentionRecord]) -> float:
    """
    score = clamp((convergence * rank_weight) + freshness_bonus, 0.0, 1.0)

    convergence = sum of model weights for models mentioning the ticker.
    rank_weight uses the ticker's BEST (lowest) rank across mentions.
    freshness_bonus = 0.2 if any mention is fresh, else 0.
    """
    ticker_mentions = [m for m in mentions if m.ticker == ticker]
    if not ticker_mentions:
        return 0.0
    convergence = 0.0
    best_rank = 99
    fresh = False
    for m in ticker_mentions:
        convergence += MODEL_WEIGHTS.get(m.model, 0.0)
        best_rank = min(best_rank, m.rank)
        fresh = fresh or m.is_fresh
    # Dedupe: multiple mentions from same model shouldn't double-count weight
    models_seen = {m.model for m in ticker_mentions}
    convergence = sum(MODEL_WEIGHTS.get(m, 0.0) for m in models_seen)
    rank_weight = compute_rank_weight(best_rank)
    freshness_bonus = 0.2 if fresh else 0.0
    score = (convergence * rank_weight) + freshness_bonus
    return max(0.0, min(1.0, score))
```

- [ ] **Step 4: Run PASS, commit**

```bash
py -3.14 -m pytest tests/test_signal_ai_sampling.py -v
git add src/signals/ai_sampling.py tests/test_signal_ai_sampling.py
git commit -m "feat(signals): rank-weighted convergence scoring with freshness bonus"
```

### Task 11: `src/signals/social_velocity.py` — Apewisdom fetcher + scoring

**Files:**
- Create: `src/signals/social_velocity.py`
- Create: `tests/fixtures/apewisdom/apewisdom_sample.json`
- Test: `tests/test_signal_social_velocity.py`

Apewisdom public endpoint: `https://apewisdom.io/api/v1.0/filter/all-stocks/page/1`. Returns JSON with top mentioned tickers.

- [ ] **Step 1: Create fixture**

`tests/fixtures/apewisdom/apewisdom_sample.json`:

```json
{
  "results": [
    {"ticker": "AAPL", "mentions": 120, "sentiment": 0.8, "upvotes": 450},
    {"ticker": "NVDA", "mentions": 95, "sentiment": 0.7, "upvotes": 380},
    {"ticker": "ABCD", "mentions": 42, "sentiment": 0.5, "upvotes": 30},
    {"ticker": "TINY", "mentions": 3, "sentiment": 0.2, "upvotes": 5}
  ]
}
```

- [ ] **Step 2: Write failing tests**

```python
# tests/test_signal_social_velocity.py
import json
from pathlib import Path
from src.signals.social_velocity import (
    parse_apewisdom_response,
    compute_velocity,
    score_velocity,
)

FIX = Path(__file__).parent / "fixtures/apewisdom/apewisdom_sample.json"

def test_parse():
    rows = parse_apewisdom_response(json.loads(FIX.read_text()))
    assert len(rows) == 4
    assert rows[0].ticker == "AAPL"
    assert rows[0].mentions == 120

def test_velocity_math():
    # today=60, avg=20 → velocity=3.0
    assert abs(compute_velocity(60, 20) - 3.0) < 1e-9
    # baseline zero safeguard
    assert compute_velocity(10, 0) == 0.0

def test_velocity_scoring_bands():
    assert score_velocity(1.0) == 0.0    # below floor
    assert score_velocity(1.75) == 0.3   # 1.5-2x
    assert score_velocity(3.0) == 0.6    # 2-5x
    assert score_velocity(7.0) == 0.9    # 5-10x
    assert score_velocity(15.0) == 1.0   # 10x+

def test_noise_floor():
    from src.signals.social_velocity import passes_noise_floor
    assert passes_noise_floor(mentions_today=4) is False
    assert passes_noise_floor(mentions_today=5) is True
```

- [ ] **Step 3: Run, FAIL**

- [ ] **Step 4: Implement**

```python
"""Social mention velocity (Apewisdom aggregates r/WSB, r/stocks, r/pennystocks, r/smallstreetbets)."""

from dataclasses import dataclass
from typing import Any

import httpx

APEWISDOM_URL = "https://apewisdom.io/api/v1.0/filter/all-stocks/page/1"
NOISE_FLOOR = 5  # ignore if absolute count < 5


@dataclass
class ApewisdomRow:
    ticker: str
    mentions: int
    sentiment: float | None = None
    upvotes: int | None = None


def parse_apewisdom_response(payload: dict[str, Any]) -> list[ApewisdomRow]:
    return [
        ApewisdomRow(
            ticker=r["ticker"].upper(),
            mentions=int(r.get("mentions", 0)),
            sentiment=r.get("sentiment"),
            upvotes=r.get("upvotes"),
        )
        for r in payload.get("results", [])
    ]


def fetch_apewisdom(client: httpx.Client | None = None, timeout: float = 10.0) -> list[ApewisdomRow]:
    """Fetch current Apewisdom snapshot. Raises on network error."""
    c = client or httpx.Client(timeout=timeout)
    r = c.get(APEWISDOM_URL)
    r.raise_for_status()
    return parse_apewisdom_response(r.json())


def compute_velocity(mentions_today: int, mentions_7d_avg: float) -> float:
    if mentions_7d_avg <= 0:
        return 0.0
    return mentions_today / mentions_7d_avg


def passes_noise_floor(mentions_today: int) -> bool:
    return mentions_today >= NOISE_FLOOR


def score_velocity(velocity: float) -> float:
    if velocity < 1.5:
        return 0.0
    if velocity < 2.0:
        return 0.3
    if velocity < 5.0:
        return 0.6
    if velocity < 10.0:
        return 0.9
    return 1.0
```

- [ ] **Step 5: Run PASS, commit**

```bash
py -3.14 -m pytest tests/test_signal_social_velocity.py -v
git add src/signals/social_velocity.py tests/test_signal_social_velocity.py tests/fixtures/apewisdom/
git commit -m "feat(signals): Apewisdom fetcher + velocity scoring"
```

### Task 12: `src/signals/volume_anomaly.py` — RVOL scoring

**Files:**
- Create: `src/signals/volume_anomaly.py`
- Test: `tests/test_signal_volume_anomaly.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_signal_volume_anomaly.py
from src.signals.volume_anomaly import (
    compute_rvol, score_volume_anomaly, passes_price_filter,
)

def test_rvol():
    assert abs(compute_rvol(today=3_000_000, avg_30d=1_000_000) - 3.0) < 1e-9
    assert compute_rvol(today=100, avg_30d=0) == 0.0

def test_score_bands():
    assert score_volume_anomaly(1.0) == 0.0
    assert score_volume_anomaly(1.75) == 0.3
    assert score_volume_anomaly(2.5) == 0.6
    assert score_volume_anomaly(4.0) == 0.85
    assert score_volume_anomaly(10.0) == 1.0

def test_price_filter():
    # Only counts if 5-day move <5% (spec §5.3)
    assert passes_price_filter(move_pct=4.5) is True
    assert passes_price_filter(move_pct=-4.5) is True
    assert passes_price_filter(move_pct=5.5) is False
    assert passes_price_filter(move_pct=-5.5) is False
```

- [ ] **Step 2: Run, FAIL**

- [ ] **Step 3: Implement**

```python
"""Relative volume (RVOL) anomaly signal. Catches accumulation, rejects late-to-party."""

PRICE_FILTER_THRESHOLD = 5.0  # 5-day move %, aligned with chasing filter


def compute_rvol(today: float, avg_30d: float) -> float:
    if avg_30d <= 0:
        return 0.0
    return today / avg_30d


def passes_price_filter(move_pct: float) -> bool:
    """Only score RVOL spikes if 5-day price move is below the chasing threshold."""
    return abs(move_pct) < PRICE_FILTER_THRESHOLD


def score_volume_anomaly(rvol: float) -> float:
    if rvol < 1.5:
        return 0.0
    if rvol < 2.0:
        return 0.3
    if rvol < 3.0:
        return 0.6
    if rvol < 5.0:
        return 0.85
    return 1.0
```

- [ ] **Step 4: Run PASS, commit**

```bash
py -3.14 -m pytest tests/test_signal_volume_anomaly.py -v
git add src/signals/volume_anomaly.py tests/test_signal_volume_anomaly.py
git commit -m "feat(signals): RVOL-based volume anomaly scoring with price filter"
```

### Task 13: `src/signals/composite.py`

**Files:**
- Create: `src/signals/composite.py`
- Test: `tests/test_signal_composite.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_signal_composite.py
from src.signals.composite import compose, COMPONENT_WEIGHTS

def test_weights_sum_to_one():
    assert abs(sum(COMPONENT_WEIGHTS.values()) - 1.0) < 1e-9

def test_composite_math():
    # 0.5*0.8 + 0.3*0.4 + 0.2*0.6 = 0.40 + 0.12 + 0.12 = 0.64
    assert abs(compose(0.8, 0.4, 0.6) - 0.64) < 1e-9

def test_clamp_low():
    assert compose(0.0, 0.0, 0.0) == 0.0

def test_clamp_high():
    assert compose(1.0, 1.0, 1.0) == 1.0

def test_neutral_default_on_missing():
    """If a component is None (signal source failed), use 0.5 neutral (spec §7.4)."""
    from src.signals.composite import compose_with_fallback
    # Social failed -> 0.5 fallback. 0.5*0.8 + 0.3*0.5 + 0.2*0.6 = 0.4 + 0.15 + 0.12 = 0.67
    assert abs(compose_with_fallback(0.8, None, 0.6) - 0.67) < 1e-9
```

- [ ] **Step 2: Run, FAIL**

- [ ] **Step 3: Implement**

```python
"""Composite prompt_pulse score combining three signal components."""

COMPONENT_WEIGHTS = {
    "ai_sampling": 0.5,
    "social_velocity": 0.3,
    "volume_anomaly": 0.2,
}
NEUTRAL = 0.5


def compose(ai_sampling: float, social_velocity: float, volume_anomaly: float) -> float:
    s = (
        COMPONENT_WEIGHTS["ai_sampling"] * ai_sampling
        + COMPONENT_WEIGHTS["social_velocity"] * social_velocity
        + COMPONENT_WEIGHTS["volume_anomaly"] * volume_anomaly
    )
    return max(0.0, min(1.0, s))


def compose_with_fallback(ai_sampling, social_velocity, volume_anomaly) -> float:
    """Use 0.5 neutral for any None component (degraded signal source)."""
    return compose(
        NEUTRAL if ai_sampling is None else ai_sampling,
        NEUTRAL if social_velocity is None else social_velocity,
        NEUTRAL if volume_anomaly is None else volume_anomaly,
    )
```

- [ ] **Step 4: Run PASS, commit**

```bash
py -3.14 -m pytest tests/test_signal_composite.py -v
git add src/signals/composite.py tests/test_signal_composite.py
git commit -m "feat(signals): composite prompt_pulse with 0.5/0.3/0.2 sub-weights"
```

---

## Phase 2 — Universe and two-ring structure (~2 days)

### Task 14: `src/watchlist/universe.py`

**Files:**
- Create: `src/watchlist/__init__.py`, `src/watchlist/universe.py`
- Test: `tests/test_watchlist_universe.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_watchlist_universe.py
from src.watchlist.universe import (
    TickerFundamentals, passes_universe_bounds,
    enforce_microcap_cap, MICROCAP_CAP,
)

def _fund(mc, dv):
    return TickerFundamentals(ticker="X", market_cap_millions=mc, avg_daily_dollar_volume=dv)

def test_in_range_small_cap_passes():
    assert passes_universe_bounds(_fund(500, 3_000_000)) is True

def test_below_market_cap_rejected():
    assert passes_universe_bounds(_fund(30, 1_000_000)) is False

def test_above_market_cap_rejected():
    assert passes_universe_bounds(_fund(12_000, 5_000_000)) is False

def test_microcap_liquidity_floor():
    # microcap = $50M-$300M needs $500K/day
    assert passes_universe_bounds(_fund(200, 400_000)) is False  # below floor
    assert passes_universe_bounds(_fund(200, 600_000)) is True   # above floor

def test_small_mid_liquidity_floor():
    # small/mid = $300M+ needs $2M/day
    assert passes_universe_bounds(_fund(500, 1_500_000)) is False
    assert passes_universe_bounds(_fund(500, 3_000_000)) is True

def test_microcap_cap_enforcement():
    core_micros = ["A", "B", "C"]  # 3 in Core already
    feeder_candidates = [
        ("D", True), ("E", True), ("F", False), ("G", True),  # 3 more microcaps + 1 non
    ]
    kept = enforce_microcap_cap(core_micros, feeder_candidates, cap=MICROCAP_CAP)
    # Core already has 3 micros, feeder allowed 12 more (15-3)
    all_micros = core_micros + [t for t, is_mc in kept if is_mc]
    assert sum(1 for _, is_mc in kept if is_mc) + len(core_micros) <= MICROCAP_CAP

def test_microcap_cap_core_exceeded():
    """When Core alone exceeds cap, Feeder contributes zero microcaps."""
    core_micros = [f"M{i}" for i in range(16)]  # 16 > 15
    feeder_candidates = [("X", True), ("Y", False)]
    kept = enforce_microcap_cap(core_micros, feeder_candidates, cap=MICROCAP_CAP)
    assert [t for t, is_mc in kept if is_mc] == []
    assert any(t == "Y" for t, _ in kept)  # non-micro still kept
```

- [ ] **Step 2: Run, FAIL**

- [ ] **Step 3: Implement**

`src/watchlist/__init__.py`: empty.

`src/watchlist/universe.py`:

```python
"""Universe bounds for the watchlist v2."""

from dataclasses import dataclass

MARKET_CAP_MIN = 50.0         # $50M
MARKET_CAP_MAX = 10_000.0     # $10B
MICROCAP_MAX = 300.0          # $300M upper bound of microcap tier
MICROCAP_LIQUIDITY_FLOOR = 500_000.0   # $500K/day
SMALLMID_LIQUIDITY_FLOOR = 2_000_000.0 # $2M/day
MICROCAP_CAP = 15


@dataclass
class TickerFundamentals:
    ticker: str
    market_cap_millions: float
    avg_daily_dollar_volume: float


def is_microcap(mc: float) -> bool:
    return MARKET_CAP_MIN <= mc < MICROCAP_MAX


def passes_universe_bounds(f: TickerFundamentals) -> bool:
    if f.market_cap_millions < MARKET_CAP_MIN or f.market_cap_millions > MARKET_CAP_MAX:
        return False
    floor = MICROCAP_LIQUIDITY_FLOOR if is_microcap(f.market_cap_millions) else SMALLMID_LIQUIDITY_FLOOR
    return f.avg_daily_dollar_volume >= floor


def enforce_microcap_cap(
    core_microcaps: list[str],
    feeder_candidates: list[tuple[str, bool]],
    cap: int = MICROCAP_CAP,
) -> list[tuple[str, bool]]:
    """
    Core is authoritative. Feeder may contribute at most (cap - |core_microcaps|) microcaps.
    feeder_candidates is list of (ticker, is_microcap). Returns kept list preserving order.
    """
    remaining = max(0, cap - len(core_microcaps))
    kept: list[tuple[str, bool]] = []
    mc_taken = 0
    for ticker, is_mc in feeder_candidates:
        if is_mc:
            if mc_taken < remaining:
                kept.append((ticker, True))
                mc_taken += 1
            # else: drop microcap candidate
        else:
            kept.append((ticker, False))
    return kept
```

- [ ] **Step 4: Run PASS, commit**

```bash
py -3.14 -m pytest tests/test_watchlist_universe.py -v
git add src/watchlist/__init__.py src/watchlist/universe.py tests/test_watchlist_universe.py
git commit -m "feat(watchlist): universe bounds with tiered liquidity floors + microcap cap"
```

### Task 15: `src/watchlist/core.py` — Core ring JSON I/O

**Files:**
- Create: `src/watchlist/core.py`
- Test: `tests/test_watchlist_core.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_watchlist_core.py
import json
from pathlib import Path
from src.watchlist.core import (
    CoreEntry, load_core, save_core, add_core_entry, remove_core_entry, CORE_MAX,
)

def test_load_missing_returns_empty(tmp_path):
    p = tmp_path / "core.json"
    assert load_core(p) == []

def test_roundtrip(tmp_path):
    p = tmp_path / "core.json"
    entries = [
        CoreEntry(ticker="XYZ", thesis="Block rebrand",
                  added="2026-04-20", conviction="high", review_by="2026-05-20"),
    ]
    save_core(p, entries)
    assert load_core(p) == entries

def test_backup_written(tmp_path):
    p = tmp_path / "core.json"
    save_core(p, [CoreEntry(ticker="A", thesis="t", added="d", conviction="high", review_by="d")])
    save_core(p, [])  # second save should create a backup
    backups = list(tmp_path.glob("core.json.bak-*"))
    assert len(backups) == 1

def test_add_enforces_max(tmp_path):
    p = tmp_path / "core.json"
    entries = [
        CoreEntry(ticker=f"T{i}", thesis="x", added="d", conviction="high", review_by="d")
        for i in range(CORE_MAX)
    ]
    save_core(p, entries)
    try:
        add_core_entry(p, CoreEntry(ticker="NEW", thesis="x", added="d", conviction="high", review_by="d"))
        assert False, "expected ValueError"
    except ValueError:
        pass

def test_remove(tmp_path):
    p = tmp_path / "core.json"
    save_core(p, [CoreEntry(ticker="A", thesis="t", added="d", conviction="high", review_by="d")])
    remove_core_entry(p, "A")
    assert load_core(p) == []
```

- [ ] **Step 2: Run, FAIL**

- [ ] **Step 3: Implement**

```python
"""Core ring — manually curated, git-tracked, up to CORE_MAX entries."""

import json
import shutil
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

CORE_MAX = 25
CORE_PATH_DEFAULT = Path("data/watchlist_core.json")


@dataclass
class CoreEntry:
    ticker: str
    thesis: str
    added: str        # ISO date
    conviction: str   # 'high' | 'medium' | 'watching'
    review_by: str    # ISO date

    @classmethod
    def from_dict(cls, d: dict) -> "CoreEntry":
        return cls(
            ticker=d["ticker"].upper(),
            thesis=d.get("thesis", ""),
            added=d.get("added", ""),
            conviction=d.get("conviction", "watching"),
            review_by=d.get("review_by", ""),
        )


def load_core(path: Path = CORE_PATH_DEFAULT) -> list[CoreEntry]:
    p = Path(path)
    if not p.exists():
        return []
    data = json.loads(p.read_text())
    return [CoreEntry.from_dict(d) for d in data]


def _backup(path: Path):
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = path.with_name(f"{path.name}.bak-{ts}")
    shutil.copy2(path, bak)


def save_core(path: Path, entries: list[CoreEntry]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        _backup(p)
    p.write_text(json.dumps([asdict(e) for e in entries], indent=2))


def add_core_entry(path: Path, entry: CoreEntry) -> None:
    entries = load_core(path)
    if len(entries) >= CORE_MAX:
        raise ValueError(f"Core is full (max {CORE_MAX})")
    if any(e.ticker == entry.ticker for e in entries):
        raise ValueError(f"{entry.ticker} already in Core")
    entries.append(entry)
    save_core(path, entries)


def remove_core_entry(path: Path, ticker: str) -> None:
    entries = [e for e in load_core(path) if e.ticker != ticker.upper()]
    save_core(path, entries)
```

- [ ] **Step 4: Run PASS, commit**

```bash
py -3.14 -m pytest tests/test_watchlist_core.py -v
git add src/watchlist/core.py tests/test_watchlist_core.py
git commit -m "feat(watchlist): Core ring JSON I/O with backup on write"
```

### Task 16: `src/watchlist/feeder.py` — Feeder regeneration + pruning

**Files:**
- Create: `src/watchlist/feeder.py`
- Test: `tests/test_watchlist_feeder.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_watchlist_feeder.py
from pathlib import Path
from src.watchlist.feeder import (
    FeederEntry, load_feeder, save_feeder, regenerate_feeder, FEEDER_MAX,
    should_prune,
)

def test_load_missing(tmp_path):
    assert load_feeder(tmp_path / "f.json") == []

def test_save_and_load(tmp_path):
    p = tmp_path / "f.json"
    e = FeederEntry(ticker="ABCD", composite_score=0.72,
                    signals={"ai_sampling": 0.8, "social_velocity": 0.4, "volume_anomaly": 0.6},
                    first_seen="2026-04-18", days_on_feeder=2)
    save_feeder(p, [e])
    loaded = load_feeder(p)
    assert loaded[0].ticker == "ABCD"
    assert loaded[0].days_on_feeder == 2

def test_regenerate_takes_top_N():
    # 60 scored candidates, should yield top FEEDER_MAX (40)
    scored = [(f"T{i:03d}", 1.0 - i * 0.01) for i in range(60)]
    existing = {}  # no prior Feeder
    new = regenerate_feeder(scored, existing, run_date="2026-04-20")
    assert len(new) == FEEDER_MAX
    assert new[0].ticker == "T000"
    assert new[-1].ticker == "T039"

def test_regenerate_preserves_first_seen():
    scored = [("ABCD", 0.8)]
    existing = {"ABCD": FeederEntry(ticker="ABCD", composite_score=0.7,
                                    signals={}, first_seen="2026-04-18", days_on_feeder=2)}
    new = regenerate_feeder(scored, existing, run_date="2026-04-20")
    assert new[0].first_seen == "2026-04-18"
    assert new[0].days_on_feeder == 3

def test_should_prune():
    # 3 consecutive scores <0.3 → prune
    assert should_prune([0.25, 0.28, 0.22]) is True
    assert should_prune([0.25, 0.35, 0.22]) is False
    assert should_prune([0.25, 0.28]) is False  # <3 scores
```

- [ ] **Step 2: Run, FAIL**

- [ ] **Step 3: Implement**

```python
"""Feeder ring — auto-populated by the screener. Deterministic regeneration."""

import json
from dataclasses import dataclass, asdict, field
from datetime import date
from pathlib import Path

FEEDER_MAX = 40
PRUNE_WINDOW = 3
PRUNE_THRESHOLD = 0.3
FEEDER_PATH_DEFAULT = Path("data/watchlist_feeder.json")


@dataclass
class FeederEntry:
    ticker: str
    composite_score: float
    signals: dict = field(default_factory=dict)  # ai_sampling, social_velocity, volume_anomaly
    first_seen: str = ""
    days_on_feeder: int = 0


def load_feeder(path: Path = FEEDER_PATH_DEFAULT) -> list[FeederEntry]:
    p = Path(path)
    if not p.exists():
        return []
    data = json.loads(p.read_text())
    return [FeederEntry(**d) for d in data]


def save_feeder(path: Path, entries: list[FeederEntry]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps([asdict(e) for e in entries], indent=2))


def regenerate_feeder(
    scored_candidates: list[tuple[str, float]],
    existing: dict[str, FeederEntry],
    run_date: str,
    signals_by_ticker: dict[str, dict] | None = None,
) -> list[FeederEntry]:
    """
    scored_candidates: [(ticker, composite_score)], sorted descending by score.
    existing: dict of ticker -> prior FeederEntry for first_seen preservation.
    """
    top = scored_candidates[:FEEDER_MAX]
    signals_by_ticker = signals_by_ticker or {}
    out: list[FeederEntry] = []
    for ticker, score in top:
        prior = existing.get(ticker)
        first_seen = prior.first_seen if prior else run_date
        days = (prior.days_on_feeder + 1) if prior else 1
        out.append(FeederEntry(
            ticker=ticker,
            composite_score=score,
            signals=signals_by_ticker.get(ticker, {}),
            first_seen=first_seen,
            days_on_feeder=days,
        ))
    return out


def should_prune(recent_composites: list[float],
                 window: int = PRUNE_WINDOW,
                 threshold: float = PRUNE_THRESHOLD) -> bool:
    """Return True if last `window` composites are all below `threshold`."""
    if len(recent_composites) < window:
        return False
    return all(c < threshold for c in recent_composites[-window:])
```

- [ ] **Step 4: Run PASS, commit**

```bash
py -3.14 -m pytest tests/test_watchlist_feeder.py -v
git add src/watchlist/feeder.py tests/test_watchlist_feeder.py
git commit -m "feat(watchlist): Feeder regeneration with first_seen preservation + pruning"
```

### Task 17: `src/watchlist/promotion.py` — promotion candidate detection

**Files:**
- Create: `src/watchlist/promotion.py`
- Test: `tests/test_watchlist_promotion.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_watchlist_promotion.py
from src.watchlist.promotion import (
    is_promotion_candidate, PROMOTION_SCORE_THRESHOLD, PROMOTION_DAYS_SUSTAINED,
)

def test_all_conditions_met():
    recent_composites = [0.7, 0.65, 0.8]  # all >=0.6
    assert is_promotion_candidate(
        recent_composites=recent_composites,
        five_day_move_pct=3.0,             # passes chasing
        volume_anomaly_component=0.5,      # >=0.3
    ) is True

def test_insufficient_days():
    assert is_promotion_candidate(
        recent_composites=[0.8, 0.9],  # only 2 days
        five_day_move_pct=3.0,
        volume_anomaly_component=0.5,
    ) is False

def test_score_dipped():
    assert is_promotion_candidate(
        recent_composites=[0.7, 0.55, 0.8],  # middle <0.6
        five_day_move_pct=3.0,
        volume_anomaly_component=0.5,
    ) is False

def test_chasing():
    assert is_promotion_candidate(
        recent_composites=[0.7, 0.7, 0.7],
        five_day_move_pct=6.0,  # >5% = chasing
        volume_anomaly_component=0.5,
    ) is False

def test_no_tape_confirmation():
    assert is_promotion_candidate(
        recent_composites=[0.7, 0.7, 0.7],
        five_day_move_pct=3.0,
        volume_anomaly_component=0.2,  # <0.3
    ) is False
```

- [ ] **Step 2: Run, FAIL**

- [ ] **Step 3: Implement**

```python
"""Promotion candidate detection: Feeder → Core (manual approval)."""

PROMOTION_SCORE_THRESHOLD = 0.6
PROMOTION_DAYS_SUSTAINED = 3
PROMOTION_CHASING_MAX = 5.0        # 5-day move < 5% (aligned with chasing filter)
PROMOTION_VOLUME_MIN = 0.3         # volume_anomaly component >=0.3


def is_promotion_candidate(
    recent_composites: list[float],
    five_day_move_pct: float,
    volume_anomaly_component: float,
) -> bool:
    if len(recent_composites) < PROMOTION_DAYS_SUSTAINED:
        return False
    if not all(c >= PROMOTION_SCORE_THRESHOLD for c in recent_composites[-PROMOTION_DAYS_SUSTAINED:]):
        return False
    if abs(five_day_move_pct) >= PROMOTION_CHASING_MAX:
        return False
    if volume_anomaly_component < PROMOTION_VOLUME_MIN:
        return False
    return True
```

- [ ] **Step 4: Run PASS, commit**

```bash
py -3.14 -m pytest tests/test_watchlist_promotion.py -v
git add src/watchlist/promotion.py tests/test_watchlist_promotion.py
git commit -m "feat(watchlist): promotion candidate detection with 3 gating conditions"
```

### Task 18: Update `.gitignore` for Feeder + backups

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Append**

```
data/watchlist_feeder.json
data/watchlist_core.json.bak-*
```

- [ ] **Step 2: Commit**

```bash
git add .gitignore
git commit -m "chore: gitignore Feeder and Core backup files"
```

### Task 19: Seed initial Core ring — draft for user approval

**Files:**
- Create: `data/watchlist_core.json`

This task is **interactive** — Claude drafts, user approves before commit.

- [ ] **Step 1: Claude proposes ~15 seed entries**

Draft based on:
- User's cannabis cluster (CURLF, TCNNF, GTBIF, HITI, MSOS are candidates — validate each still has a forward thesis, not just "I own it")
- Any tickers currently scoring high in the AI sampling output from a dry-run
- Specific themes user wants coverage on (ask at step 2)

Output a proposed `data/watchlist_core.json` as a chat draft. Do NOT write the file yet.

- [ ] **Step 2: User reviews, edits inline, approves**

User responds with edits or approval. Iterate until the user signs off.

- [ ] **Step 3: Write approved file**

Write `data/watchlist_core.json` with the approved entries.

- [ ] **Step 4: Validate**

Run: `py -3.14 -c "from src.watchlist.core import load_core; from pathlib import Path; print(len(load_core(Path('data/watchlist_core.json'))))"`
Expected: prints count (~15).

- [ ] **Step 5: Commit**

```bash
git add data/watchlist_core.json
git commit -m "feat(watchlist): seed initial Core ring with <count> conviction names"
```

---

## Phase 3 — Cutover (~1 day)

### Task 20: Add `get_prompt_pulse_score()` to `src/core/prompt_pulse.py`

Flag-guarded function that reads from DB if flag is on, else falls back to existing heuristic.

**Files:**
- Modify: `src/core/prompt_pulse.py`
- Modify: `tests/test_prompt_pulse.py`

- [ ] **Step 1: Append failing tests**

```python
# Append to tests/test_prompt_pulse.py
def test_get_score_uses_heuristic_when_flag_off(monkeypatch, tmp_path):
    monkeypatch.setenv("USE_REAL_PROMPT_PULSE", "false")
    from src.core.prompt_pulse import get_prompt_pulse_score
    score = get_prompt_pulse_score(
        ticker="ABCD", company_name="Foo Co",
        market_cap_millions=800, sector="technology",
        fallback_to_heuristic=True,
    )
    assert 0.0 <= score <= 1.0

def test_get_score_uses_real_signal_when_flag_on(monkeypatch, tmp_path):
    monkeypatch.setenv("USE_REAL_PROMPT_PULSE", "true")
    from src.db import init_db, get_connection, save_prompt_pulse_components
    from datetime import datetime
    db = tmp_path / "t.db"
    init_db(str(db))
    conn = get_connection(str(db))
    save_prompt_pulse_components(conn, ticker="ABCD",
                                  captured_at=datetime.now().isoformat(timespec="seconds"),
                                  scan_type="premarket", ai_sampling=0.8,
                                  social_velocity=0.4, volume_anomaly=0.6, composite=0.64)
    conn.close()
    from src.core.prompt_pulse import get_prompt_pulse_score
    score = get_prompt_pulse_score(ticker="ABCD", company_name="Foo", market_cap_millions=800,
                                    sector="technology", db_path=str(db))
    assert abs(score - 0.64) < 1e-9
```

- [ ] **Step 2: Run, FAIL**

- [ ] **Step 3: Implement**

Append to `src/core/prompt_pulse.py`:

```python
from src.config import Settings


def get_prompt_pulse_score(
    ticker: str,
    company_name: str,
    market_cap_millions: float,
    sector: str,
    has_options: bool = True,
    fallback_to_heuristic: bool = True,
    db_path: str | None = None,
) -> float:
    """
    Unified entry point. Returns a 0-1 prompt_pulse score.
    If USE_REAL_PROMPT_PULSE is on, reads latest composite from DB;
    otherwise uses the discoverability heuristic.
    """
    settings = Settings.from_env()
    if settings.use_real_prompt_pulse:
        from src.db import get_connection, get_latest_composite
        conn = get_connection(db_path) if db_path else get_connection()
        try:
            row = get_latest_composite(conn, ticker)
        finally:
            conn.close()
        if row is not None:
            return float(row["composite"])
        if not fallback_to_heuristic:
            return 0.5  # neutral when no signal available yet
    # Heuristic path
    return estimate_discoverability(ticker, company_name, market_cap_millions, sector, has_options)
```

- [ ] **Step 4: Run PASS, commit**

```bash
py -3.14 -m pytest tests/test_prompt_pulse.py -v
git add src/core/prompt_pulse.py tests/test_prompt_pulse.py
git commit -m "feat(prompt_pulse): flag-guarded get_prompt_pulse_score reads from DB when live"
```

### Task 21: `scripts/signal_refresh.py` — standalone run entry point

End-to-end pre-market / post-close orchestration. Runs the three signal generators, composes, persists to DB.

**Files:**
- Create: `scripts/signal_refresh.py`

- [ ] **Step 1: Implement (integration script, not unit-tested — component tests cover the logic)**

```python
#!/usr/bin/env python3
"""
VantaStonk — Signal Refresh

Runs the v2 signal pipeline:
  1. Pull AI sampling (once per calendar day, skipped if today's row already exists)
  2. Pull social velocity snapshot (Apewisdom)
  3. Compute volume anomalies from Schwab quote data
  4. Compose per-ticker prompt_pulse, persist to prompt_pulse_components

Usage:
    python scripts/signal_refresh.py --scan-type premarket
    python scripts/signal_refresh.py --scan-type postclose
"""

import argparse
import os
import sys
from datetime import datetime, date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from src.config import Settings
from src.db import (
    init_db, get_connection,
    save_prompt_pulse_components, save_ai_sample_raw, save_social_snapshot,
    get_ai_samples_since, get_mentions_history,
)
from src.signals import ai_sampling, social_velocity, volume_anomaly, composite, prompts
from src.signals.ticker_validator import validate_tickers
from src.integrations.schwab_client import SchwabClient


def _run_ai_sampling(conn, settings: Settings, run_date: str):
    """Query all three models, extract tickers, persist raw samples. Return list of MentionRecord."""
    mentions: list[ai_sampling.MentionRecord] = []
    today = run_date
    existing_today = {r["model"] for r in get_ai_samples_since(conn, since=today + "T00:00:00")}
    prev_day = (date.fromisoformat(run_date).toordinal() - 1)
    prev_iso = date.fromordinal(prev_day).isoformat()
    yesterday_tickers: set[str] = set()
    import json as _json
    for r in get_ai_samples_since(conn, since=prev_iso + "T00:00:00"):
        if r["captured_at"].startswith(prev_iso):
            yesterday_tickers.update(_json.loads(r["tickers_extracted"] or "[]"))

    picked = prompts.pick_prompts_for_run(run_date, k=5)
    for model_name, api_key in (
        ("grok", settings.xai_api_key),
        ("gpt-5", settings.openai_api_key),
        ("claude-4.7", settings.anthropic_api_key),
    ):
        if model_name in existing_today:
            continue  # already ran today
        if not api_key:
            print(f"  skip {model_name}: no API key")
            continue
        try:
            client = ai_sampling.build_client(model_name, api_key)
        except Exception as e:
            print(f"  skip {model_name}: client build failed: {e}")
            continue
        for p in picked:
            try:
                res = client.query(p.text, prompt_id=p.prompt_id)
                ranked = ai_sampling.extract_ranked_tickers(res.response_text)
                res.tickers_extracted = [t for t, _ in ranked]
                save_ai_sample_raw(
                    conn, captured_at=datetime.now().isoformat(timespec="seconds"),
                    model=model_name, prompt_id=p.prompt_id, prompt_text=p.text,
                    response_text=res.response_text,
                    tickers_extracted=res.tickers_extracted,
                    token_cost_usd=res.token_cost_usd,
                )
                for ticker, rank in ranked:
                    mentions.append(ai_sampling.MentionRecord(
                        ticker=ticker, model=model_name, rank=rank,
                        is_fresh=ticker not in yesterday_tickers,
                    ))
            except Exception as e:
                print(f"  {model_name} {p.prompt_id} failed: {e}")
    return mentions


def _fetch_social(conn, run_date: str):
    try:
        rows = social_velocity.fetch_apewisdom()
    except Exception as e:
        print(f"  apewisdom fetch failed: {e}")
        return
    now = datetime.now().isoformat(timespec="seconds")
    for r in rows:
        save_social_snapshot(conn, captured_at=now, source="apewisdom",
                             ticker=r.ticker, mentions_count=r.mentions,
                             sentiment_score=r.sentiment)


def _compute_volume_anomaly(client: SchwabClient, tickers: list[str]) -> dict[str, float]:
    """Return ticker -> volume_anomaly score for the given universe."""
    out: dict[str, float] = {}
    for t in tickers:
        try:
            quote = client.get_quote(t)
            if not quote:
                out[t] = 0.0
                continue
            current_price, price_5d_ago = client.get_5day_prices(t)
            if current_price is None or price_5d_ago is None:
                out[t] = 0.0
                continue
            move_pct = ((current_price - price_5d_ago) / price_5d_ago * 100) if price_5d_ago else 0
            if not volume_anomaly.passes_price_filter(move_pct):
                out[t] = 0.0
                continue
            # 30-day avg: approximation using Schwab price history
            hist = client.get_volume_history(t, days=30) if hasattr(client, "get_volume_history") else []
            avg30 = (sum(hist) / len(hist)) if hist else quote.volume
            rvol = volume_anomaly.compute_rvol(today=quote.volume or 0, avg_30d=avg30)
            out[t] = volume_anomaly.score_volume_anomaly(rvol)
        except Exception as e:
            print(f"  rvol {t} failed: {e}")
            out[t] = 0.0
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scan-type", required=True, choices=["premarket", "postclose", "ondemand"])
    args = parser.parse_args()

    settings = Settings.from_env()
    run_date = date.today().isoformat()
    init_db()
    conn = get_connection()

    print(f"Signal refresh: {args.scan_type} {run_date}")

    # 1. AI sampling (skipped on postclose — already done pre-market)
    mentions: list[ai_sampling.MentionRecord] = []
    if args.scan_type != "postclose":
        print("AI sampling...")
        mentions = _run_ai_sampling(conn, settings, run_date)
    # Validate tickers
    schwab = SchwabClient()
    schwab.connect()
    candidate_tickers = list({m.ticker for m in mentions})
    valid, rejected = validate_tickers(candidate_tickers, schwab)
    print(f"  {len(valid)} valid tickers, {len(rejected)} rejected")
    mentions = [m for m in mentions if m.ticker in set(valid)]

    # 2. Social velocity
    print("Social velocity (Apewisdom)...")
    _fetch_social(conn, run_date)

    # 3. Build universe for scoring: Core ∪ Feeder ∪ mentioned-today
    from src.watchlist.core import load_core
    from src.watchlist.feeder import load_feeder
    core_tickers = [e.ticker for e in load_core()]
    feeder_tickers = [e.ticker for e in load_feeder()]
    universe = sorted(set(core_tickers) | set(feeder_tickers) | set(valid))

    # 4. Compute per-ticker scores
    vol_scores = _compute_volume_anomaly(schwab, universe)
    now_iso = datetime.now().isoformat(timespec="seconds")

    for ticker in universe:
        ai_score = ai_sampling.compute_ai_sampling_score(ticker, mentions)
        # social velocity: mentions today vs 7d avg
        hist = get_mentions_history(conn, ticker, source="apewisdom", days=7)
        if hist:
            today_mentions = hist[0]["mentions_count"]
            if social_velocity.passes_noise_floor(today_mentions):
                baseline = sum(h["mentions_count"] for h in hist[1:]) / max(1, len(hist) - 1)
                velocity = social_velocity.compute_velocity(today_mentions, baseline)
                social_score = social_velocity.score_velocity(velocity)
            else:
                social_score = 0.0
        else:
            social_score = 0.0
        vol_score = vol_scores.get(ticker, 0.0)
        comp = composite.compose_with_fallback(ai_score, social_score, vol_score)
        save_prompt_pulse_components(
            conn, ticker=ticker, captured_at=now_iso, scan_type=args.scan_type,
            ai_sampling=ai_score, social_velocity=social_score,
            volume_anomaly=vol_score, composite=comp,
        )

    conn.close()
    print(f"  {len(universe)} tickers scored. Done.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke test — dry run once with flag OFF**

Run: `py -3.14 scripts/signal_refresh.py --scan-type ondemand`
Expected: runs without crashing; scores a handful of universe tickers. Skip if API keys missing — log message should be explicit.

- [ ] **Step 3: Commit**

```bash
git add scripts/signal_refresh.py
git commit -m "feat(scripts): signal_refresh orchestration for pre/post/ondemand runs"
```

### Task 22: Update `scripts/morning_scan.py` to use Core ∪ Feeder

**Files:**
- Modify: `scripts/morning_scan.py`

- [ ] **Step 1: Replace STARTER_WATCHLIST load with Core ∪ Feeder load**

Find `load_watchlist()` (around line 57). Replace the body:

```python
def load_watchlist(path: str = None) -> dict:
    """Load watchlist v2 — union of Core + Feeder."""
    from src.watchlist.core import load_core
    from src.watchlist.feeder import load_feeder
    core = load_core()
    feeder = load_feeder()
    tickers = list({e.ticker for e in core} | {e.ticker for e in feeder})
    return {
        "tickers": sorted(tickers),
        "themes": {},  # themes moved to Core entry metadata; legacy empty
        "core_count": len(core),
        "feeder_count": len(feeder),
    }
```

Remove the STARTER_WATCHLIST constant and the `path` parameter handling (no longer creates a file).

- [ ] **Step 2: Add Promotion Queue section to `run_morning_scan`**

After the Shorties section, before the Rejected section, add:

```python
# Promotion Queue
from src.watchlist.promotion import is_promotion_candidate
from src.db import get_recent_components
promotion_candidates = []
for ticker in tickers:
    recent = get_recent_components(conn, ticker, limit=5)
    if not recent:
        continue
    recent_composites = [r["composite"] for r in reversed(recent)]
    ctx = next((p for p in price_contexts if p.ticker == ticker), None)
    if not ctx:
        continue
    move = ((ctx.price_current - ctx.price_5d_ago) / ctx.price_5d_ago * 100) if ctx.price_5d_ago else 0
    latest = recent[0]
    if is_promotion_candidate(recent_composites, move, latest.get("volume_anomaly", 0)):
        promotion_candidates.append((ticker, latest["composite"], move))

if promotion_candidates:
    full_output += "\n\n---\n\n## Promotion Queue\n"
    full_output += "Feeder names sustaining composite ≥0.6 with tape confirmation.\n"
    for ticker, comp, move in promotion_candidates:
        full_output += f"- **{ticker}**: composite {comp:.2f}, 5d move {move:+.1f}%\n"
```

- [ ] **Step 3: Run a smoke scan**

Run: `py -3.14 scripts/morning_scan.py`
Expected: runs with Core ∪ Feeder tickers. No crashes. Output file saved.

- [ ] **Step 4: Commit**

```bash
git add scripts/morning_scan.py
git commit -m "feat(scan): source universe from Core ∪ Feeder; add Promotion Queue section"
```

### Task 23: Enable real prompt_pulse — flip the flag in live path

**Files:**
- Modify: `scripts/morning_scan.py` (use `get_prompt_pulse_score`)
- Modify: `scripts/score_ticker.py`

- [ ] **Step 1: In morning_scan.py, replace estimate_discoverability call**

Find the scoring loop. Change:

```python
discoverability = estimate_discoverability(
    ticker=ticker, company_name=ticker, market_cap_millions=0, sector="unknown",
)
```

To:

```python
from src.core.prompt_pulse import get_prompt_pulse_score
discoverability = get_prompt_pulse_score(
    ticker=ticker, company_name=ticker, market_cap_millions=0, sector="unknown",
    fallback_to_heuristic=True,
)
```

- [ ] **Step 2: Same change in score_ticker.py** (line ~51)

- [ ] **Step 3: Run unit tests (expect no breakage with flag OFF)**

Run: `py -3.14 -m pytest tests/ -v`
Expected: all previous 23 tests still pass, plus new tests from Phase 1–2.

- [ ] **Step 4: Commit**

```bash
git add scripts/morning_scan.py scripts/score_ticker.py
git commit -m "feat(cutover): scoring scripts call get_prompt_pulse_score (flag-guarded)"
```

### Task 24: `src/tracking/outcomes.py` — hit-rate logging

**Files:**
- Create: `src/tracking/__init__.py`, `src/tracking/outcomes.py`
- Test: `tests/test_tracking_outcomes.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_tracking_outcomes.py
from datetime import datetime
from src.db import init_db, get_connection
from src.tracking.outcomes import log_feeder_entries, fill_outcome_prices

def test_log_feeder_only_creates_once(tmp_path):
    db = tmp_path / "t.db"
    init_db(str(db))
    conn = get_connection(str(db))

    entries = [{"ticker": "ABCD", "composite_score": 0.72}]
    now = datetime.now().isoformat(timespec="seconds")

    class FakeClient:
        def get_quote(self, t):
            return type("Q", (), {"last_price": 10.0})()
    client = FakeClient()

    log_feeder_entries(conn, entries, now, "premarket", client)
    log_feeder_entries(conn, entries, now, "premarket", client)  # idempotent
    rows = conn.execute("SELECT COUNT(*) as n FROM recommendation_outcomes").fetchone()
    assert rows["n"] == 1
    conn.close()
```

- [ ] **Step 2: Run, FAIL**

- [ ] **Step 3: Implement**

`src/tracking/__init__.py`: empty.

`src/tracking/outcomes.py`:

```python
"""Hit-rate tracking for Feeder entries."""

from src.db import (
    save_recommendation_outcome, get_outcome,
    update_outcome_price, mark_outcome_dropped,
)


def log_feeder_entries(conn, feeder_entries, captured_at, scan_type, schwab_client):
    """For each Feeder entry, create an outcome row on first appearance."""
    source_by_scan = {
        "premarket": "premarket_quote",
        "postclose": "postclose_last",
        "ondemand": "intraday_last",
    }
    source = source_by_scan.get(scan_type, "intraday_last")
    for entry in feeder_entries:
        ticker = entry["ticker"] if isinstance(entry, dict) else entry.ticker
        score = entry["composite_score"] if isinstance(entry, dict) else entry.composite_score
        existing = get_outcome(conn, ticker, captured_at, "feeder")
        if existing:
            continue
        quote = schwab_client.get_quote(ticker)
        price = getattr(quote, "last_price", 0.0) if quote else 0.0
        save_recommendation_outcome(
            conn, ticker=ticker, ring="feeder", first_appeared_at=captured_at,
            entry_price=price, entry_price_source=source,
            composite_score_at_entry=score,
        )


def fill_outcome_prices(conn, schwab_client, days_ago: int, field_name: str):
    """Fill price_{1d|3d|7d} for outcomes that are exactly days_ago old."""
    rows = conn.execute("""
        SELECT ticker, first_appeared_at, ring
        FROM recommendation_outcomes
        WHERE date(first_appeared_at) = date('now', '-' || ? || ' days')
          AND (
            (? = 'price_1d' AND price_1d IS NULL)
            OR (? = 'price_3d' AND price_3d IS NULL)
            OR (? = 'price_7d' AND price_7d IS NULL)
          )
    """, (days_ago, field_name, field_name, field_name)).fetchall()
    for r in rows:
        q = schwab_client.get_quote(r["ticker"])
        if q and q.last_price:
            update_outcome_price(conn, r["ticker"], r["first_appeared_at"], r["ring"],
                                  field=field_name, price=q.last_price)
```

- [ ] **Step 4: Run PASS, commit**

```bash
py -3.14 -m pytest tests/test_tracking_outcomes.py -v
git add src/tracking/__init__.py src/tracking/outcomes.py tests/test_tracking_outcomes.py
git commit -m "feat(tracking): log Feeder entries for hit-rate analysis"
```

### Task 25: `scripts/fill_outcomes.py` — scheduled price fill

**Files:**
- Create: `scripts/fill_outcomes.py`

- [ ] **Step 1: Implement**

```python
#!/usr/bin/env python3
"""
VantaStonk — Fill N-day outcome prices.

Intended to run daily via `schedule`. Looks up Feeder/Core entries that are
exactly 1, 3, or 7 trading days old and fills their price_1d / price_3d / price_7d.
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv; load_dotenv()

from src.db import init_db, get_connection
from src.tracking.outcomes import fill_outcome_prices
from src.integrations.schwab_client import SchwabClient


def main():
    init_db()
    conn = get_connection()
    client = SchwabClient()
    client.connect()
    for days_ago, field in [(1, "price_1d"), (3, "price_3d"), (7, "price_7d")]:
        fill_outcome_prices(conn, client, days_ago, field)
    conn.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Commit**

```bash
git add scripts/fill_outcomes.py
git commit -m "feat(tracking): fill_outcomes script for 1d/3d/7d follow-up prices"
```

### Task 26: Schedule cron jobs via the `schedule` skill

**Not a code task — runtime configuration.**

- [ ] **Step 1: Use the `schedule` skill to create three triggers**

Create triggers for:
- Pre-market signal refresh: `0 6 * * 1-5` → `py -3.14 scripts/signal_refresh.py --scan-type premarket && py -3.14 scripts/morning_scan.py`
- Post-close signal refresh: `30 14 * * 1-5` → same chain with `--scan-type postclose`
- Daily outcome fills: `0 21 * * 1-5` (9pm PT, after market close) → `py -3.14 scripts/fill_outcomes.py`

- [ ] **Step 2: Verify triggers listed**

Run CronList via the skill to confirm all three triggers are scheduled.

- [ ] **Step 3: Commit any config files the skill writes**

```bash
# Only if schedule skill generates tracked config
git status
git add -A
git commit -m "chore: schedule cron triggers for signal pipeline + hit-rate fills" || true
```

### Task 27: Phase 3 cutover — flip `USE_REAL_PROMPT_PULSE=true`

**Files:**
- Modify: `.env` (per-machine, NOT committed)

- [ ] **Step 1: Pre-flight checklist**

Run manually:
- `py -3.14 scripts/signal_refresh.py --scan-type ondemand` — 3 consecutive days of successful runs, output reviewed
- `py -3.14 -m pytest tests/ -v` — all green
- Core ring seed file committed
- `data/vantastonk.db` has actual rows in `prompt_pulse_components` (query: `sqlite3 data/vantastonk.db 'SELECT COUNT(*) FROM prompt_pulse_components'`)

- [ ] **Step 2: Flip the flag**

Edit `.env` on each machine:

```
USE_REAL_PROMPT_PULSE=true
```

- [ ] **Step 3: Confirm by scoring a known ticker**

Run: `py -3.14 scripts/score_ticker.py AAPL`
Expected: score output shows `prompt_pulse` pulled from DB (not the heuristic).

- [ ] **Step 4: Monitor first live morning scan**

Let the next cron-triggered pre-market run execute. Review output. If junk, flip flag back: `USE_REAL_PROMPT_PULSE=false`.

No commit — `.env` is gitignored and per-machine by design.

---

## Phase 4 — Observation window (1–2 weeks)

No code changes. Daily review of scan output, note surprises, log weight-adjustment hunches.

- [ ] **Step 1: Create a daily review log**

Append a short section to `Notes.md` each day:

```markdown
### Observation — YYYY-MM-DD

- Top 5 Feeder picks by composite: ...
- Any outright bad calls? ...
- Any great calls the system missed? ...
- Token spend: ~$X
```

- [ ] **Step 2: After 7 days, compute first hit-rate summary**

Run: `py -3.14 -c "from src.db import get_connection; conn=get_connection(); rows = conn.execute('SELECT ticker, entry_price, price_1d, price_3d, price_7d FROM recommendation_outcomes WHERE price_7d IS NOT NULL').fetchall(); [print(dict(r)) for r in rows]"`

Eyeball the distribution. Is median return at 7d positive?

---

## Phase 5 — Tuning pass (~1–2 days)

### Task 28: Review composite sub-weights

**Files:**
- Modify: `src/signals/composite.py` (weights dict)
- Modify: `tests/test_signal_composite.py` (test_weights_sum_to_one still passes)

- [ ] **Step 1: Run backtest script (built as a simple Jupyter/CLI analysis)**

Compute hit-rate slices:
- Names where `ai_sampling` was dominant: how did they perform?
- Names where `social_velocity` was dominant?
- Names where `volume_anomaly` was dominant?

Write a small script or run a notebook interactively.

- [ ] **Step 2: If a component underperforms, reduce its weight**

Adjust `COMPONENT_WEIGHTS` in `src/signals/composite.py`. Keep sum=1.0.

- [ ] **Step 3: Run test suite, commit**

```bash
py -3.14 -m pytest tests/ -v
git add src/signals/composite.py
git commit -m "tune: composite sub-weights post-observation (<reason>)"
```

### Task 29: Review AI model weights

Same pattern for `MODEL_WEIGHTS` in `src/signals/ai_sampling.py`. Check if Grok-only signals converted; if not, rebalance.

- [ ] Adjust `MODEL_WEIGHTS`, keep sum=1.0, run tests, commit.

### Task 30: Review promotion thresholds

Check promotion rate against target (~1-2/week). Adjust `PROMOTION_SCORE_THRESHOLD`, `PROMOTION_DAYS_SUSTAINED`, or `PROMOTION_VOLUME_MIN` in `src/watchlist/promotion.py`.

- [ ] Adjust constants, run tests, commit.

### Task 31: Wire v1.1 scheduled reviews

Use the `schedule` skill to set +14 day and +30 day reminder triggers.

- [ ] Create reminder triggers per spec §10.1.

### Task 32: Clean up old heuristic path

Once the real signal has been live for 4+ weeks without incident:

- [ ] Remove `fallback_to_heuristic` path from `get_prompt_pulse_score` (spec §9.2: "Keep the old heuristic code until Phase 5 ends clean").
- [ ] Mark `estimate_discoverability` as deprecated (or delete if no other callers).
- [ ] Commit.

---

## Appendix — Test coverage summary at plan completion

| Module | Tests |
|---|---|
| `src/signals/ticker_validator.py` | 2 |
| `src/signals/prompts.py` | 4 |
| `src/signals/ai_sampling.py` | 8 |
| `src/signals/social_velocity.py` | 4 |
| `src/signals/volume_anomaly.py` | 3 |
| `src/signals/composite.py` | 5 |
| `src/watchlist/universe.py` | 7 |
| `src/watchlist/core.py` | 5 |
| `src/watchlist/feeder.py` | 5 |
| `src/watchlist/promotion.py` | 5 |
| `src/tracking/outcomes.py` | 1 |
| `src/config.py` | 2 |
| `src/db.py` (v2 functions) | 4 |
| `src/core/prompt_pulse.py` (new) | 2 |
| **Total new tests** | **~57** |

Existing 23 tests should continue to pass unchanged.

---

## Skills to invoke during execution

- @superpowers:subagent-driven-development or @superpowers:executing-plans — for task execution
- @superpowers:test-driven-development — embedded per-task via the Write/Run/Implement/Run/Commit cycle
- @superpowers:verification-before-completion — before claiming each task complete, the test must run and pass
- @superpowers:sync — periodically pull/push to keep laptop and desktop aligned during the build
