# Vantastonk (95v2)

Short-term equities desk. Early names before the crowd. Horizon: intraday to ~3 days.

## Slate inherit (session close)
On session close, or when a decision lands that is not a commit, append one dated ship/decision/kill line to Dropbox `claude-memory/Vantastonk/cross-agent-log.md`. Friday = Repeat offenses score. Do not ask CJ for Cursor recaps. Do not edit MEMORY.md for routine closes.

## Durable writes (house rule)
On every CJ correction / kill / park: same-day `feedback_*.md` (or MEMORY if foundational) under Dropbox `claude-memory/Vantastonk/` AND one cross-agent-log line. Chat-only fixes do not count. Before deep work: load MEMORY + feedback_*.md + last 5 log lines from Dropbox first.

## Core rules
1. No chasing — reject >5% / 5 sessions or >15% intraday unless unpriced catalyst.
2. Buy the rumor — pre-catalyst / under-recognized over post-news winners.
3. Prompt Pulse — what AI tools recommend in the next 6–48 hours.
4. Early > confirmed.
5. CJ clicks; no live Schwab orders / outbound without explicit approval.

## Week ops (locked 2026-09-11)
- Goal +5% on week-book frame. Hard Fri flat unless CJ extends.
- Up to 5–6 live clips; ≤2 on the same fuse. Lotto $750–1k; core $1–2k.
- Do not result. Week-book P/L separate from owned pads.
- Book sits (robotics sleeve / unless CJ opens): leave BOTZ/SYM/TER/OUST/PRCT.

## Schwab SoT
- Live token on Vanta box secrets (absolute path). Optional desk/laptop sync.
- Re-auth: box handoff or laptop authorize URL → paste 127.0.0.1:8182 redirect. Never print secrets.

## Modules
Glance (actionable) / ShadowList (pre-trigger) / Shorties (fade).

## Scoring (ref)
TOTAL = catalyst×0.28 + prompt_pulse×0.24 + freshness×0.18 + peer×0.12 + volume×0.08 + macro×0.10
Penalties: chasing(-0.25), stale_narrative(-0.15), negative_peer(-0.10)

## Memory SoT
Dropbox `claude-memory/Vantastonk/` (MEMORY.md, feedback_*, cross-agent-log). Missing GitHub ≠ absent.
