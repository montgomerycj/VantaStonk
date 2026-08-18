"""Core ring — manually curated, git-tracked, up to CORE_MAX entries."""

import json
import shutil
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

CORE_MAX = 25
CORE_PATH_DEFAULT = Path("data/watchlist_core.json")


@dataclass
class CoreEntry:
    ticker: str
    thesis: str
    added: str        # ISO date
    conviction: str   # 'high' | 'medium' | 'watching'
    review_by: str    # ISO date

    @classmethod
    def from_dict(cls, d: dict) -> "CoreEntry":
        return cls(
            ticker=d["ticker"].upper(),
            thesis=d.get("thesis", ""),
            added=d.get("added", ""),
            conviction=d.get("conviction", "watching"),
            review_by=d.get("review_by", ""),
        )


def load_core(path: Path = CORE_PATH_DEFAULT) -> list[CoreEntry]:
    p = Path(path)
    if not p.exists():
        return []
    data = json.loads(p.read_text())
    return [CoreEntry.from_dict(d) for d in data]


def _backup(path: Path):
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = path.with_name(f"{path.name}.bak-{ts}")
    shutil.copy2(path, bak)


def save_core(path: Path, entries: list[CoreEntry]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        _backup(p)
    p.write_text(json.dumps([asdict(e) for e in entries], indent=2))


def add_core_entry(path: Path, entry: CoreEntry) -> None:
    entries = load_core(path)
    if len(entries) >= CORE_MAX:
        raise ValueError(f"Core is full (max {CORE_MAX})")
    if any(e.ticker == entry.ticker for e in entries):
        raise ValueError(f"{entry.ticker} already in Core")
    entries.append(entry)
    save_core(path, entries)


def remove_core_entry(path: Path, ticker: str) -> None:
    entries = [e for e in load_core(path) if e.ticker != ticker.upper()]
    save_core(path, entries)
