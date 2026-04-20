# VantaStonk Watchlist v2 — Design

**Date:** 2026-04-20
**Status:** Approved design, ready for implementation plan
**Author:** Claude (Opus 4.7) in collaboration with CJ Montgomery

## 1. Context and motivation

The current `STARTER_WATCHLIST` in `scripts/morning_scan.py` is 20 mega-cap tech names (AAPL, MSFT, NVDA, etc.). This directly contradicts the VantaStonk thesis:

- **Thesis**: "Predict what AI tools will recommend in the next 6–48 hours; buy the rumor; pre-catalyst, under-discovered names."
- **Reality**: Mega-caps are maximally discovered. They move with the market. The chasing filter rejects almost all of them every day — not because the system is broken, but because the universe is wrong.

The scoring engine has a second problem: `prompt_pulse × 0.24` is the second-heaviest factor, but its implementation is a fake market-cap discoverability heuristic. The actual "Prompt Pulse" concept (what AI models are starting to recommend) is not measured anywhere.

This design fixes both problems simultaneously by replacing the watchlist and replacing the fake `prompt_pulse` with a real signal pipeline. The two are tightly coupled — the signal pipeline IS the screener that builds the watchlist, and it also feeds the scoring engine.

## 2. Goals

- Surface actionable small/mid-cap setups 6–48 hours before they crowd.
- Replace the fake `prompt_pulse` factor with a real multi-source signal.
- Keep infrastructure changes minimal where possible — reuse scoring engine, filters, Glance/Shorties output unchanged.
- Keep the system runnable on a single developer's workstation with free/cheap data sources.

## 3. Non-goals

- Exit signals for existing positions. Handled separately as a sibling project.
- Intraday scans. Deferred to v1.1 review (see §9).
- Trade journal / full feedback loop. Minimal hit-rate logging ships here; full analytics is a separate project.
- News/catalyst data from Benzinga/Polygon. Deferred pending budget justification.
- Options flow (Cheddar Flow). Deferred to v1.2 as a fourth signal source.
- A UI. CLI + markdown output remains the interface until the FastAPI dashboard lands.

## 4. System overview

Two-ring, hybrid-sourced, signal-fed watchlist:

- **Core ring (≤25 names)** — manually curated, high-conviction. User maintains weekly. Scanned every run.
- **Feeder ring (≤40 names)** — screener-populated from signal pipeline. Regenerated twice daily.
- **Signal pipeline** — new subsystem producing real `prompt_pulse` scores from three sources (AI model sampling, social velocity, volume anomalies). Replaces the market-cap heuristic in `src/core/prompt_pulse.py`.

Unchanged: `morning_scan.py` → filters → scoring → Glance/Shorties workflow. Same CLI, same markdown output. The engine's `prompt_pulse × 0.24` weight stays at 0.24 — only the *source* of the factor changes.

Positions (the user's 28 existing holdings, ~$3M) stay out of the watchlist. That's a deliberate separation of concerns — "should I buy?" and "should I sell?" have fundamentally different logic (cost basis, thesis decay, concentration risk).

## 5. Signal pipeline

Three parallel signal generators feed into a composite `prompt_pulse` score (0.0–1.0).

```
prompt_pulse = clamp(
    0.5 * ai_sampling + 0.3 * social_velocity + 0.2 * volume_anomaly,
    0.0, 1.0
)
```

Sub-weights are v1 defaults; subject to tuning at +14 days (see §9).

### 5.1 AI model sampling (weight: 0.5)

**Purpose:** Directly measure what frontier AI models are starting to surface. This is the VantaStonk thesis, operationalized.

**Sources:** OpenAI (GPT-5), Anthropic (Claude 4.7), xAI (Grok). Cost ~$0.10–0.50 per model per day.

**Mechanism:**
- 5–7 rotating prompts, run once per day per model. Claude (as code author) drafts the initial prompt set; user reviews before launch. Example prompts:
  - "What under-the-radar small/mid-cap stocks should retail traders watch this week?"
  - "Which sectors appear to be starting a rotation?"
  - "Name 5 stocks with upcoming catalysts in the next 2 weeks that aren't widely discussed yet."
- Parse responses for ticker symbols via regex plus context validation (rejects cashtags that aren't real tickers per Schwab lookup).
- Dedupe per model across prompts.
- Store raw responses in `ai_samples_raw` table for audit and prompt-tuning.

**Scoring — model-weighted convergence:**

Each model has a weight reflecting signal quality for this use case:
- Grok: **0.45** — real-time X firehose, earliest detector of breaking narratives
- GPT-5: **0.30** — broadest training, strong thematic synthesis, slower to new narratives
- Claude 4.7: **0.25** — strong reasoning, catches thesis nuance, similar data vintage to GPT

Convergence score for a ticker = sum of weights of models that mention it (max 1.00). Example scenarios:

| Models mentioning | Score | Interpretation |
|---|---|---|
| All three | 1.00 | High conviction; idea spreading across AI knowledge |
| Grok + GPT | 0.75 | Strong; real-time + mainstream agree |
| Grok + Claude | 0.70 | Strong; real-time + reasoning model agree |
| GPT + Claude | 0.55 | Moderate; slower consensus without real-time voice |
| Grok only | 0.45 | Early signal worth watching; often what a thesis is chasing |
| GPT only | 0.30 | Weak; potentially stale thesis |
| Claude only | 0.25 | Weak; potentially stale thesis |

**Multipliers on top of convergence:**
- Freshness: +0.2 for tickers mentioned today that weren't mentioned yesterday
- Rank-weight: 1.5x for tickers appearing in top-3 of an enumerated response list vs. buried at the bottom

Final `ai_sampling` score clamped to [0.0, 1.0].

### 5.2 Social velocity (weight: 0.3)

**Purpose:** Catch retail-forming theses before institutional flows arrive.

**Source:** Apewisdom.io public JSON (free, no auth). Aggregates r/WSB, r/stocks, r/pennystocks, r/smallstreetbets. Fetched twice daily aligned with screener runs.

**Mechanism:**
- Pull ticker mention counts from Apewisdom.
- Compute 7-day rolling baseline per ticker.
- Velocity = today's mentions / 7-day baseline.
- Noise floor: ignore if absolute mention count <5.

**Scoring:**
- Velocity 1.5–2x: 0.3
- 2–5x: 0.6
- 5–10x: 0.9
- 10x+: 1.0 (capped)

**Fallback:** If Apewisdom is down, scrape Reddit directly via PRAW (more work, slightly more fragile). Not implemented in v1; component defaults to 0.5 neutral on failure.

### 5.3 Volume anomaly (weight: 0.2)

**Purpose:** Confirm with tape. Volume coming in *without* price moving = accumulation, not chase.

**Source:** Schwab quotes + historical (already wired in `src/integrations/schwab_client.py`).

**Mechanism:**
- For each ticker in the universe: compute 30-day average daily volume.
- Relative Volume (RVOL) = today's volume / 30-day average.
- Price filter: only counts if 5-day price move is <5% (aligned with the chasing threshold). Catches accumulation, rejects late-to-party.

**Scoring:**
- RVOL 1.5–2x: 0.3
- 2–3x: 0.6
- 3–5x: 0.85
- 5x+: 1.0

## 6. Two-ring structure

### 6.1 Core ring

**File:** `data/watchlist_core.json` (tracked in git; syncs across machines)

**Size:** Up to 25 tickers. Target working size ~20.

**Entry format:**
```json
{
  "ticker": "XYZ",
  "thesis": "Block rebrand + stablecoin exposure, pre-institutional re-rating",
  "added": "2026-04-20",
  "conviction": "high",
  "review_by": "2026-05-20"
}
```

`conviction` ∈ {`high`, `medium`, `watching`}. `review_by` is a soft deadline prompting the user to re-validate the thesis.

**Source:** User. Weekly review cadence (add/drop based on thesis state). Claude provides suggested promotions from the Feeder ring; user approves manually.

**Scanned:** Every scan (pre-market + post-close).

### 6.2 Feeder ring

**File:** `data/watchlist_feeder.json` (gitignored; regenerates deterministically from centralized signal data)

**Size:** Up to 40 tickers.

**Entry format:**
```json
{
  "ticker": "ABCD",
  "composite_score": 0.72,
  "signals": {"ai_sampling": 0.8, "social_velocity": 0.4, "volume_anomaly": 0.6},
  "first_seen": "2026-04-18",
  "days_on_feeder": 2
}
```

**Source:** Screener auto-populates twice daily. Top 40 composite scores within universe bounds.

**Scanned:** Every scan, lighter-weight (reuses cached signal data).

**Pruning:** Drops off if composite score <0.3 for 3 consecutive scans.

### 6.3 Promotion rules (Feeder → Core candidate)

A Feeder name becomes a **promotion candidate** when ALL three conditions hold:
- Composite score ≥0.6 sustained for 3+ days
- Still passes chasing filter (5-day move <5%)
- Volume anomaly component ≥0.3 (tape confirming narrative)

Candidates surface in a new **"Promotion Queue"** section of the morning scan output. Each candidate includes:
- Current composite score and sub-scores
- Days sustained above 0.6
- Thesis bullets drafted from underlying AI sampling transcripts (so the user doesn't start from a blank page)
- Suggested conviction tier

**User promotes manually** by editing `watchlist_core.json`. System never auto-promotes. This is the conviction gate.

### 6.4 Universe bounds (applies to both rings)

- Market cap: $50M – $10B
- Liquidity floors (tiered):
  - Micro-cap ($50M–$300M): $500K/day dollar volume minimum
  - Small/mid ($300M–$10B): $2M/day dollar volume minimum
- Sectors: unrestricted (let the edge find the theme)
- Hard cap: maximum 15 micro-caps across both rings combined (noise ceiling)

## 7. Operational flow

### 7.1 Pre-market run — 6:00 AM PT (heavy)

1. **AI sampling** (once daily): query OpenAI, Anthropic, xAI; parse tickers; compute per-ticker `ai_sampling` score.
2. **Social velocity**: fetch Apewisdom; compute velocity vs. 7-day baseline.
3. **Volume anomaly**: use prior-day EOD Schwab data + any pre-market quotes.
4. **Composite `prompt_pulse`**: computed for all tickers in universe (Core ∪ Feeder ∪ new signal-surfaced candidates).
5. **Feeder regenerates**: top 40 composite scores become new Feeder (subject to universe bounds + micro-cap cap).
6. **Morning scan**: runs existing filters + scoring + Glance + Shorties; adds new **Promotion Queue** section.
7. Output saved to `data/glance_YYYY-MM-DD.md`.

### 7.2 Post-close run — 2:30 PM PT (light)

1. AI sampling **skipped** (already done today).
2. Social velocity re-fetched (end-of-day mention counts tend to peak late).
3. Volume anomaly uses final EOD Schwab data.
4. Composite `prompt_pulse` recomputed.
5. Feeder re-ranked; names may add/drop.
6. **Delta-focused output**: only surfaces names whose signal state changed today (new entries, new exits, new promotion candidates).
7. Appended to `data/glance_YYYY-MM-DD.md`.

### 7.3 On-demand — `score_ticker.py`

Same CLI. `prompt_pulse` component now reflects real composite signals from cached signal data (no API re-queries per invocation).

### 7.4 Graceful degradation

If any signal source fails:
- Affected component defaults to **0.5 (neutral)** for impacted tickers.
- Composite computed anyway.
- Error logged; warning shows in scan output.
- Scan never skips a run.

### 7.5 Cron wiring

Two entries (weekdays only), wired via the `schedule` skill once v1 ships:
- `0 6 * * 1-5` → pre-market run
- `30 14 * * 1-5` → post-close run

No market-hours scans in v1. Signal data doesn't move fast enough intraday to justify the compute + API cost. Revisited in v1.1 (see §9).

## 8. Data storage

Three new SQLite tables appended to `sql/schema.sql`. All live in `data/vantastonk.db` (per-machine, gitignored).

### 8.1 `signal_scores`

Per-ticker composite history. Enables the "3-day sustained ≥0.6" promotion rule and Feeder pruning.

```sql
CREATE TABLE signal_scores (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ticker TEXT NOT NULL,
  captured_at DATETIME NOT NULL,
  scan_type TEXT NOT NULL,       -- 'premarket' | 'postclose'
  ai_sampling REAL,
  social_velocity REAL,
  volume_anomaly REAL,
  composite REAL NOT NULL,
  UNIQUE(ticker, captured_at)
);
CREATE INDEX idx_signal_ticker_time ON signal_scores(ticker, captured_at DESC);
```

### 8.2 `ai_samples_raw`

Audit trail and prompt-tuning source.

```sql
CREATE TABLE ai_samples_raw (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  captured_at DATETIME NOT NULL,
  model TEXT NOT NULL,           -- 'grok' | 'gpt-5' | 'claude-4.7'
  prompt_id TEXT NOT NULL,
  prompt_text TEXT NOT NULL,
  response_text TEXT NOT NULL,
  tickers_extracted TEXT,        -- JSON array
  token_cost_usd REAL
);
CREATE INDEX idx_ai_samples_time ON ai_samples_raw(captured_at DESC);
```

### 8.3 `social_snapshots`

Mention counts over time for velocity baselines.

```sql
CREATE TABLE social_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  captured_at DATETIME NOT NULL,
  source TEXT NOT NULL,          -- 'apewisdom' | 'reddit_direct'
  ticker TEXT NOT NULL,
  mentions_count INTEGER NOT NULL,
  sentiment_score REAL,
  UNIQUE(captured_at, source, ticker)
);
CREATE INDEX idx_social_ticker_time ON social_snapshots(ticker, captured_at DESC);
```

### 8.4 Retention

30-day retention across all three tables, then rollup to daily aggregates. Monthly rollup runs via the same `schedule` skill.

- `signal_scores`: 30 days granular, then daily averages per ticker.
- `ai_samples_raw`: 30 days full responses, then prune `response_text` but retain `tickers_extracted`.
- `social_snapshots`: 30 days granular, then daily averages.

### 8.5 Watchlist files

- `data/watchlist_core.json` — **git-tracked**, cross-machine sync.
- `data/watchlist_feeder.json` — **gitignored**, regenerates deterministically.
- `data/watchlist_core.json.bak-YYYYMMDD-HHMMSS` — auto-backup before each manual edit.

## 9. Testing and rollout

### 9.1 Testing

- **Unit tests** (fast, deterministic): ticker extraction from AI responses, composite scoring math, promotion rule evaluation, universe bounds filters, velocity computation. Target ≥80% coverage on new modules. Reuses existing pytest setup.
- **Integration tests**: AI API calls use record/replay cassettes (`vcrpy`) so CI doesn't burn real tokens. Apewisdom + Schwab fetchers mocked with fixture payloads (including malformed/empty to verify degradation).
- **End-to-end smoke**: fixture universe → full pipeline → assert Feeder output shape.
- **Manual pre-deploy smoke**: run pre-market scan manually 3 consecutive days before enabling cron. Check output sanity, verify token costs, confirm Feeder composition looks sane.

### 9.2 Rollout phases

| Phase | Work | Duration | Risk |
|---|---|---|---|
| 1 | Signal pipeline built; writes scores to DB but NOT wired to live scoring | ~3–4 days | Low — runs in shadow |
| 2 | Universe + Core/Feeder ring mechanics; initial Core seeding | ~2 days | Low — new files, no engine change |
| 3 | Cutover: switch `prompt_pulse` source to real signal; update tests; enable cron | ~1 day | Medium — engine behavior changes |
| 4 | Observation window, no code | 1–2 weeks | Zero — just watching |
| 5 | Tuning pass: sub-weights, model weights, promotion thresholds | ~1–2 days | Low — numbers only |

**Backout:** Phases 1–2 trivially reversible. Phase 3 guarded by `USE_REAL_PROMPT_PULSE` config flag that can be flipped back to the old heuristic in seconds. Keep the old heuristic code until Phase 5 ends clean.

### 9.3 Hit-rate tracking (minimal v1)

After each run, auto-log Feeder entries with timestamp + entry price to a new `recommendation_outcomes` table. Query at N=1, N=3, N=7 days: did Feeder picks outperform a random universe sample? Weekly summary appended to `data/glance_*.md` as a "Scorecard" section.

This is the minimal feedback loop. Full trade-journal integration is a separate project.

### 9.4 Core ring seeding (Phase 2 deliverable)

Claude proposes an initial ~15 Core names based on:
- User's existing cannabis exposure (convert validated holdings to thesis-annotated Core entries)
- Current AI/social signal hits that fit universe bounds
- Specific themes user wants coverage on

User edits/approves/rejects before Phase 2 flips live.

## 10. v1.1 roadmap

### 10.1 Scheduled reviews

All wired via `schedule` skill after launch.

| Trigger | Review item | Action |
|---|---|---|
| +14 days | Composite sub-weights (AI 0.5 / social 0.3 / volume 0.2) | Backtest against 2 weeks of hit-rate data; tune |
| +14 days | AI model weights (Grok 0.45 / GPT 0.30 / Claude 0.25) | Did Grok-only signals convert? Rebalance if not |
| +14 days | Promotion thresholds (0.6 / 3-day sustained / ≥0.3 volume) | Tune to hit a target promotion rate (~1–2 per week) |
| +30 days | **Intraday scan viability** (add 11am PT mid-session run?) | Check if Grok/social catch breaks our 2:30pm misses |
| +30 days | Core ring count (20/25) + Feeder size (40) | Right-size based on actual signal density observed |

### 10.2 Explicitly deferred (v1.2+)

- **Exit-signal engine** for existing positions (sibling project).
- **Cheddar Flow / options flow signal** — 4th signal source, ~0.15 weight, rebalance others.
- **Trade journal + full hit-rate feedback loop** — upgrades §9.3 minimal version.
- **AI research partner** — conversational companion for deep-dive on watchlist names.
- **Local FastAPI dashboard** — unifies watchlist + positions + signal history (Phase 3 of project roadmap).
- **News/catalyst integration** (Benzinga, Polygon) — once budget justifies $30/mo+.
- **Pair trade detection** — within-theme divergence scanning.

### 10.3 Known risks

| Risk | Mitigation |
|---|---|
| AI API cost drift | Log token spend per run; alert if daily >$5 |
| Apewisdom stability (free public JSON, no SLA) | Fallback to Reddit direct via PRAW (deferred to v1.1); social component → 0.5 neutral on failure in v1 |
| AI models hallucinate fake tickers | Validate extracted tickers against Schwab `get_quote` before scoring; reject unmatched |
| Prompt drift over time as models retrain | Rotating prompt set + raw response archive enables period comparison |
| Grok overweight amplifies pump/dump noise | +14 day review catches this; watch for Grok-only signals that crater |

## 11. Open questions for user review

None known. All architectural decisions locked during brainstorming. Calibration decisions (sub-weights, model weights, promotion thresholds, retention, Core/Feeder sizes) are v1 defaults subject to the +14/+30 day reviews in §10.1.
