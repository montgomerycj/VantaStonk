"""Rotating prompts for AI model sampling. Stable selection per run date."""

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class Prompt:
    prompt_id: str
    text: str


ROTATING_PROMPTS: list[Prompt] = [
    Prompt("undiscovered_weekly",
           "What under-the-radar small/mid-cap stocks (market cap $50M–$10B, US-listed) "
           "should retail traders watch this week? Give me 5–10 specific tickers with a "
           "one-line thesis each. Prioritize names that aren't yet widely discussed."),
    Prompt("sector_rotation",
           "Which sectors or sub-themes appear to be starting a rotation right now, and "
           "what specific small/mid-cap stocks would benefit? Give tickers."),
    Prompt("pre_catalyst_2wk",
           "Name 5 stocks with known catalysts in the next 2 weeks (earnings, FDA, product "
           "launch, partnership) that aren't already priced in. Be specific with tickers."),
    Prompt("squeezable_shorts",
           "Which small-cap stocks have high short interest (>15% of float) AND a recent "
           "positive catalyst that could trigger a squeeze? Tickers only."),
    Prompt("ai_adjacent_stealth",
           "What stealth AI-adjacent plays (companies benefiting from AI infrastructure, "
           "data, or applications) are not yet recognized as AI stocks by the market? Tickers."),
    Prompt("cannabis_biotech_catalyst",
           "In cannabis/MSO or small-cap biotech, which specific tickers have near-term "
           "regulatory or clinical catalysts that could re-rate the name 20%+?"),
    Prompt("overlooked_momentum",
           "What small-cap stocks are showing 3-month relative strength vs. their sector "
           "without having run more than 10% in the last week? List tickers."),
]


def pick_prompts_for_run(run_date: str, k: int = 5) -> list[Prompt]:
    """Deterministically pick k prompts for a given run date."""
    h = int(hashlib.sha256(run_date.encode()).hexdigest(), 16)
    n = len(ROTATING_PROMPTS)
    start = h % n
    return [ROTATING_PROMPTS[(start + i) % n] for i in range(k)]
