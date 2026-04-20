# Vantastonk (95v2) — Notes

## Current Focus

## To Do

~~port in the Schwab Developer API connection~~
- Phase 2: AI research partner + Prompt Pulse automation
- Phase 3: Local FastAPI dashboard
- Phase 4: Alerts + position monitoring + trade journal auto-logging
- Tune watchlist with smaller, under-discovered names

## Done

### 2026-04-19
- Built full 95v2 scoring engine (scoring.py, filters.py, prompt_pulse.py)
- Built all 3 workflows (Glance, ShadowList, Shorties)
- Created SQLite schema (8 tables with indexes)
- 23 tests written and passing
- Schwab Developer API connected and live
- Built score_ticker.py CLI — scored PLTR with live data (chasing detected +14.3%)
- Built morning_scan.py — ran full scan across 20-ticker watchlist
- First live morning scan: 18/19 tickers flagged as chasing (broad market rally week)
- Created strategic roadmap (4 phases)

## Daily Log

### 2026-04-20

**Morning — live market work (~72 min to close):**
- Ran `morning_scan.py` — only AMZN passed filters (+3.5%, C grade); 18/19 rejected as chasing (SQ missing — rebranded to XYZ).
- Added new [scripts/positions_snapshot.py](scripts/positions_snapshot.py) and pulled all 28 positions: portfolio $3.04M MV, −$5,123 on the day. Cannabis complex ripping — MSOX +15%, CVSI +12%, CURLF +9%, MSOS +8%, TCNNF +8%. Biggest $ drag: PFN −$13K (on a $2.36M position).
- Scored MSOX/CURLF/GME via `score_ticker.py` — all three rejected as chasing (cannabis complex +24% over 5 days; don't add here, let winners run).

**Mid-day cleanup commits:**
- `188b2a1` — committed `positions_snapshot.py`, replaced SQ with XYZ in watchlist.
- `4e54578` — tracked `data/watchlist.json` for cross-machine sync (narrowed gitignore).
- `d0d71cb` — untracked `data/vantastonk.db` (per-machine scan history; was causing binary merge risk).

**Afternoon — design sprint for watchlist v2:**
- Realized the mega-cap starter watchlist directly contradicts the "pre-catalyst, under-discovered" thesis — every scan rejects everything as chasing because mega-caps move with the market. Also: `prompt_pulse × 0.24` is the second-heaviest scoring factor, and its implementation is a fake market-cap heuristic. Both get fixed together in v2.
- Brainstormed design via `superpowers:brainstorming` — decided: hybrid two-ring (manual Core ≤25 + screener-fed Feeder ≤40), tiered market caps with tiered liquidity floors, composite Prompt Pulse fed by AI model sampling (Grok-weighted higher for real-time X access) + social velocity (Apewisdom) + volume anomalies (Schwab). Cutover guarded by `USE_REAL_PROMPT_PULSE` flag.
- Spec written + reviewer-approved: [docs/superpowers/specs/2026-04-20-watchlist-v2-design.md](docs/superpowers/specs/2026-04-20-watchlist-v2-design.md) — commits `41b4336`, `96d416c`.
- Implementation plan written + reviewer-approved: [docs/superpowers/plans/2026-04-20-watchlist-v2-implementation.md](docs/superpowers/plans/2026-04-20-watchlist-v2-implementation.md) — 33 tasks across 5 phases, ~57 new tests. Commits `a8465ff`, `7a9eb65`.

**EOD — kicked off implementation via subagent-driven-development:**
- **Task 1 done** (commits `41439c6` + `be0faf1`): added 4 new SQLite tables (`prompt_pulse_components`, `ai_samples_raw`, `social_snapshots`, `recommendation_outcomes`) + `created_at` audit columns. 24 tests passing.
- **Task 2 spec-compliant** (commit `4146732`): added `save_prompt_pulse_components`, `get_recent_components`, `get_latest_composite` to `src/db.py`. Test passes. Code-quality reviewer flagged 3 minor cleanups (docstring, unused `timedelta` import, upsert coverage test) — pending tomorrow.
- Observed subagent-driven cadence burns ~5-6 subagents per task. Decided tomorrow's sessions use hybrid "Option 2" cadence: inline execution for mechanical tasks, subagents only for complex/high-risk pieces (orchestration, cutover, interactive steps). Saved this as a feedback memory.

**Tomorrow's entry point:**
1. Close Task 2's pending cleanups (5 min inline work).
2. Continue Task 3 onward on the plan.
3. Task 19 (Core ring seed draft) will pause for my approval. Task 27 (flip `USE_REAL_PROMPT_PULSE=true`) will pause for pre-flight confirmation.

### 2026-04-19

- Project bootstrap day: went from empty repo to live Schwab-connected trading intelligence system
- PLTR scored F (0.242) due to chasing penalty — system working as designed
- Market observation: entire watchlist ran +5-25% this week, almost nothing actionable = sit on hands

### 2026-04-19 (desktop setup)

- Brought desktop machine online as second VantaStonk workstation (mirror of laptop)
- Untangled GitHub repo: default branch was wrongly `main` with Kalshibot content; restored `master` as default, deleted the stale `main` branch
- Installed Python 3.14 deps system-wide (schwab-py 1.5.1 + transitive) to match laptop pattern
- Copied Schwab credentials into `.env` and completed fresh OAuth login → desktop-specific `data/schwab_token.json`
- Verified live connection: AAPL quote + 25 positions pulled cleanly
- All 23 tests pass on Python 3.14.3 (0.13s)
- **Bug fix committed** (`0800fe1`): `scripts/schwab_login.py` needed `if __name__ == '__main__'` guard (Windows multiprocessing spawn) and `interactive=False` (breaks in non-TTY contexts). Laptop will pick it up on next pull.
- **Cleanup** (`658328f`): untracked 9 `__pycache__/*.pyc` files that were committed before gitignore rules
- Next re-auth: on or before 2026-04-26 (Schwab refresh token 7-day TTL)

