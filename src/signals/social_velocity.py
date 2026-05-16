"""Social mention velocity (Apewisdom aggregates r/WSB, r/stocks, r/pennystocks, r/smallstreetbets)."""

from dataclasses import dataclass
from typing import Any

import httpx

APEWISDOM_URL = "https://apewisdom.io/api/v1.0/filter/all-stocks/page/1"
NOISE_FLOOR = 5  # ignore if absolute count < 5


@dataclass
class ApewisdomRow:
    ticker: str
    mentions: int
    sentiment: float | None = None
    upvotes: int | None = None


def parse_apewisdom_response(payload: dict[str, Any]) -> list[ApewisdomRow]:
    return [
        ApewisdomRow(
            ticker=r["ticker"].upper(),
            mentions=int(r.get("mentions", 0)),
            sentiment=r.get("sentiment"),
            upvotes=r.get("upvotes"),
        )
        for r in payload.get("results", [])
    ]


def fetch_apewisdom(client: httpx.Client | None = None, timeout: float = 10.0) -> list[ApewisdomRow]:
    """Fetch current Apewisdom snapshot. Raises on network error."""
    c = client or httpx.Client(timeout=timeout)
    r = c.get(APEWISDOM_URL)
    r.raise_for_status()
    return parse_apewisdom_response(r.json())


def compute_velocity(mentions_today: int, mentions_7d_avg: float) -> float:
    if mentions_7d_avg <= 0:
        return 0.0
    return mentions_today / mentions_7d_avg


def passes_noise_floor(mentions_today: int) -> bool:
    return mentions_today >= NOISE_FLOOR


def score_velocity(velocity: float) -> float:
    if velocity < 1.5:
        return 0.0
    if velocity < 2.0:
        return 0.3
    if velocity < 5.0:
        return 0.6
    if velocity < 10.0:
        return 0.9
    return 1.0
