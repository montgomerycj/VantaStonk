#!/usr/bin/env python3
"""
VantaStonk — Morning Scan

Daily pre-market routine:
1. Load watchlist
2. Pull prices from Schwab API
3. Run filters + scoring
4. Split into Glance / ShadowList / Shorties
5. Output markdown
6. Log everything to database

Usage:
    python scripts/morning_scan.py
    python scripts/morning_scan.py --watchlist data/watchlist.json
"""

import sys
import os
import json
import argparse
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.integrations.schwab_client import SchwabClient
from src.core.scoring import ScoreInputs, rank
from src.core.filters import PriceContext, filter_universe
from src.core.prompt_pulse import estimate_discoverability
from src.workflows.run_glance import build_glance, format_glance_markdown
from src.workflows.run_shorties import ShortCandidate, is_overextended, build_shorties, format_shorties_markdown
from src.db import get_connection, init_db, save_price_snapshot, save_score, upsert_ticker, save_recommendation


DEFAULT_WATCHLIST = "data/watchlist.json"

# Default watchlist if none exists yet
STARTER_WATCHLIST = {
    "tickers": [
        "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL",
        "META", "TSLA", "AMD", "PLTR", "SOFI",
        "MARA", "RIOT", "COIN", "SQ", "SHOP",
        "NET", "CRWD", "DDOG", "SNOW", "RKLB",
    ],
    "themes": {
        "ai_infrastructure": ["NVDA", "AMD", "PLTR"],
        "fintech": ["SOFI", "SQ", "COIN"],
        "crypto_adjacent": ["MARA", "RIOT", "COIN"],
        "cybersecurity": ["CRWD", "NET"],
        "space_economy": ["RKLB"],
    },
}


def load_watchlist(path: str) -> dict:
    """Load watchlist from JSON. Create starter if none exists."""
    p = Path(path)
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(STARTER_WATCHLIST, indent=2))
        print(f"Created starter watchlist at {path}")
    return json.loads(p.read_text())


def run_morning_scan(client: SchwabClient, watchlist: dict) -> str:
    """Run the full morning scan pipeline. Returns markdown output."""
    tickers = watchlist["tickers"]
    print(f"Scanning {len(tickers)} tickers...")

    # Initialize DB
    init_db()
    conn = get_connection()

    # 1. Pull batch quotes
    print("Pulling quotes...")
    quotes = client.get_quotes(tickers)
    print(f"  Got quotes for {len(quotes)}/{len(tickers)} tickers")

    # 2. Build PriceContexts for filtering
    price_contexts = []
    for ticker in tickers:
        quote = quotes.get(ticker)
        if not quote:
            print(f"  Skipping {ticker} — no quote data")
            continue

        # Get 5-day price
        current_price, price_5d_ago = client.get_5day_prices(ticker)
        if current_price is None:
            current_price = quote.last_price
            price_5d_ago = quote.close_price

        price_contexts.append(PriceContext(
            ticker=ticker,
            price_current=current_price,
            price_5d_ago=price_5d_ago,
            price_open_today=quote.open_price,
        ))

        # Save snapshot
        upsert_ticker(conn, ticker)
        save_price_snapshot(conn, ticker, current_price, quote.volume)

    # 3. Run chasing filters
    print("Running filters...")
    passed, rejected = filter_universe(price_contexts)
    print(f"  Passed: {len(passed)}, Rejected (chasing): {len(rejected)}")

    # 4. Score passed candidates
    print("Scoring candidates...")
    score_inputs = []
    for f_result in passed:
        ticker = f_result.ticker
        quote = quotes[ticker]
        discoverability = estimate_discoverability(
            ticker=ticker,
            company_name=ticker,
            market_cap_millions=0,
            sector="unknown",
        )

        score_inputs.append(ScoreInputs(
            ticker=ticker,
            catalyst=0.5,
            prompt_pulse=discoverability,
            freshness=0.5,
            peer=0.5,
            volume=min(1.0, quote.volume / 10_000_000) if quote.volume else 0.3,
            macro=0.5,
            is_chasing=False,
        ))

    ranked = rank(score_inputs)
    for r in ranked:
        save_score(conn, r.ticker, r)

    # 5. Build Glance picks (top scorers get momentum slots)
    picks_meta = {}
    for i, r in enumerate(ranked[:4]):
        quote = quotes[r.ticker]
        ctx = next(p for p in price_contexts if p.ticker == r.ticker)
        move_5d = ((ctx.price_current - ctx.price_5d_ago) / ctx.price_5d_ago * 100) if ctx.price_5d_ago else 0

        if i < 2:
            category = "momentum"
        elif i == 2:
            category = "macro_tilt"
        else:
            category = "lotto"

        picks_meta[r.ticker] = {
            "category": category,
            "setup": f"Score {r.total:.2f} ({r.grade}) — 5d move {move_5d:+.1f}%",
            "why_now": f"Volume {quote.volume:,} | Prompt Pulse {r.breakdown.get('prompt_pulse', 0):.2f}",
            "catalyst": "Evaluate manually — AI research phase needed",
            "not_priced_in": "Requires manual assessment",
            "risk": f"{'High' if abs(move_5d) > 3 else 'Moderate' if abs(move_5d) > 1 else 'Low'} volatility",
        }

    glance_output = build_glance(ranked, picks_meta)
    glance_output.rejected = rejected
    glance_md = format_glance_markdown(glance_output)

    # 6. Build Shorties from rejected (chasing) candidates
    short_candidates = []
    for f_result in rejected:
        ctx = next(p for p in price_contexts if p.ticker == f_result.ticker)
        over, move_pct = is_overextended(ctx.price_current, ctx.price_5d_ago, threshold_pct=5.0)
        if over:
            short_candidates.append(ShortCandidate(
                ticker=f_result.ticker,
                why_short=f_result.reasons[0] if f_result.reasons else "Overextended",
                catalyst="Chasing filter triggered",
                risk="Could continue higher on momentum/squeeze",
                overextension_pct=move_pct,
                category="fade",
            ))

    shorties_output = build_shorties(short_candidates)
    shorties_md = format_shorties_markdown(shorties_output)

    # 7. Save recommendations to DB
    for pick in glance_output.picks:
        save_recommendation(
            conn, pick.ticker, "glance", pick.category, pick.setup,
            pick.why_now, pick.catalyst, pick.not_priced_in, pick.risk,
            pick.score_result.total if pick.score_result else None,
        )
    for sc in short_candidates:
        save_recommendation(
            conn, sc.ticker, "shorties", sc.category, sc.why_short,
            catalyst=sc.catalyst, risk=sc.risk, score_total=sc.overextension_pct,
        )

    conn.close()

    # 8. Combine output
    now = datetime.now().strftime("%Y-%m-%d %H:%M PT")
    full_output = f"# VantaStonk Morning Scan — {now}\n\n"
    full_output += glance_md + "\n\n---\n\n" + shorties_md

    # Add rejected summary
    if rejected:
        full_output += "\n\n---\n\n## Rejected (Chasing)\n"
        for r in rejected:
            full_output += f"- **{r.ticker}**: {', '.join(r.reasons)}\n"

    # Add full rankings
    full_output += "\n\n---\n\n## Full Rankings\n"
    full_output += "| Rank | Ticker | Score | Grade |\n"
    full_output += "|------|--------|-------|-------|\n"
    for i, r in enumerate(ranked, 1):
        full_output += f"| {i} | {r.ticker} | {r.total:.3f} | {r.grade} |\n"

    return full_output


def main():
    parser = argparse.ArgumentParser(description="VantaStonk Morning Scan")
    parser.add_argument("--watchlist", default=DEFAULT_WATCHLIST, help="Path to watchlist JSON")
    args = parser.parse_args()

    # Load watchlist
    watchlist = load_watchlist(args.watchlist)

    # Connect to Schwab
    client = SchwabClient()
    if not client.connect():
        print("Failed to connect to Schwab API. Check your .env credentials.")
        sys.exit(1)

    # Run scan
    output = run_morning_scan(client, watchlist)

    # Save output
    date_str = datetime.now().strftime("%Y-%m-%d")
    output_path = f"data/glance_{date_str}.md"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(output)
    print(f"\nOutput saved to {output_path}")

    # Print to console
    print("\n" + output)


if __name__ == "__main__":
    main()
