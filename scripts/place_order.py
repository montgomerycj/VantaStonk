#!/usr/bin/env python3
"""
VantaStonk — Place one Schwab equity order.

Dry-run is the default. Nothing is sent unless --i-mean-it is set.
Token path is always repo-rooted via resolve_schwab_token_path()
(C:\\Users\\cj\\projects\\Vantastonk\\data\\schwab_token.json on the laptop).

Usage:
    python scripts/place_order.py --ticker AAPL --side buy --quantity 1 --order-type market
    python scripts/place_order.py --ticker AAPL --side buy --quantity 1 --order-type limit --price 150
    python scripts/place_order.py --ticker AAPL --side sell --quantity 1 --order-type market --i-mean-it
"""

import argparse
import json
import sys
from pathlib import Path

# Pin imports to this repo, never leftover cwd (same idea as schwab_login.py).
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv
load_dotenv()

from src.config import resolve_schwab_token_path
from src.integrations.schwab_auth import SchwabAuthError
from src.integrations.schwab_client import SchwabClient, build_equity_order

TOKEN_PATH = resolve_schwab_token_path()


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Place one Schwab equity order. Dry-run unless --i-mean-it.",
    )
    parser.add_argument("--ticker", required=True, help="Common-stock ticker (equities only)")
    parser.add_argument("--side", required=True, choices=["buy", "sell"])
    parser.add_argument("--quantity", required=True, type=int, help="Whole shares, positive integer")
    parser.add_argument("--order-type", required=True, choices=["market", "limit"])
    parser.add_argument(
        "--price",
        type=float,
        default=None,
        help="Limit price (required for --order-type limit)",
    )
    parser.add_argument(
        "--tif",
        default="DAY",
        choices=["DAY", "GTC"],
        help="Time-in-force. Default DAY. GTC only if you pass this flag.",
    )
    parser.add_argument(
        "--i-mean-it",
        dest="i_mean_it",
        action="store_true",
        help="Actually place the order. Without this flag, print the payload and exit.",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        spec = build_equity_order(
            ticker=args.ticker,
            side=args.side,
            quantity=args.quantity,
            order_type=args.order_type,
            price=args.price,
            tif=args.tif,
        )
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 2

    if not args.i_mean_it:
        print("DRY-RUN (not sent). Pass --i-mean-it to place this order.")
        print()
        print(json.dumps(spec, indent=2))
        return 0

    client = SchwabClient(token_path=TOKEN_PATH)
    if not client.connect():
        return 1

    try:
        result = client.place_order(
            ticker=args.ticker,
            side=args.side,
            quantity=args.quantity,
            order_type=args.order_type,
            price=args.price,
            tif=args.tif,
        )
    except SchwabAuthError as exc:
        print(exc, flush=True)
        return 1
    except Exception as exc:
        print(f"ERROR: order failed ({type(exc).__name__})", flush=True)
        return 1

    order_id = result.order_id or "unknown"
    print(f"order_id={order_id} status={result.status}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
