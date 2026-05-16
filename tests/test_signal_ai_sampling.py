from src.signals.ai_sampling import (
    AiSampleResult, MODEL_WEIGHTS, build_client, extract_tickers,
    compute_rank_weight, extract_ranked_tickers, compute_ai_sampling_score,
    MentionRecord,
)

def test_model_weights_sum_to_one():
    assert abs(sum(MODEL_WEIGHTS.values()) - 1.0) < 1e-9

def test_grok_weight_is_highest():
    assert MODEL_WEIGHTS["grok"] > MODEL_WEIGHTS["gpt-5"]
    assert MODEL_WEIGHTS["grok"] > MODEL_WEIGHTS["claude-4.7"]

def test_build_client_returns_callable():
    client = build_client("grok", api_key="fake")
    assert callable(client.query)

# --- Ticker extraction ---

def test_cashtag_extraction():
    text = "My picks: $AAPL, $NVDA and $RKLB for space."
    assert set(extract_tickers(text)) == {"AAPL", "NVDA", "RKLB"}

def test_bareword_ticker_extraction():
    text = "1. AAPL - iPhone maker\n2. NVDA - GPU leader\n3. TSM (Taiwan Semi)"
    got = set(extract_tickers(text))
    assert "AAPL" in got
    assert "NVDA" in got
    assert "TSM" in got

def test_common_false_positives_excluded():
    text = "Here are MY TOP 5 AI PICKS NOW ASAP: $AAPL."
    got = set(extract_tickers(text))
    assert got == {"AAPL"}

def test_dedupe():
    text = "$AAPL is great. AAPL trades at..."
    assert extract_tickers(text) == ["AAPL"]

# --- Rank-weighted convergence ---

def test_rank_weight():
    assert compute_rank_weight(0) == 1.5
    assert compute_rank_weight(2) == 1.5
    assert compute_rank_weight(3) == 1.0
    assert compute_rank_weight(99) == 1.0

def test_extract_ranked():
    text = "Here are 5 picks:\n1. AAPL — iPhone\n2. NVDA — GPUs\n3. AMD"
    ranked = extract_ranked_tickers(text)
    assert ranked[0] == ("AAPL", 0)
    assert ranked[1] == ("NVDA", 1)
    assert ranked[2] == ("AMD", 2)

def test_convergence_scoring_all_three_models():
    mentions = [
        MentionRecord(ticker="ABCD", model="grok", rank=0, is_fresh=False),
        MentionRecord(ticker="ABCD", model="gpt-5", rank=1, is_fresh=False),
        MentionRecord(ticker="ABCD", model="claude-4.7", rank=5, is_fresh=False),
    ]
    score = compute_ai_sampling_score("ABCD", mentions)
    assert score == 1.0

def test_convergence_grok_only_not_fresh():
    mentions = [MentionRecord(ticker="ABCD", model="grok", rank=5, is_fresh=False)]
    score = compute_ai_sampling_score("ABCD", mentions)
    assert abs(score - 0.45) < 1e-9

def test_freshness_bonus_applied_after_rank():
    mentions = [MentionRecord(ticker="ABCD", model="grok", rank=0, is_fresh=True)]
    score = compute_ai_sampling_score("ABCD", mentions)
    assert abs(score - 0.875) < 1e-9

def test_clamp_to_one():
    mentions = [
        MentionRecord(ticker="ABCD", model="grok", rank=0, is_fresh=True),
        MentionRecord(ticker="ABCD", model="gpt-5", rank=0, is_fresh=True),
        MentionRecord(ticker="ABCD", model="claude-4.7", rank=0, is_fresh=True),
    ]
    score = compute_ai_sampling_score("ABCD", mentions)
    assert score == 1.0
