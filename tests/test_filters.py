"""Tests for VantaStonk anti-chasing filters."""

import pytest
from src.core.filters import (
    PriceContext,
    check_chasing,
    filter_universe,
    calc_5day_move,
    calc_intraday_move,
    MAX_5DAY_MOVE_PCT,
    MAX_INTRADAY_MOVE_PCT,
)


def test_clean_stock_passes():
    """Stock with small moves should pass."""
    ctx = PriceContext(ticker="CALM", price_current=100, price_5d_ago=98, price_open_today=99.5)
    result = check_chasing(ctx)
    assert result.passed is True
    assert result.is_chasing is False


def test_5day_chasing_rejected():
    """Stock up >5% in 5 days should be rejected."""
    ctx = PriceContext(ticker="HOT", price_current=110, price_5d_ago=100, price_open_today=109)
    result = check_chasing(ctx)
    assert result.passed is False
    assert result.is_chasing is True
    assert "5-day" in result.reasons[0]


def test_intraday_chasing_rejected():
    """Stock up >15% intraday should be rejected."""
    ctx = PriceContext(ticker="SPIKE", price_current=120, price_5d_ago=118, price_open_today=100)
    result = check_chasing(ctx)
    assert result.passed is False
    assert result.is_chasing is True
    assert "intraday" in result.reasons[0]


def test_catalyst_override():
    """New catalyst should override chasing rejection."""
    ctx = PriceContext(
        ticker="NEWS",
        price_current=115,
        price_5d_ago=100,
        price_open_today=108,
        has_new_catalyst=True,
        catalyst_description="FDA approval announced",
    )
    result = check_chasing(ctx)
    assert result.passed is True
    assert result.is_chasing is False  # cleared by catalyst
    assert "OVERRIDE" in result.reasons[-1]


def test_negative_move_chasing():
    """Large negative moves should also trigger chasing filter."""
    ctx = PriceContext(ticker="DUMP", price_current=90, price_5d_ago=100, price_open_today=95)
    result = check_chasing(ctx)
    assert result.passed is False
    assert result.is_chasing is True


def test_filter_universe_splits():
    """filter_universe should correctly split passed/rejected."""
    candidates = [
        PriceContext(ticker="OK", price_current=101, price_5d_ago=100, price_open_today=100.5),
        PriceContext(ticker="BAD", price_current=115, price_5d_ago=100, price_open_today=110),
        PriceContext(ticker="ALSO_OK", price_current=102, price_5d_ago=100, price_open_today=101),
    ]
    passed, rejected = filter_universe(candidates)
    assert len(passed) == 2
    assert len(rejected) == 1
    assert rejected[0].ticker == "BAD"


def test_zero_price_handling():
    """Zero prices should not cause division errors."""
    ctx = PriceContext(ticker="ZERO", price_current=10, price_5d_ago=0, price_open_today=0)
    result = check_chasing(ctx)
    assert result.passed is True  # 0% moves, no chasing
