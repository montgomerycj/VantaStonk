#!/usr/bin/env python3
"""Quick test of Schwab API connection."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()
from schwab import auth, client as sc

from src.config import resolve_schwab_token_path
from src.integrations.schwab_auth import SchwabAuthError, require_usable_token

APP_KEY = os.getenv("SCHWAB_APP_KEY")
APP_SECRET = os.getenv("SCHWAB_APP_SECRET")
TOKEN_PATH = resolve_schwab_token_path()


def main():
    try:
        require_usable_token(TOKEN_PATH)
    except SchwabAuthError:
        sys.exit(1)

    c = auth.client_from_token_file(
        token_path=TOKEN_PATH,
        api_key=APP_KEY,
        app_secret=APP_SECRET,
    )

    # Test quote
    r = c.get_quote("AAPL")
    data = r.json()
    q = data.get("AAPL", {}).get("quote", {})
    last = q.get("lastPrice", "?")
    vol = q.get("totalVolume", "?")
    print(f"AAPL: ${last}  |  Vol: {vol:,}" if isinstance(vol, int) else f"AAPL: ${last}  |  Vol: {vol}")

    # Test positions
    accts = c.get_account_numbers().json()
    account_hash = accts[0]["hashValue"]
    r = c.get_account(account_hash, fields=sc.Client.Account.Fields.POSITIONS)
    data = r.json()
    positions = data.get("securitiesAccount", {}).get("positions", [])
    print(f"\nPositions: {len(positions)} holdings")
    for pos in positions[:5]:
        sym = pos.get("instrument", {}).get("symbol", "?")
        qty = pos.get("longQuantity", 0)
        mv = pos.get("marketValue", 0)
        print(f"  {sym}: {qty} shares, ${mv:,.2f}")
    if len(positions) > 5:
        print(f"  ... and {len(positions) - 5} more")


if __name__ == "__main__":
    main()
