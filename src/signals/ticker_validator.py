"""Validates candidate tickers (e.g. extracted from AI responses) against Schwab."""

from typing import Protocol


class QuoteLookup(Protocol):
    def has_quote(self, symbol: str) -> bool: ...


def validate_tickers(candidates: list[str], client: QuoteLookup) -> tuple[list[str], list[str]]:
    """Return (valid, rejected) after deduping, normalizing, and Schwab-validating."""
    seen: set[str] = set()
    valid: list[str] = []
    rejected: list[str] = []
    for raw in candidates:
        sym = raw.strip().upper()
        if not sym or sym in seen:
            continue
        seen.add(sym)
        if client.has_quote(sym):
            valid.append(sym)
        else:
            rejected.append(sym)
    return valid, rejected
