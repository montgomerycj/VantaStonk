"""Feeder ring — auto-populated by the screener. Deterministic regeneration."""

import json
from dataclasses import dataclass, asdict, field
from pathlib import Path

FEEDER_MAX = 40
PRUNE_WINDOW = 3
PRUNE_THRESHOLD = 0.3
FEEDER_PATH_DEFAULT = Path("data/watchlist_feeder.json")


@dataclass
class FeederEntry:
    ticker: str
    composite_score: float
    signals: dict = field(default_factory=dict)  # ai_sampling, social_velocity, volume_anomaly
    first_seen: str = ""
    days_on_feeder: int = 0


def load_feeder(path: Path = FEEDER_PATH_DEFAULT) -> list[FeederEntry]:
    p = Path(path)
    if not p.exists():
        return []
    data = json.loads(p.read_text())
    return [FeederEntry(**d) for d in data]


def save_feeder(path: Path, entries: list[FeederEntry]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps([asdict(e) for e in entries], indent=2))


def regenerate_feeder(
    scored_candidates: list[tuple[str, float]],
    existing: dict[str, FeederEntry],
    run_date: str,
    signals_by_ticker: dict[str, dict] | None = None,
) -> list[FeederEntry]:
    """
    scored_candidates: [(ticker, composite_score)], sorted descending by score.
    existing: dict of ticker -> prior FeederEntry for first_seen preservation.
    """
    top = scored_candidates[:FEEDER_MAX]
    signals_by_ticker = signals_by_ticker or {}
    out: list[FeederEntry] = []
    for ticker, score in top:
        prior = existing.get(ticker)
        first_seen = prior.first_seen if prior else run_date
        days = (prior.days_on_feeder + 1) if prior else 1
        out.append(FeederEntry(
            ticker=ticker,
            composite_score=score,
            signals=signals_by_ticker.get(ticker, {}),
            first_seen=first_seen,
            days_on_feeder=days,
        ))
    return out


def should_prune(recent_composites: list[float],
                 window: int = PRUNE_WINDOW,
                 threshold: float = PRUNE_THRESHOLD) -> bool:
    """Return True if last `window` composites are all below `threshold`."""
    if len(recent_composites) < window:
        return False
    return all(c < threshold for c in recent_composites[-window:])
