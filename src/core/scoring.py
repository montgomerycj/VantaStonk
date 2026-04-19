"""
VantaStonk 95v2 — Scoring Engine

TOTAL_SCORE = (
    catalyst * 0.28 +
    prompt_pulse * 0.24 +
    freshness * 0.18 +
    peer * 0.12 +
    volume * 0.08 +
    macro * 0.10
)

All weights are visible and tunable. No hidden heuristics.
"""

from dataclasses import dataclass, field
from typing import Optional


# --- Weights (visible, tunable) ---

WEIGHTS = {
    "catalyst": 0.28,
    "prompt_pulse": 0.24,
    "freshness": 0.18,
    "peer": 0.12,
    "volume": 0.08,
    "macro": 0.10,
}

# --- Penalties ---

PENALTY_CHASING = -0.25          # applied when chasing detected
PENALTY_STALE_NARRATIVE = -0.15  # applied when narrative is stale
PENALTY_NEGATIVE_PEER = -0.10   # applied when peer trend is negative


@dataclass
class ScoreInputs:
    """Raw factor scores (0.0–1.0 each)."""
    ticker: str
    catalyst: float = 0.0
    prompt_pulse: float = 0.0
    freshness: float = 0.0
    peer: float = 0.0
    volume: float = 0.0
    macro: float = 0.0

    # Penalty flags
    is_chasing: bool = False
    is_stale_narrative: bool = False
    is_negative_peer: bool = False


@dataclass
class ScoreResult:
    """Computed score with breakdown."""
    ticker: str
    total: float
    raw_total: float
    penalties_applied: list[str] = field(default_factory=list)
    breakdown: dict[str, float] = field(default_factory=dict)

    @property
    def grade(self) -> str:
        if self.total >= 0.75:
            return "A"
        elif self.total >= 0.60:
            return "B"
        elif self.total >= 0.45:
            return "C"
        elif self.total >= 0.30:
            return "D"
        return "F"


def score(inputs: ScoreInputs) -> ScoreResult:
    """Compute total score from factor inputs + penalties."""

    # Weighted sum
    breakdown = {
        "catalyst": inputs.catalyst * WEIGHTS["catalyst"],
        "prompt_pulse": inputs.prompt_pulse * WEIGHTS["prompt_pulse"],
        "freshness": inputs.freshness * WEIGHTS["freshness"],
        "peer": inputs.peer * WEIGHTS["peer"],
        "volume": inputs.volume * WEIGHTS["volume"],
        "macro": inputs.macro * WEIGHTS["macro"],
    }

    raw_total = sum(breakdown.values())

    # Apply penalties
    penalty_total = 0.0
    penalties_applied = []

    if inputs.is_chasing:
        penalty_total += PENALTY_CHASING
        penalties_applied.append(f"chasing ({PENALTY_CHASING})")

    if inputs.is_stale_narrative:
        penalty_total += PENALTY_STALE_NARRATIVE
        penalties_applied.append(f"stale_narrative ({PENALTY_STALE_NARRATIVE})")

    if inputs.is_negative_peer:
        penalty_total += PENALTY_NEGATIVE_PEER
        penalties_applied.append(f"negative_peer ({PENALTY_NEGATIVE_PEER})")

    total = max(0.0, min(1.0, raw_total + penalty_total))

    return ScoreResult(
        ticker=inputs.ticker,
        total=round(total, 4),
        raw_total=round(raw_total, 4),
        penalties_applied=penalties_applied,
        breakdown={k: round(v, 4) for k, v in breakdown.items()},
    )


def rank(candidates: list[ScoreInputs]) -> list[ScoreResult]:
    """Score and rank a list of candidates, highest first."""
    results = [score(c) for c in candidates]
    results.sort(key=lambda r: r.total, reverse=True)
    return results
