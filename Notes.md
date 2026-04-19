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

### 2026-04-19

- Project bootstrap day: went from empty repo to live Schwab-connected trading intelligence system
- PLTR scored F (0.242) due to chasing penalty — system working as designed
- Market observation: entire watchlist ran +5-25% this week, almost nothing actionable = sit on hands

