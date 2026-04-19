"""
VantaStonk — Schwab API Client

Wraps schwab-py for:
- OAuth2 authentication + token management
- Account positions
- Price quotes (single + batch)
- Price history (5-day lookback for chasing filter)
- Recent orders (for trade journal)
"""

import os
import json
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from schwab import auth, client as schwab_client

load_dotenv()

# --- Config from .env ---

APP_KEY = os.getenv("SCHWAB_APP_KEY", "")
APP_SECRET = os.getenv("SCHWAB_APP_SECRET", "")
CALLBACK_URL = os.getenv("SCHWAB_CALLBACK_URL", "https://127.0.0.1:8182/")
TOKEN_PATH = os.getenv("SCHWAB_TOKEN_PATH", "data/schwab_token.json")


@dataclass
class Position:
    """A single account position."""
    ticker: str
    quantity: float
    avg_price: float
    market_value: float
    current_price: float
    day_pnl: float
    total_pnl: float
    total_pnl_pct: float


@dataclass
class Quote:
    """Price quote for a single ticker."""
    ticker: str
    last_price: float
    open_price: float
    high_price: float
    low_price: float
    close_price: float  # previous close
    volume: int
    bid_price: float
    ask_price: float
    timestamp: Optional[str] = None


@dataclass
class PriceBar:
    """Single OHLCV bar."""
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class SchwabClient:
    """VantaStonk's interface to the Schwab API."""

    def __init__(self):
        self._client = None
        self._account_hash = None

    def connect(self) -> bool:
        """
        Establish authenticated connection to Schwab API.

        First run: opens browser for OAuth login.
        Subsequent runs: loads token from file, auto-refreshes.
        """
        if not APP_KEY or not APP_SECRET:
            print("ERROR: Set SCHWAB_APP_KEY and SCHWAB_APP_SECRET in .env")
            return False

        token_path = Path(TOKEN_PATH)
        token_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            self._client = auth.easy_client(
                api_key=APP_KEY,
                app_secret=APP_SECRET,
                callback_url=CALLBACK_URL,
                token_path=str(token_path),
            )
            print("Schwab API connected.")
            return True
        except Exception as e:
            print(f"Schwab connection failed: {e}")
            return False

    def _ensure_account_hash(self):
        """Fetch and cache the account hash (required for all account operations)."""
        if self._account_hash:
            return
        resp = self._client.get_account_numbers()
        resp.raise_for_status()
        accounts = resp.json()
        if not accounts:
            raise RuntimeError("No accounts found on this Schwab login")
        # Use the first account
        self._account_hash = accounts[0]["hashValue"]

    # --- Positions ---

    def get_positions(self) -> list[Position]:
        """Get all current positions."""
        self._ensure_account_hash()
        resp = self._client.get_account(
            self._account_hash,
            fields=schwab_client.Client.Account.Fields.POSITIONS,
        )
        resp.raise_for_status()
        data = resp.json()

        positions = []
        for pos in data.get("securitiesAccount", {}).get("positions", []):
            instrument = pos.get("instrument", {})
            ticker = instrument.get("symbol", "???")

            quantity = pos.get("longQuantity", 0) - pos.get("shortQuantity", 0)
            avg_price = pos.get("averagePrice", 0)
            market_value = pos.get("marketValue", 0)
            current_price = pos.get("currentDayProfitLossPercentage", 0)  # fallback
            day_pnl = pos.get("currentDayProfitLoss", 0)

            # Calculate current price from market value and quantity
            if quantity != 0:
                current_price = market_value / quantity

            total_pnl = market_value - (avg_price * quantity)
            total_pnl_pct = (total_pnl / (avg_price * quantity) * 100) if avg_price * quantity != 0 else 0

            positions.append(Position(
                ticker=ticker,
                quantity=quantity,
                avg_price=round(avg_price, 2),
                market_value=round(market_value, 2),
                current_price=round(current_price, 2),
                day_pnl=round(day_pnl, 2),
                total_pnl=round(total_pnl, 2),
                total_pnl_pct=round(total_pnl_pct, 2),
            ))

        return positions

    # --- Quotes ---

    def get_quote(self, ticker: str) -> Optional[Quote]:
        """Get a single price quote."""
        resp = self._client.get_quote(ticker)
        resp.raise_for_status()
        data = resp.json()

        quote_data = data.get(ticker, {}).get("quote", {})
        if not quote_data:
            return None

        return Quote(
            ticker=ticker,
            last_price=quote_data.get("lastPrice", 0),
            open_price=quote_data.get("openPrice", 0),
            high_price=quote_data.get("highPrice", 0),
            low_price=quote_data.get("lowPrice", 0),
            close_price=quote_data.get("closePrice", 0),
            volume=quote_data.get("totalVolume", 0),
            bid_price=quote_data.get("bidPrice", 0),
            ask_price=quote_data.get("askPrice", 0),
        )

    def get_quotes(self, tickers: list[str]) -> dict[str, Quote]:
        """Get batch quotes for multiple tickers."""
        resp = self._client.get_quotes(tickers)
        resp.raise_for_status()
        data = resp.json()

        quotes = {}
        for ticker in tickers:
            quote_data = data.get(ticker, {}).get("quote", {})
            if quote_data:
                quotes[ticker] = Quote(
                    ticker=ticker,
                    last_price=quote_data.get("lastPrice", 0),
                    open_price=quote_data.get("openPrice", 0),
                    high_price=quote_data.get("highPrice", 0),
                    low_price=quote_data.get("lowPrice", 0),
                    close_price=quote_data.get("closePrice", 0),
                    volume=quote_data.get("totalVolume", 0),
                    bid_price=quote_data.get("bidPrice", 0),
                    ask_price=quote_data.get("askPrice", 0),
                )
        return quotes

    # --- Price History ---

    def get_price_history(
        self,
        ticker: str,
        days: int = 10,
        frequency: str = "daily",
    ) -> list[PriceBar]:
        """
        Get OHLCV price history.

        Args:
            ticker: Stock symbol
            days: Number of days of history (default 10 for 5-day trading lookback)
            frequency: "daily" or "minute"
        """
        if frequency == "daily":
            resp = self._client.get_price_history_every_day(
                ticker,
                period_type=schwab_client.Client.PriceHistory.PeriodType.DAY,
                period=schwab_client.Client.PriceHistory.Period.TEN_DAYS,
                need_previous_close=True,
            )
        else:
            resp = self._client.get_price_history_every_minute(
                ticker,
                period_type=schwab_client.Client.PriceHistory.PeriodType.DAY,
                period=schwab_client.Client.PriceHistory.Period.ONE_DAY,
            )

        resp.raise_for_status()
        data = resp.json()

        bars = []
        for candle in data.get("candles", []):
            # Schwab returns epoch milliseconds
            dt = datetime.fromtimestamp(candle["datetime"] / 1000)
            bars.append(PriceBar(
                date=dt.strftime("%Y-%m-%d"),
                open=candle.get("open", 0),
                high=candle.get("high", 0),
                low=candle.get("low", 0),
                close=candle.get("close", 0),
                volume=candle.get("volume", 0),
            ))

        return bars

    def get_5day_prices(self, ticker: str) -> tuple[Optional[float], Optional[float]]:
        """
        Get current price and price from 5 trading days ago.

        Returns (current_price, price_5d_ago) for the chasing filter.
        """
        bars = self.get_price_history(ticker, days=10, frequency="daily")
        if not bars:
            return None, None

        current_price = bars[-1].close
        # 5 trading days back (or as far back as we have)
        idx = max(0, len(bars) - 6)
        price_5d_ago = bars[idx].close

        return current_price, price_5d_ago

    # --- Orders ---

    def get_recent_orders(self, days: int = 7) -> list[dict]:
        """Get recent orders for trade journal logging."""
        self._ensure_account_hash()
        from_dt = datetime.now() - timedelta(days=days)
        to_dt = datetime.now()

        resp = self._client.get_orders_for_account(
            self._account_hash,
            from_entered_datetime=from_dt,
            to_entered_datetime=to_dt,
        )
        resp.raise_for_status()
        return resp.json()

    # --- Account Summary ---

    def get_account_summary(self) -> dict:
        """Get account balances and summary info."""
        self._ensure_account_hash()
        resp = self._client.get_account(self._account_hash)
        resp.raise_for_status()
        data = resp.json()

        balances = data.get("securitiesAccount", {}).get("currentBalances", {})
        return {
            "account_value": balances.get("liquidationValue", 0),
            "cash_available": balances.get("cashBalance", 0),
            "buying_power": balances.get("buyingPower", 0),
            "day_pnl": balances.get("currentDayProfitLoss", 0) if "currentDayProfitLoss" in balances else None,
        }
