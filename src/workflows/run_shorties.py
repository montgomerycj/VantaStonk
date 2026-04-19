"""
VantaStonk 95v2 — Shorties Workflow

Identifies fade/short candidates:
- Overextended to the upside
- Fresh downside catalysts
- Crowded trades unwinding

These are the opposite of Glance — stocks to avoid or actively short.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from src.core.scoring import ScoreResult


@dataclass
class ShortCandidate:
    """A single Shorties entry."""
    ticker: str
    why_short: str
    catalyst: str
    risk: str  # risk of being wrong (short squeeze, etc.)
    overextension_pct: Optional[float] = None  # how far above norm
    score_result: Optional[ScoreResult] = None
    category: str = "fade"  # "fade", "breakdown", "crowded_unwind"


@dataclass
class ShortiesOutput:
    """Full Shorties output for a session."""
    timestamp: str
    candidates: list[ShortCandidate] = field(default_factory=list)

    @property
    def fades(self) -> list[ShortCandidate]:
        return [c for c in self.candidates if c.category == "fade"]

    @property
    def breakdowns(self) -> list[ShortCandidate]:
        return [c for c in self.candidates if c.category == "breakdown"]

    @property
    def crowded_unwinds(self) -> list[ShortCandidate]:
        return [c for c in self.candidates if c.category == "crowded_unwind"]


def is_overextended(
    price_current: float,
    price_5d_ago: float,
    threshold_pct: float = 10.0,
) -> tuple[bool, float]:
    """
    Check if a stock is overextended to the upside.

    Returns (is_overextended, move_pct).
    """
    if price_5d_ago == 0:
        return False, 0.0
    move_pct = ((price_current - price_5d_ago) / price_5d_ago) * 100
    return move_pct > threshold_pct, round(move_pct, 2)


def build_shorties(candidates: list[ShortCandidate]) -> ShortiesOutput:
    """Build Shorties output from evaluated candidates."""
    return ShortiesOutput(
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M PT"),
        candidates=sorted(
            candidates,
            key=lambda c: c.overextension_pct or 0,
            reverse=True,
        ),
    )


def format_shorties_markdown(output: ShortiesOutput) -> str:
    """Render Shorties output as markdown."""
    lines = [
        f"# Shorties — {output.timestamp}",
        "",
    ]

    if not output.candidates:
        lines.append("_No short/fade candidates today._")
        return "\n".join(lines)

    # Group by category
    for label, group in [
        ("Fades (Overextended)", output.fades),
        ("Breakdowns", output.breakdowns),
        ("Crowded Unwinds", output.crowded_unwinds),
    ]:
        if not group:
            continue
        lines.append(f"## {label}")
        for c in group:
            ext_str = f" (+{c.overextension_pct:.1f}%)" if c.overextension_pct else ""
            lines.append(f"- **{c.ticker}**{ext_str}")
            lines.append(f"  - **Why short:** {c.why_short}")
            lines.append(f"  - **Catalyst:** {c.catalyst}")
            lines.append(f"  - **Risk:** {c.risk}")
            lines.append("")

    return "\n".join(lines)
