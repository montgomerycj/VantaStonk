"""Universe bounds for the watchlist v2."""

from dataclasses import dataclass

MARKET_CAP_MIN = 50.0         # $50M
MARKET_CAP_MAX = 10_000.0     # $10B
MICROCAP_MAX = 300.0          # $300M upper bound of microcap tier
MICROCAP_LIQUIDITY_FLOOR = 500_000.0   # $500K/day
SMALLMID_LIQUIDITY_FLOOR = 2_000_000.0 # $2M/day
MICROCAP_CAP = 15


@dataclass
class TickerFundamentals:
    ticker: str
    market_cap_millions: float
    avg_daily_dollar_volume: float


def is_microcap(mc: float) -> bool:
    return MARKET_CAP_MIN <= mc < MICROCAP_MAX


def passes_universe_bounds(f: TickerFundamentals) -> bool:
    if f.market_cap_millions < MARKET_CAP_MIN or f.market_cap_millions > MARKET_CAP_MAX:
        return False
    floor = MICROCAP_LIQUIDITY_FLOOR if is_microcap(f.market_cap_millions) else SMALLMID_LIQUIDITY_FLOOR
    return f.avg_daily_dollar_volume >= floor


def enforce_microcap_cap(
    core_microcaps: list[str],
    feeder_candidates: list[tuple[str, bool]],
    cap: int = MICROCAP_CAP,
) -> list[tuple[str, bool]]:
    """
    Core is authoritative. Feeder may contribute at most (cap - |core_microcaps|) microcaps.
    feeder_candidates is list of (ticker, is_microcap). Returns kept list preserving order.
    """
    remaining = max(0, cap - len(core_microcaps))
    kept: list[tuple[str, bool]] = []
    mc_taken = 0
    for ticker, is_mc in feeder_candidates:
        if is_mc:
            if mc_taken < remaining:
                kept.append((ticker, True))
                mc_taken += 1
        else:
            kept.append((ticker, False))
    return kept
