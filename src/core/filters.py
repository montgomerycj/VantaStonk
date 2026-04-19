"""
VantaStonk 95v2 — Anti-Chasing Filters

Core rules:
- Reject >5% move in last 5 trading days
- Reject >15% intraday move
- Exception: clear NEW catalyst not priced in

No hidden heuristics. All thresholds are visible constants.
"""

from dataclasses import dataclass
from typing import Optional


# --- Thresholds (visible, tunable) ---

MAX_5DAY_MOVE_PCT = 5.0     # reject if >5% in last 5 trading days
MAX_INTRADAY_MOVE_PCT = 15.0  # reject if >15% intraday move


@dataclass
class PriceContext:
    """Price data needed for filter evaluation."""
    ticker: str
    price_current: float
    price_5d_ago: float
    price_open_today: float
    has_new_catalyst: bool = False  # exception override
    catalyst_description: Optional[str] = None


@dataclass
class FilterResult:
    """Result of running all filters on a candidate."""
    ticker: str
    passed: bool
    is_chasing: bool = False
    reasons: list[str] = None

    def __post_init__(self):
        if self.reasons is None:
            self.reasons = []


def calc_5day_move(ctx: PriceContext) -> float:
    """Percent change over 5 trading days."""
    if ctx.price_5d_ago == 0:
        return 0.0
    return ((ctx.price_current - ctx.price_5d_ago) / ctx.price_5d_ago) * 100


def calc_intraday_move(ctx: PriceContext) -> float:
    """Percent change from today's open."""
    if ctx.price_open_today == 0:
        return 0.0
    return ((ctx.price_current - ctx.price_open_today) / ctx.price_open_today) * 100


def check_chasing(ctx: PriceContext) -> FilterResult:
    """
    Apply anti-chasing filters.

    Returns FilterResult with passed=True if the stock is NOT chasing.
    Exception: new catalyst not priced in overrides the rejection.
    """
    reasons = []
    is_chasing = False

    move_5d = calc_5day_move(ctx)
    move_intraday = calc_intraday_move(ctx)

    if abs(move_5d) > MAX_5DAY_MOVE_PCT:
        reasons.append(f"5-day move {move_5d:+.1f}% exceeds ±{MAX_5DAY_MOVE_PCT}%")
        is_chasing = True

    if abs(move_intraday) > MAX_INTRADAY_MOVE_PCT:
        reasons.append(f"intraday move {move_intraday:+.1f}% exceeds ±{MAX_INTRADAY_MOVE_PCT}%")
        is_chasing = True

    # Exception: new catalyst overrides chasing rejection
    if is_chasing and ctx.has_new_catalyst:
        reasons.append(f"OVERRIDE: new catalyst — {ctx.catalyst_description or 'unspecified'}")
        return FilterResult(
            ticker=ctx.ticker,
            passed=True,
            is_chasing=False,  # cleared by catalyst
            reasons=reasons,
        )

    return FilterResult(
        ticker=ctx.ticker,
        passed=not is_chasing,
        is_chasing=is_chasing,
        reasons=reasons,
    )


def filter_universe(candidates: list[PriceContext]) -> tuple[list[FilterResult], list[FilterResult]]:
    """
    Run filters on a list of candidates.

    Returns (passed, rejected) lists.
    """
    passed = []
    rejected = []

    for ctx in candidates:
        result = check_chasing(ctx)
        if result.passed:
            passed.append(result)
        else:
            rejected.append(result)

    return passed, rejected
