"""AI model sampling — query three frontier models, score convergence, feed prompt_pulse."""

import re
from dataclasses import dataclass, field
from typing import Protocol

# Model-weighted convergence (sum = 1.0)
MODEL_WEIGHTS = {
    "grok": 0.45,      # real-time X access
    "gpt-5": 0.30,
    "claude-4.7": 0.25,
}


@dataclass
class AiSampleResult:
    model: str
    prompt_id: str
    prompt_text: str
    response_text: str
    tickers_extracted: list[str] = field(default_factory=list)
    token_cost_usd: float = 0.0


class _Client(Protocol):
    def query(self, prompt: str) -> AiSampleResult: ...


class _OpenAIClient:
    def __init__(self, api_key: str, model: str = "gpt-5", base_url: str | None = None):
        from openai import OpenAI
        self._openai = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
        self._model_id = model

    def query(self, prompt: str, prompt_id: str = "") -> AiSampleResult:
        resp = self._openai.chat.completions.create(
            model=self._model_id,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        text = resp.choices[0].message.content or ""
        usage = getattr(resp, "usage", None)
        cost = 0.0
        if usage:
            cost = (usage.prompt_tokens * 0.00001) + (usage.completion_tokens * 0.00003)
        return AiSampleResult(
            model=self._model_id,
            prompt_id=prompt_id,
            prompt_text=prompt,
            response_text=text,
            token_cost_usd=round(cost, 5),
        )


class _AnthropicClient:
    def __init__(self, api_key: str, model: str = "claude-opus-4-7"):
        from anthropic import Anthropic
        self._anthropic = Anthropic(api_key=api_key)
        self._model_id = model

    def query(self, prompt: str, prompt_id: str = "") -> AiSampleResult:
        resp = self._anthropic.messages.create(
            model=self._model_id,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in resp.content if hasattr(b, "text"))
        cost = 0.0
        if resp.usage:
            cost = (resp.usage.input_tokens * 0.000015) + (resp.usage.output_tokens * 0.000075)
        return AiSampleResult(
            model=self._model_id,
            prompt_id=prompt_id,
            prompt_text=prompt,
            response_text=text,
            token_cost_usd=round(cost, 5),
        )


def build_client(name: str, api_key: str) -> _Client:
    """Build a client by canonical model name."""
    if name == "grok":
        return _OpenAIClient(api_key=api_key, model="grok-4", base_url="https://api.x.ai/v1")
    if name == "gpt-5":
        return _OpenAIClient(api_key=api_key, model="gpt-5")
    if name == "claude-4.7":
        return _AnthropicClient(api_key=api_key, model="claude-opus-4-7")
    raise ValueError(f"unknown model: {name}")


# --- Ticker extraction ---

_CASHTAG_RE = re.compile(r"\$([A-Z]{1,5})\b")
_BAREWORD_RE = re.compile(r"\b([A-Z]{2,5})\b")

_BLOCKLIST = {
    "I", "A", "AI", "US", "USA", "ETF", "IPO", "CEO", "CFO", "COO", "CTO",
    "SEC", "FDA", "FTC", "DOJ", "IRS", "EU", "UK", "FX", "PE", "PS",
    "NOW", "TOP", "BIG", "NEW", "ALL", "THE", "MY", "YOUR", "OUR",
    "Q1", "Q2", "Q3", "Q4", "H1", "H2", "YTD", "EOD", "EOM", "EOY",
    "ASAP", "FYI", "OMG", "WTF", "LOL", "ATH", "ATL", "FOMO", "FUD",
    "GDP", "CPI", "PCE", "PPI", "ISM", "PMI", "FOMC", "NFP", "ECB",
    "PICKS", "TRADE", "STOCK", "BUY", "SELL", "HOLD", "LONG", "SHORT",
}


def extract_tickers(text: str) -> list[str]:
    """Extract likely ticker symbols. Dedupes; preserves first-seen order."""
    seen: set[str] = set()
    out: list[str] = []
    for m in _CASHTAG_RE.finditer(text):
        sym = m.group(1).upper()
        if sym not in seen and sym not in _BLOCKLIST:
            seen.add(sym); out.append(sym)
    for m in _BAREWORD_RE.finditer(text):
        sym = m.group(1).upper()
        if sym not in seen and sym not in _BLOCKLIST:
            seen.add(sym); out.append(sym)
    return out


# --- Rank-weighted convergence scoring ---

@dataclass
class MentionRecord:
    ticker: str
    model: str
    rank: int          # 0-indexed position within response list
    is_fresh: bool     # True if ticker is newly mentioned today


def compute_rank_weight(rank: int) -> float:
    """1.5x for top-3 (rank 0-2), else 1.0x."""
    return 1.5 if rank < 3 else 1.0


_RANKED_LINE_RE = re.compile(r"^\s*\d+[\.\)]\s+(.*)", re.MULTILINE)


def extract_ranked_tickers(text: str) -> list[tuple[str, int]]:
    """Extract tickers with their numeric list position. Returns [(ticker, rank_0indexed), ...]."""
    seen: set[str] = set()
    out: list[tuple[str, int]] = []
    lines = _RANKED_LINE_RE.findall(text)
    for idx, line in enumerate(lines):
        ts = extract_tickers(line)
        if ts and ts[0] not in seen:
            seen.add(ts[0])
            out.append((ts[0], idx))
    # Fallback: if no numbered list, flat extraction with sequential ranks
    if not out:
        for idx, sym in enumerate(extract_tickers(text)):
            out.append((sym, idx))
    return out


def compute_ai_sampling_score(ticker: str, mentions: list[MentionRecord]) -> float:
    """
    score = clamp((convergence * rank_weight) + freshness_bonus, 0.0, 1.0)

    convergence = sum of model weights for models mentioning the ticker.
    rank_weight uses the ticker's BEST (lowest) rank across mentions.
    freshness_bonus = 0.2 if any mention is fresh, else 0.
    """
    ticker_mentions = [m for m in mentions if m.ticker == ticker]
    if not ticker_mentions:
        return 0.0
    models_seen = {m.model for m in ticker_mentions}
    convergence = sum(MODEL_WEIGHTS.get(m, 0.0) for m in models_seen)
    best_rank = min(m.rank for m in ticker_mentions)
    fresh = any(m.is_fresh for m in ticker_mentions)
    rank_weight = compute_rank_weight(best_rank)
    freshness_bonus = 0.2 if fresh else 0.0
    score = (convergence * rank_weight) + freshness_bonus
    return max(0.0, min(1.0, score))
