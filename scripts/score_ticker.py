#!/usr/bin/env python3
"""
VantaStonk — Quick Score CLI

Score any ticker against the 95v2 model.

Usage:
    python scripts/score_ticker.py PLTR
    python scripts/score_ticker.py AAPL MSFT NVDA
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.integrations.schwab_client import SchwabClient
from src.core.scoring import ScoreInputs, score
from src.core.filters import PriceContext, check_chasing
from src.core.prompt_pulse import estimate_discoverability
from src.db import get_connection, init_db, save_price_snapshot, save_score, upsert_ticker


def score_ticker(client: SchwabClient, ticker: str) -> dict:
    """Score a single ticker using live Schwab data."""
    ticker = ticker.upper()

    # Get current quote
    quote = client.get_quote(ticker)
    if not quote:
        print(f"  Could not get quote for {ticker}")
        return None

    # Get 5-day price for chasing filter
    current_price, price_5d_ago = client.get_5day_prices(ticker)
    if current_price is None:
        current_price = quote.last_price
        price_5d_ago = quote.close_price  # fallback to previous close

    # Run chasing filter
    price_ctx = PriceContext(
        ticker=ticker,
        price_current=current_price,
        price_5d_ago=price_5d_ago,
        price_open_today=quote.open_price,
    )
    filter_result = check_chasing(price_ctx)

    # Estimate discoverability (basic heuristic without full company data)
    discoverability = estimate_discoverability(
        ticker=ticker,
        company_name=ticker,  # placeholder
        market_cap_millions=0,  # unknown without additional data
        sector="unknown",
    )

    # Build score inputs
    # Note: catalyst, freshness, peer, macro are set to neutral (0.5) as defaults.
    # These get refined by the AI research partner in Phase 2.
    inputs = ScoreInputs(
        ticker=ticker,
        catalyst=0.5,       # neutral default — needs AI/manual input
        prompt_pulse=discoverability,
        freshness=0.5,      # neutral default
        peer=0.5,           # neutral default
        volume=min(1.0, quote.volume / 10_000_000) if quote.volume else 0.3,  # normalize volume
        macro=0.5,          # neutral default
        is_chasing=filter_result.is_chasing,
    )

    result = score(inputs)

    return {
        "ticker": ticker,
        "price": current_price,
        "open": quote.open_price,
        "price_5d_ago": price_5d_ago,
        "volume": quote.volume,
        "bid": quote.bid_price,
        "ask": quote.ask_price,
        "filter": filter_result,
        "score": result,
    }


def print_result(data: dict):
    """Pretty-print a score result."""
    if not data:
        return

    r = data["score"]
    f = data["filter"]

    print(f"\n{'='*50}")
    print(f"  {data['ticker']}  -  ${data['price']:.2f}  |  Grade: {r.grade}  |  Score: {r.total:.3f}")
    print(f"{'='*50}")
    print(f"  Open: ${data['open']:.2f}  |  5d ago: ${data['price_5d_ago']:.2f}  |  Vol: {data['volume']:,}")
    print(f"  Bid: ${data['bid']:.2f}  |  Ask: ${data['ask']:.2f}")
    print()

    # Chasing filter
    if f.is_chasing:
        print(f"  !! CHASING DETECTED !!")
        for reason in f.reasons:
            print(f"     {reason}")
    else:
        print(f"  Filter: PASSED (not chasing)")

    # Score breakdown
    print(f"\n  Score Breakdown:")
    for factor, value in r.breakdown.items():
        bar = "#" * int(value * 40)
        print(f"    {factor:>14}: {value:.4f}  {bar}")

    print(f"    {'raw_total':>14}: {r.raw_total:.4f}")

    if r.penalties_applied:
        print(f"\n  Penalties:")
        for p in r.penalties_applied:
            print(f"    - {p}")

    print(f"\n  Final: {r.total:.4f} ({r.grade})")
    print()


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/score_ticker.py TICKER [TICKER2 ...]")
        sys.exit(1)

    tickers = [t.upper() for t in sys.argv[1:]]

    # Connect to Schwab
    client = SchwabClient()
    if not client.connect():
        print("Failed to connect to Schwab API. Check your .env credentials.")
        sys.exit(1)

    # Initialize DB
    init_db()
    conn = get_connection()

    for ticker in tickers:
        print(f"\nScoring {ticker}...")
        data = score_ticker(client, ticker)
        if data:
            print_result(data)

            # Save to database
            upsert_ticker(conn, ticker)
            save_price_snapshot(conn, ticker, data["price"], data["volume"])
            save_score(conn, ticker, data["score"])

    conn.close()


if __name__ == "__main__":
    main()
