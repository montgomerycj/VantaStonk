from src.watchlist.universe import (
    TickerFundamentals, passes_universe_bounds,
    enforce_microcap_cap, MICROCAP_CAP,
)

def _fund(mc, dv):
    return TickerFundamentals(ticker="X", market_cap_millions=mc, avg_daily_dollar_volume=dv)

def test_in_range_small_cap_passes():
    assert passes_universe_bounds(_fund(500, 3_000_000)) is True

def test_below_market_cap_rejected():
    assert passes_universe_bounds(_fund(30, 1_000_000)) is False

def test_above_market_cap_rejected():
    assert passes_universe_bounds(_fund(12_000, 5_000_000)) is False

def test_microcap_liquidity_floor():
    assert passes_universe_bounds(_fund(200, 400_000)) is False
    assert passes_universe_bounds(_fund(200, 600_000)) is True

def test_small_mid_liquidity_floor():
    assert passes_universe_bounds(_fund(500, 1_500_000)) is False
    assert passes_universe_bounds(_fund(500, 3_000_000)) is True

def test_microcap_cap_enforcement():
    core_micros = ["A", "B", "C"]
    feeder_candidates = [
        ("D", True), ("E", True), ("F", False), ("G", True),
    ]
    kept = enforce_microcap_cap(core_micros, feeder_candidates, cap=MICROCAP_CAP)
    all_micros = core_micros + [t for t, is_mc in kept if is_mc]
    assert sum(1 for _, is_mc in kept if is_mc) + len(core_micros) <= MICROCAP_CAP

def test_microcap_cap_core_exceeded():
    """When Core alone exceeds cap, Feeder contributes zero microcaps."""
    core_micros = [f"M{i}" for i in range(16)]
    feeder_candidates = [("X", True), ("Y", False)]
    kept = enforce_microcap_cap(core_micros, feeder_candidates, cap=MICROCAP_CAP)
    assert [t for t, is_mc in kept if is_mc] == []
    assert any(t == "Y" for t, _ in kept)
