#!/usr/bin/env python3
"""
VantaStonk — Schwab OAuth Login

Run this in your terminal to authenticate with Schwab.
Copy/paste the URL into your browser, log in, then paste back the redirect URL.

Usage:
    python scripts/schwab_login.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from schwab import auth

APP_KEY = os.getenv("SCHWAB_APP_KEY", "")
APP_SECRET = os.getenv("SCHWAB_APP_SECRET", "")
CALLBACK_URL = os.getenv("SCHWAB_CALLBACK_URL", "https://127.0.0.1:8182/")
TOKEN_PATH = os.getenv("SCHWAB_TOKEN_PATH", "data/schwab_token.json")

if not APP_KEY or not APP_SECRET:
    print("ERROR: Set SCHWAB_APP_KEY and SCHWAB_APP_SECRET in .env")
    sys.exit(1)

Path(TOKEN_PATH).parent.mkdir(parents=True, exist_ok=True)

print("=" * 60)
print("  VantaStonk — Schwab Login")
print("=" * 60)
print()

try:
    c = auth.client_from_manual_flow(
        api_key=APP_KEY,
        app_secret=APP_SECRET,
        callback_url=CALLBACK_URL,
        token_path=TOKEN_PATH,
    )
    print("\nSuccess! Token saved to", TOKEN_PATH)
    print("You can now use score_ticker.py and morning_scan.py")
except Exception as e:
    print(f"\nLogin failed: {e}")
    sys.exit(1)
