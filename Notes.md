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

- <!-- session log: fill in accomplishments -->

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

