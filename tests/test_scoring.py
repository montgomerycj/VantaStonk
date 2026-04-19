"""Tests for VantaStonk scoring engine."""

import pytest
from src.core.scoring import ScoreInputs, ScoreResult, score, rank, WEIGHTS


def test_weights_sum_to_one():
    """All weights must sum to 1.0."""
    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9


def test_perfect_score():
    """All factors at 1.0, no penalties → score = 1.0."""
    inputs = ScoreInputs(
        ticker="TEST",
        catalyst=1.0,
        prompt_pulse=1.0,
        freshness=1.0,
        peer=1.0,
        volume=1.0,
        macro=1.0,
    )
    result = score(inputs)
    assert result.total == 1.0
    assert result.grade == "A"
    assert result.penalties_applied == []


def test_zero_score():
    """All factors at 0.0 → score = 0.0."""
    inputs = ScoreInputs(ticker="ZERO")
    result = score(inputs)
    assert result.total == 0.0
    assert result.grade == "F"


def test_chasing_penalty():
    """Chasing penalty reduces score."""
    base = ScoreInputs(ticker="BASE", catalyst=0.8, prompt_pulse=0.7, freshness=0.6, peer=0.5, volume=0.5, macro=0.5)
    chasing = ScoreInputs(ticker="CHASE", catalyst=0.8, prompt_pulse=0.7, freshness=0.6, peer=0.5, volume=0.5, macro=0.5, is_chasing=True)

    base_result = score(base)
    chase_result = score(chasing)

    assert chase_result.total < base_result.total
    assert "chasing" in chase_result.penalties_applied[0]


def test_stale_narrative_penalty():
    """Stale narrative penalty reduces score."""
    inputs = ScoreInputs(ticker="STALE", catalyst=0.5, prompt_pulse=0.5, freshness=0.5, is_stale_narrative=True)
    result = score(inputs)
    assert "stale_narrative" in result.penalties_applied[0]


def test_multiple_penalties_stack():
    """Multiple penalties should stack."""
    inputs = ScoreInputs(
        ticker="BAD",
        catalyst=0.8, prompt_pulse=0.8, freshness=0.8, peer=0.8, volume=0.8, macro=0.8,
        is_chasing=True,
        is_stale_narrative=True,
        is_negative_peer=True,
    )
    result = score(inputs)
    assert len(result.penalties_applied) == 3
    assert result.total < 0.8  # raw would be 0.8, penalties should reduce


def test_score_clamped_to_zero():
    """Score should never go below 0.0 even with heavy penalties."""
    inputs = ScoreInputs(
        ticker="FLOOR",
        catalyst=0.1,
        is_chasing=True,
        is_stale_narrative=True,
        is_negative_peer=True,
    )
    result = score(inputs)
    assert result.total >= 0.0


def test_rank_ordering():
    """Rank should sort highest score first."""
    candidates = [
        ScoreInputs(ticker="LOW", catalyst=0.1),
        ScoreInputs(ticker="HIGH", catalyst=1.0, prompt_pulse=1.0, freshness=1.0),
        ScoreInputs(ticker="MID", catalyst=0.5, prompt_pulse=0.5),
    ]
    results = rank(candidates)
    assert results[0].ticker == "HIGH"
    assert results[-1].ticker == "LOW"


def test_grade_boundaries():
    """Verify grade cutoff boundaries."""
    # Grade A: >= 0.75
    assert score(ScoreInputs(ticker="A", catalyst=1.0, prompt_pulse=1.0, freshness=1.0, peer=1.0, volume=1.0, macro=1.0)).grade == "A"
    # Grade F: < 0.30
    assert score(ScoreInputs(ticker="F")).grade == "F"
