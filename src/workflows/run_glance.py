"""
VantaStonk 95v2 — Glance Workflow

Produces the actionable daily output:
- 1–2 momentum picks (early-stage)
- 1 pair trade
- 1 macro tilt
- optional lotto

Pipeline:
1. Score universe
2. Apply anti-chasing filters
3. Rank survivors
4. Slot into Glance categories
5. Output markdown
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from src.core.scoring import ScoreInputs, ScoreResult, score, rank
from src.core.filters import PriceContext, FilterResult, check_chasing


@dataclass
class GlancePick:
    """A single Glance recommendation."""
    ticker: str
    category: str  # "momentum", "pair_trade", "macro_tilt", "lotto"
    setup: str
    why_now: str
    catalyst: str
    not_priced_in: str
    risk: str
    score_result: Optional[ScoreResult] = None


@dataclass
class GlanceOutput:
    """Full Glance output for a session."""
    timestamp: str
    picks: list[GlancePick] = field(default_factory=list)
    rejected: list[FilterResult] = field(default_factory=list)

    @property
    def momentum_picks(self) -> list[GlancePick]:
        return [p for p in self.picks if p.category == "momentum"]

    @property
    def pair_trade(self) -> Optional[GlancePick]:
        pts = [p for p in self.picks if p.category == "pair_trade"]
        return pts[0] if pts else None

    @property
    def macro_tilt(self) -> Optional[GlancePick]:
        mts = [p for p in self.picks if p.category == "macro_tilt"]
        return mts[0] if mts else None

    @property
    def lotto(self) -> Optional[GlancePick]:
        ls = [p for p in self.picks if p.category == "lotto"]
        return ls[0] if ls else None


def build_glance(
    scored: list[ScoreResult],
    picks_meta: dict[str, dict],
) -> GlanceOutput:
    """
    Build Glance output from scored + filtered candidates.

    scored: ranked ScoreResults (highest first)
    picks_meta: dict of ticker -> {category, setup, why_now, catalyst, not_priced_in, risk}
    """
    output = GlanceOutput(
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M PT"),
    )

    momentum_count = 0

    for result in scored:
        meta = picks_meta.get(result.ticker)
        if not meta:
            continue

        category = meta.get("category", "momentum")

        # Enforce Glance slot limits
        if category == "momentum" and momentum_count >= 2:
            continue
        if category == "pair_trade" and output.pair_trade is not None:
            continue
        if category == "macro_tilt" and output.macro_tilt is not None:
            continue
        if category == "lotto" and output.lotto is not None:
            continue

        pick = GlancePick(
            ticker=result.ticker,
            category=category,
            setup=meta.get("setup", ""),
            why_now=meta.get("why_now", ""),
            catalyst=meta.get("catalyst", ""),
            not_priced_in=meta.get("not_priced_in", ""),
            risk=meta.get("risk", ""),
            score_result=result,
        )

        output.picks.append(pick)
        if category == "momentum":
            momentum_count += 1

    return output


def format_glance_markdown(output: GlanceOutput) -> str:
    """Render Glance output as markdown."""
    lines = [
        f"# Glance — {output.timestamp}",
        "",
    ]

    if not output.picks:
        lines.append("_No actionable picks today._")
        return "\n".join(lines)

    # Momentum
    momentum = output.momentum_picks
    if momentum:
        lines.append("## Momentum (Early)")
        for p in momentum:
            _append_pick(lines, p)

    # Pair Trade
    if output.pair_trade:
        lines.append("## Pair Trade")
        _append_pick(lines, output.pair_trade)

    # Macro Tilt
    if output.macro_tilt:
        lines.append("## Macro Tilt")
        _append_pick(lines, output.macro_tilt)

    # Lotto
    if output.lotto:
        lines.append("## Lotto")
        _append_pick(lines, output.lotto)

    return "\n".join(lines)


def _append_pick(lines: list[str], pick: GlancePick):
    """Append a single pick to the markdown output."""
    score_str = ""
    if pick.score_result:
        score_str = f" [{pick.score_result.total:.2f} {pick.score_result.grade}]"

    lines.append(f"- **{pick.ticker}** — {pick.setup}{score_str}")
    lines.append(f"  - **Why now:** {pick.why_now}")
    lines.append(f"  - **Catalyst:** {pick.catalyst}")
    lines.append(f"  - **Not priced in:** {pick.not_priced_in}")
    lines.append(f"  - **Risk:** {pick.risk}")
    lines.append("")
