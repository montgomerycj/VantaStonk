#!/usr/bin/env python3
"""
VantaStonk — Schwab OAuth Login

Prints a pasteable authorization URL first, writes it to
data/schwab_auth_url.txt, then starts schwab-py's callback flow.
Browser auto-open is a convenience only — do not rely on it.

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

from src.config import resolve_schwab_token_path
from src.integrations.schwab_auth import AUTH_URL_PATH, prepare_login_flow


def main():
    APP_KEY = os.getenv("SCHWAB_APP_KEY", "")
    APP_SECRET = os.getenv("SCHWAB_APP_SECRET", "")
    CALLBACK_URL = os.getenv("SCHWAB_CALLBACK_URL", "https://127.0.0.1:8182/")
    TOKEN_PATH = resolve_schwab_token_path()

    if not APP_KEY or not APP_SECRET:
        print("ERROR: Set SCHWAB_APP_KEY and SCHWAB_APP_SECRET in .env")
        sys.exit(1)

    Path(TOKEN_PATH).parent.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("  VantaStonk — Schwab Login")
    print("=" * 60)
    print()
    print("A pasteable authorization URL will be printed next.")
    print("Log in, then if you see a certificate warning:")
    print("  -> Click 'Advanced' -> 'Proceed'")
    print()

    # get_auth_context (schwab-py 1.4+) builds the authorize URL + OAuth
    # state. We print/save that URL BEFORE client_from_login_flow tries
    # webbrowser, then pin the same context so state matches.
    prepare_login_flow(auth, APP_KEY, CALLBACK_URL, AUTH_URL_PATH)

    try:
        auth.client_from_login_flow(
            api_key=APP_KEY,
            app_secret=APP_SECRET,
            callback_url=CALLBACK_URL,
            token_path=TOKEN_PATH,
            callback_timeout=300,
            interactive=False,
        )
        print("\nSuccess! Token saved to", TOKEN_PATH)
        print("You can now use score_ticker.py and morning_scan.py")
    except Exception as e:
        print(f"\nLogin failed: {e}")
        print(f"If the browser never opened, paste the URL from {AUTH_URL_PATH}")
        sys.exit(1)


if __name__ == "__main__":
    # Required on Windows: schwab-py uses multiprocessing for the OAuth
    # redirect server, and spawn start method re-imports this module.
    import multiprocessing
    multiprocessing.freeze_support()
    main()
