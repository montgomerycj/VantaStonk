"""
VantaStonk 95v2 — ShadowList Workflow

Tracks pre-trigger candidates: stocks that are interesting but NOT ready yet.
Each entry requires a clear trigger to graduate to Glance.

Pipeline:
1. Evaluate candidates that didn't pass Glance thresholds
2. Check if any existing ShadowList entries have triggered
3. Graduate triggered entries → Glance
4. Add new pre-trigger entries
5. Output markdown
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from src.core.scoring import ScoreResult


@dataclass
class ShadowEntry:
    """A single ShadowList entry."""
    ticker: str
    why_interesting: str
    why_not_ready: str
    trigger: str
    added_date: str
    score_result: Optional[ScoreResult] = None
    is_triggered: bool = False
    trigger_note: Optional[str] = None


@dataclass
class ShadowListOutput:
    """Full ShadowList state."""
    timestamp: str
    active: list[ShadowEntry] = field(default_factory=list)
    graduated: list[ShadowEntry] = field(default_factory=list)
    expired: list[ShadowEntry] = field(default_factory=list)


def evaluate_trigger(entry: ShadowEntry, current_data: dict) -> ShadowEntry:
    """
    Check if an existing ShadowList entry's trigger condition has been met.

    current_data: dict with keys like 'price', 'volume', 'news', 'catalyst' etc.
    This is intentionally flexible — trigger evaluation is context-dependent.
    """
    # Trigger evaluation is done externally (by the AI agent or data pipeline).
    # This function is a structured hook for that evaluation.
    return entry


def add_to_shadowlist(
    ticker: str,
    why_interesting: str,
    why_not_ready: str,
    trigger: str,
    score_result: Optional[ScoreResult] = None,
) -> ShadowEntry:
    """Create a new ShadowList entry."""
    return ShadowEntry(
        ticker=ticker,
        why_interesting=why_interesting,
        why_not_ready=why_not_ready,
        trigger=trigger,
        added_date=datetime.now().strftime("%Y-%m-%d"),
        score_result=score_result,
    )


def refresh_shadowlist(
    current_entries: list[ShadowEntry],
    new_candidates: list[ShadowEntry],
    max_entries: int = 10,
) -> ShadowListOutput:
    """
    Refresh the ShadowList:
    - Graduate any triggered entries
    - Add new candidates
    - Expire oldest if over limit
    """
    output = ShadowListOutput(
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M PT"),
    )

    # Check existing entries for triggers
    for entry in current_entries:
        if entry.is_triggered:
            output.graduated.append(entry)
        else:
            output.active.append(entry)

    # Add new candidates (avoid duplicates)
    active_tickers = {e.ticker for e in output.active}
    for candidate in new_candidates:
        if candidate.ticker not in active_tickers:
            output.active.append(candidate)
            active_tickers.add(candidate.ticker)

    # Expire oldest if over limit
    if len(output.active) > max_entries:
        # Sort by added_date, expire oldest
        output.active.sort(key=lambda e: e.added_date, reverse=True)
        output.expired = output.active[max_entries:]
        output.active = output.active[:max_entries]

    return output


def format_shadowlist_markdown(output: ShadowListOutput) -> str:
    """Render ShadowList as markdown."""
    lines = [
        f"# ShadowList — {output.timestamp}",
        "",
    ]

    if output.graduated:
        lines.append("## Graduated → Glance")
        for e in output.graduated:
            lines.append(f"- **{e.ticker}** — TRIGGERED: {e.trigger_note or e.trigger}")
        lines.append("")

    if not output.active:
        lines.append("_No active ShadowList entries._")
        return "\n".join(lines)

    lines.append("## Active")
    for e in output.active:
        score_str = f" [{e.score_result.total:.2f}]" if e.score_result else ""
        lines.append(f"- **{e.ticker}**{score_str} (added {e.added_date})")
        lines.append(f"  - **Why interesting:** {e.why_interesting}")
        lines.append(f"  - **Why not ready:** {e.why_not_ready}")
        lines.append(f"  - **Trigger:** {e.trigger}")
        lines.append("")

    if output.expired:
        lines.append("## Expired")
        for e in output.expired:
            lines.append(f"- ~~{e.ticker}~~ (added {e.added_date})")
        lines.append("")

    return "\n".join(lines)
