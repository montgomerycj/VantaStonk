"""
VantaStonk — Schwab API Client

Wraps schwab-py for:
- OAuth2 authentication + token management
- Account positions
- Price quotes (single + batch)
- Price history (5-day lookback for chasing filter)
- Recent orders (for trade journal)
- Place one equity order (common stock; dry-run lives in the CLI)
"""

import os
import re
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv
from schwab import auth, client as schwab_client
from schwab.orders.common import Duration
from schwab.orders.equities import (
    equity_buy_limit,
    equity_buy_market,
    equity_sell_limit,
    equity_sell_market,
)

from src.config import resolve_schwab_token_path
from src.integrations.schwab_auth import (
    LOGIN_COMMAND,
    SchwabAuthError,
    inspect_token,
    is_refresh_rejected,
    refresh_rejected_error,
)

load_dotenv()

# --- Config from .env ---

APP_KEY = os.getenv("SCHWAB_APP_KEY", "")
APP_SECRET = os.getenv("SCHWAB_APP_SECRET", "")
CALLBACK_URL = os.getenv("SCHWAB_CALLBACK_URL", "https://127.0.0.1:8182/")
TOKEN_PATH = resolve_schwab_token_path()


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


@dataclass
class PlacedOrder:
    """Result of a submitted equity order. No secrets, no account hash."""
    order_id: Optional[str]
    status: str


# Common stock only: 1–6 letters, optional class suffix (.B / -B / /B).
_EQUITY_TICKER_RE = re.compile(r"^[A-Z]{1,6}([./-][A-Z])?$")
# OCC / OSI option root: underlying + YYMMDD + C|P + 8-digit strike.
_OCC_OPTION_RE = re.compile(r"^[A-Z]{1,6}\d{6}[CP]\d{8}$")
_ORDER_ID_IN_LOCATION_RE = re.compile(
    r"/accounts/[^/]+/orders/(\d+)\s*$",
    re.IGNORECASE,
)

_SIDES = frozenset({"buy", "sell"})
_ORDER_TYPES = frozenset({"market", "limit"})
_TIF_ALIASES = {
    "DAY": Duration.DAY,
    "GTC": Duration.GOOD_TILL_CANCEL,
    "GOOD_TILL_CANCEL": Duration.GOOD_TILL_CANCEL,
}


def looks_like_option_symbol(ticker: str) -> bool:
    """True for OCC/OSI strings and other non-equity option tickets."""
    raw = (ticker or "").strip().upper()
    if not raw:
        return False
    compact = re.sub(r"\s+", "", raw)
    if _OCC_OPTION_RE.match(compact):
        return True
    if any(ch.isspace() for ch in raw):
        return True
    return False


def normalize_equity_ticker(ticker: str) -> str:
    """Uppercase a common-stock ticker. Reject options / OCC strings."""
    raw = (ticker or "").strip().upper()
    if not raw:
        raise ValueError("ticker is required")
    if looks_like_option_symbol(raw):
        raise ValueError(f"Options symbols are not supported (v1 equities only): {raw}")
    if not _EQUITY_TICKER_RE.match(raw):
        raise ValueError(f"Not a common-stock ticker: {raw}")
    return raw


def format_limit_price(price) -> str:
    """Schwab-py prefers price strings. Sub-dollar uses 4 dp; else 2 dp."""
    try:
        value = float(price)
    except (TypeError, ValueError) as exc:
        raise ValueError("price must be a positive number") from exc
    if value <= 0:
        raise ValueError("price must be positive")
    if abs(value) < 1:
        return f"{value:.4f}"
    return f"{value:.2f}"


def build_equity_order(
    ticker: str,
    side: str,
    quantity: int,
    order_type: str,
    price=None,
    tif: str = "DAY",
) -> dict:
    """
    Build a schwab-py equity order spec (dict). Does not call the API.

    Default time-in-force is DAY. GTC requires an explicit tif of GTC
    (or GOOD_TILL_CANCEL). Equities / common stock only.
    """
    symbol = normalize_equity_ticker(ticker)
    side_key = (side or "").strip().lower()
    type_key = (order_type or "").strip().lower()
    tif_key = (tif or "DAY").strip().upper()

    if side_key not in _SIDES:
        raise ValueError("side must be buy or sell")
    if type_key not in _ORDER_TYPES:
        raise ValueError("order type must be market or limit")
    if tif_key not in _TIF_ALIASES:
        raise ValueError("tif must be DAY or GTC")

    try:
        qty = int(quantity)
    except (TypeError, ValueError) as exc:
        raise ValueError("quantity must be a positive integer") from exc
    if qty <= 0 or qty != quantity:
        raise ValueError("quantity must be a positive integer")

    if type_key == "limit":
        if price is None:
            raise ValueError("limit orders require a price")
        formatted = format_limit_price(price)
        builder = (
            equity_buy_limit(symbol, qty, formatted)
            if side_key == "buy"
            else equity_sell_limit(symbol, qty, formatted)
        )
    else:
        if price is not None:
            raise ValueError("market orders do not take a price")
        builder = (
            equity_buy_market(symbol, qty)
            if side_key == "buy"
            else equity_sell_market(symbol, qty)
        )

    duration = _TIF_ALIASES[tif_key]
    if duration is not Duration.DAY:
        builder = builder.set_duration(duration)

    return builder.build()


def extract_placed_order_id(response) -> Optional[str]:
    """
    Pull the order id from a place_order Location header.

    Never returns or embeds the Location URL (it contains the account hash).
    """
    headers = getattr(response, "headers", None) or {}
    location = headers.get("Location") or headers.get("location")
    if not location:
        return None
    match = _ORDER_ID_IN_LOCATION_RE.search(str(location))
    if match:
        return match.group(1)
    tail = str(location).rstrip("/").rsplit("/", 1)[-1]
    if tail.isdigit():
        return tail
    return None


class SchwabClient:
    """VantaStonk's interface to the Schwab API."""

    def __init__(self, token_path: Optional[str] = None):
        self._client = None
        self._account_hash = None
        self.token_path = token_path or TOKEN_PATH

    def connect(self) -> bool:
        """
        Establish authenticated connection to Schwab API.

        Loads token from file (created by scripts/schwab_login.py).
        Access-token auto-refresh (30 min) stays with schwab-py.
        Missing or 7-day-dead refresh tokens return False with a
        login command — they do not surface as a generic OAuth trace.
        """
        if not APP_KEY or not APP_SECRET:
            print("ERROR: Set SCHWAB_APP_KEY and SCHWAB_APP_SECRET in .env")
            return False

        age = inspect_token(self.token_path)
        print(age.message, flush=True)
        if age.status in ("missing", "dead"):
            return False

        try:
            self._client = auth.client_from_token_file(
                token_path=str(self.token_path),
                api_key=APP_KEY,
                app_secret=APP_SECRET,
            )
            print("Schwab API connected.")
            return True
        except SchwabAuthError as e:
            print(e, flush=True)
            return False
        except Exception as e:
            if is_refresh_rejected(e):
                err = refresh_rejected_error(e)
                print(err, flush=True)
                return False
            print(f"Schwab connection failed: {e}")
            print(f"If the token is stale, run {LOGIN_COMMAND}")
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
        start_dt = datetime.now() - timedelta(days=days)

        if frequency == "daily":
            resp = self._client.get_price_history_every_day(
                ticker,
                start_datetime=start_dt,
                need_previous_close=True,
            )
        else:
            resp = self._client.get_price_history_every_minute(
                ticker,
                start_datetime=start_dt,
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

    def place_order(
        self,
        ticker: str,
        side: str,
        quantity: int,
        order_type: str,
        price=None,
        tif: str = "DAY",
    ) -> PlacedOrder:
        """
        Place one equity order on the first account hash (same as get_positions).

        Uses schwab-py ``Client.place_order``. Does not print tokens, app
        credentials, or the account hash. Raises SchwabAuthError with the
        login command when the refresh token is rejected.
        """
        if self._client is None:
            raise RuntimeError("Not connected. Call connect() first.")

        spec = build_equity_order(
            ticker=ticker,
            side=side,
            quantity=quantity,
            order_type=order_type,
            price=price,
            tif=tif,
        )
        self._ensure_account_hash()
        try:
            resp = self._client.place_order(self._account_hash, spec)
        except SchwabAuthError:
            raise
        except Exception as e:
            if is_refresh_rejected(e):
                raise refresh_rejected_error(e) from e
            raise

        status_code = getattr(resp, "status_code", None)
        if status_code is not None and status_code >= 400:
            raise RuntimeError(f"Schwab rejected the order (HTTP {status_code})")

        order_id = extract_placed_order_id(resp)
        status = "ACCEPTED" if status_code in (200, 201, None) else str(status_code)
        return PlacedOrder(order_id=order_id, status=status)

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
