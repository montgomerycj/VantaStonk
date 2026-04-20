#!/usr/bin/env python3
"""Ad-hoc: dump all positions with today's % change + day P/L."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from schwab import auth, client as sc

APP_KEY = os.getenv("SCHWAB_APP_KEY")
APP_SECRET = os.getenv("SCHWAB_APP_SECRET")
TOKEN_PATH = os.getenv("SCHWAB_TOKEN_PATH", "data/schwab_token.json")

c = auth.client_from_token_file(token_path=TOKEN_PATH, api_key=APP_KEY, app_secret=APP_SECRET)

accts = c.get_account_numbers().json()
account_hash = accts[0]["hashValue"]
r = c.get_account(account_hash, fields=sc.Client.Account.Fields.POSITIONS)
positions = r.json().get("securitiesAccount", {}).get("positions", [])

rows = []
total_mv = 0.0
total_day_pl = 0.0
for pos in positions:
    inst = pos.get("instrument", {})
    sym = inst.get("symbol", "?")
    qty = pos.get("longQuantity", 0) - pos.get("shortQuantity", 0)
    mv = pos.get("marketValue", 0.0)
    day_pl = pos.get("currentDayProfitLoss", 0.0)
    day_pl_pct = pos.get("currentDayProfitLossPercentage", 0.0)
    avg_price = pos.get("averagePrice", 0.0)
    last_price = (mv / qty) if qty else 0.0
    pct_vs_cost = ((last_price - avg_price) / avg_price * 100) if avg_price else 0.0
    total_mv += mv
    total_day_pl += day_pl
    rows.append((sym, qty, last_price, mv, day_pl, day_pl_pct, avg_price, pct_vs_cost))

rows.sort(key=lambda r: abs(r[5]), reverse=True)

print(f"\n{'SYM':<10} {'QTY':>10} {'LAST':>10} {'MV':>12} {'DAY P/L':>11} {'DAY %':>8} {'AVG':>10} {'UNRLZ %':>9}")
print("-" * 90)
for sym, qty, last, mv, dpl, dpl_pct, avg, unrlz in rows:
    print(f"{sym:<10} {qty:>10.0f} {last:>10.2f} {mv:>12,.2f} {dpl:>+11,.2f} {dpl_pct:>+7.2f}% {avg:>10.2f} {unrlz:>+8.2f}%")
print("-" * 90)
print(f"{'TOTAL':<10} {'':<10} {'':<10} {total_mv:>12,.2f} {total_day_pl:>+11,.2f} {'':>8} {'':>10} {'':>9}")
