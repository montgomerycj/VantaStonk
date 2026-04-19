"""
VantaStonk 95v2 — Prompt Pulse

Predicts what AI tools (ChatGPT, Claude, Grok) will recommend next.

Score based on:
- AI query likelihood — how likely is this ticker to surface in AI responses?
- Narrative clarity — is the bull case simple and compelling?
- Theme alignment — does it match trending investment themes?
- Retail discoverability — will retail traders find this via AI prompts?

Example prompts to simulate:
- "best AI small caps"
- "stocks benefiting from tariffs"
- "short squeeze candidates"
"""

from dataclasses import dataclass, field


# Theme categories that drive AI recommendations
TRENDING_THEMES = [
    "ai_infrastructure",
    "defense_spending",
    "tariff_beneficiary",
    "reshoring",
    "energy_transition",
    "short_squeeze",
    "biotech_catalyst",
    "cybersecurity",
    "space_economy",
    "gig_economy",
]


@dataclass
class PromptPulseInputs:
    """Inputs for Prompt Pulse scoring."""
    ticker: str
    company_name: str

    # 0.0–1.0 scores
    ai_query_likelihood: float = 0.0
    narrative_clarity: float = 0.0
    theme_alignment: float = 0.0
    retail_discoverability: float = 0.0

    # Which themes match
    matching_themes: list[str] = field(default_factory=list)

    # Simulated prompt matches (e.g., "best AI small caps" → True)
    prompt_matches: list[str] = field(default_factory=list)


@dataclass
class PromptPulseResult:
    """Computed Prompt Pulse score with breakdown."""
    ticker: str
    score: float  # 0.0–1.0 composite
    breakdown: dict[str, float] = field(default_factory=dict)
    matching_themes: list[str] = field(default_factory=list)
    prompt_matches: list[str] = field(default_factory=list)

    @property
    def signal(self) -> str:
        if self.score >= 0.75:
            return "HIGH"
        elif self.score >= 0.50:
            return "MEDIUM"
        elif self.score >= 0.25:
            return "LOW"
        return "NONE"


# Sub-factor weights within Prompt Pulse
PP_WEIGHTS = {
    "ai_query_likelihood": 0.35,
    "narrative_clarity": 0.25,
    "theme_alignment": 0.25,
    "retail_discoverability": 0.15,
}


def score_prompt_pulse(inputs: PromptPulseInputs) -> PromptPulseResult:
    """Compute Prompt Pulse score from sub-factors."""

    breakdown = {
        "ai_query_likelihood": inputs.ai_query_likelihood * PP_WEIGHTS["ai_query_likelihood"],
        "narrative_clarity": inputs.narrative_clarity * PP_WEIGHTS["narrative_clarity"],
        "theme_alignment": inputs.theme_alignment * PP_WEIGHTS["theme_alignment"],
        "retail_discoverability": inputs.retail_discoverability * PP_WEIGHTS["retail_discoverability"],
    }

    total = sum(breakdown.values())
    total = max(0.0, min(1.0, total))

    return PromptPulseResult(
        ticker=inputs.ticker,
        score=round(total, 4),
        breakdown={k: round(v, 4) for k, v in breakdown.items()},
        matching_themes=inputs.matching_themes,
        prompt_matches=inputs.prompt_matches,
    )


def estimate_discoverability(
    ticker: str,
    company_name: str,
    market_cap_millions: float,
    sector: str,
    has_options: bool = True,
) -> float:
    """
    Heuristic estimate of how discoverable a stock is via AI prompts.

    Factors: name recognizability, market cap sweet spot, sector appeal, options availability.
    """
    score = 0.0

    # Market cap sweet spot: $500M–$10B (small/mid cap, interesting but not mega)
    if 500 <= market_cap_millions <= 10_000:
        score += 0.3
    elif 100 <= market_cap_millions < 500:
        score += 0.15  # micro caps less likely to surface

    # Short, memorable ticker (1-4 chars)
    if len(ticker) <= 4:
        score += 0.1

    # Sector appeal for AI recommendations
    hot_sectors = {"technology", "healthcare", "energy", "industrials", "communication"}
    if sector.lower() in hot_sectors:
        score += 0.2

    # Options availability (retail accessibility)
    if has_options:
        score += 0.1

    # Name clarity (shorter names are more searchable)
    if len(company_name.split()) <= 3:
        score += 0.1

    return min(1.0, score)
