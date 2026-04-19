"""Tests for VantaStonk Prompt Pulse module."""

import pytest
from src.core.prompt_pulse import (
    PromptPulseInputs,
    score_prompt_pulse,
    estimate_discoverability,
    PP_WEIGHTS,
)


def test_pp_weights_sum_to_one():
    """Prompt Pulse sub-weights must sum to 1.0."""
    assert abs(sum(PP_WEIGHTS.values()) - 1.0) < 1e-9


def test_max_prompt_pulse():
    """All sub-factors at 1.0 → score = 1.0."""
    inputs = PromptPulseInputs(
        ticker="MAX",
        company_name="Max Corp",
        ai_query_likelihood=1.0,
        narrative_clarity=1.0,
        theme_alignment=1.0,
        retail_discoverability=1.0,
    )
    result = score_prompt_pulse(inputs)
    assert result.score == 1.0
    assert result.signal == "HIGH"


def test_zero_prompt_pulse():
    """All sub-factors at 0.0 → score = 0.0."""
    inputs = PromptPulseInputs(ticker="ZERO", company_name="Zero Inc")
    result = score_prompt_pulse(inputs)
    assert result.score == 0.0
    assert result.signal == "NONE"


def test_signal_levels():
    """Verify signal level thresholds."""
    high = PromptPulseInputs(ticker="H", company_name="H", ai_query_likelihood=1.0, narrative_clarity=1.0, theme_alignment=1.0, retail_discoverability=1.0)
    med = PromptPulseInputs(ticker="M", company_name="M", ai_query_likelihood=0.6, narrative_clarity=0.5, theme_alignment=0.5, retail_discoverability=0.5)
    low = PromptPulseInputs(ticker="L", company_name="L", ai_query_likelihood=0.4, narrative_clarity=0.3, theme_alignment=0.3, retail_discoverability=0.3)

    assert score_prompt_pulse(high).signal == "HIGH"
    assert score_prompt_pulse(med).signal == "MEDIUM"
    assert score_prompt_pulse(low).signal == "LOW"


def test_themes_preserved():
    """Matching themes should pass through to result."""
    inputs = PromptPulseInputs(
        ticker="THEME",
        company_name="Theme Corp",
        matching_themes=["ai_infrastructure", "cybersecurity"],
        prompt_matches=["best AI small caps"],
    )
    result = score_prompt_pulse(inputs)
    assert "ai_infrastructure" in result.matching_themes
    assert "best AI small caps" in result.prompt_matches


def test_discoverability_sweet_spot():
    """Mid-cap tech stock with short ticker should score well."""
    score = estimate_discoverability(
        ticker="PLTR",
        company_name="Palantir",
        market_cap_millions=5000,
        sector="Technology",
        has_options=True,
    )
    assert score >= 0.6


def test_discoverability_micro_cap():
    """Micro-cap scores lower than mid-cap."""
    micro = estimate_discoverability("TINY", "Tiny Biotech Corp International", 200, "healthcare")
    mid = estimate_discoverability("MID", "Mid Corp", 2000, "technology")
    assert mid > micro
