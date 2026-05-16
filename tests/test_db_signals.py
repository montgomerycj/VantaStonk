import json
from datetime import datetime
from src.db import (
    init_db, get_connection,
    save_prompt_pulse_components, get_recent_components,
    save_ai_sample_raw, get_ai_samples_since,
    save_social_snapshot, get_mentions_history,
    save_recommendation_outcome, get_outcome,
    update_outcome_price, mark_outcome_dropped,
)

def _setup(tmp_path):
    db = tmp_path / "t.db"
    init_db(str(db))
    return get_connection(str(db))

def test_save_and_retrieve_components(tmp_path):
    conn = _setup(tmp_path)
    now = datetime.now().isoformat(timespec="seconds")
    save_prompt_pulse_components(
        conn, ticker="ABCD", captured_at=now, scan_type="premarket",
        ai_sampling=0.8, social_velocity=0.4, volume_anomaly=0.6, composite=0.72,
    )
    rows = get_recent_components(conn, "ABCD", limit=5)
    assert len(rows) == 1
    assert rows[0]["composite"] == 0.72
    assert rows[0]["ai_sampling"] == 0.8


def test_upsert_replaces_existing_component(tmp_path):
    conn = _setup(tmp_path)
    ts = datetime.now().isoformat(timespec="seconds")
    save_prompt_pulse_components(
        conn, ticker="XYZ", captured_at=ts, scan_type="premarket",
        ai_sampling=0.5, social_velocity=0.3, volume_anomaly=0.2, composite=0.40,
    )
    # Same ticker + captured_at → should replace, not duplicate
    save_prompt_pulse_components(
        conn, ticker="XYZ", captured_at=ts, scan_type="premarket",
        ai_sampling=0.9, social_velocity=0.7, volume_anomaly=0.6, composite=0.85,
    )
    rows = get_recent_components(conn, "XYZ", limit=10)
    assert len(rows) == 1
    assert rows[0]["composite"] == 0.85


def test_save_and_query_ai_sample(tmp_path):
    conn = _setup(tmp_path)
    now = datetime.now().isoformat(timespec="seconds")
    save_ai_sample_raw(
        conn, captured_at=now, model="grok", prompt_id="p1",
        prompt_text="What small caps?", response_text="$ABCD, $WXYZ",
        tickers_extracted=["ABCD", "WXYZ"], token_cost_usd=0.02,
    )
    rows = get_ai_samples_since(conn, since=now)
    assert len(rows) == 1
    assert json.loads(rows[0]["tickers_extracted"]) == ["ABCD", "WXYZ"]


def test_save_and_query_social_snapshot(tmp_path):
    conn = _setup(tmp_path)
    now = datetime.now().isoformat(timespec="seconds")
    save_social_snapshot(conn, captured_at=now, source="apewisdom",
                         ticker="ABCD", mentions_count=42, sentiment_score=0.6)
    hist = get_mentions_history(conn, "ABCD", source="apewisdom", days=7)
    assert len(hist) == 1
    assert hist[0]["mentions_count"] == 42


def test_outcome_lifecycle(tmp_path):
    conn = _setup(tmp_path)
    now = datetime.now().isoformat(timespec="seconds")
    save_recommendation_outcome(
        conn, ticker="ABCD", ring="feeder", first_appeared_at=now,
        entry_price=10.0, entry_price_source="premarket_quote",
        composite_score_at_entry=0.72,
    )
    update_outcome_price(conn, "ABCD", now, "feeder", field="price_1d", price=11.0)
    row = get_outcome(conn, "ABCD", now, "feeder")
    assert row["price_1d"] == 11.0
    assert row["dropped_at"] is None
    mark_outcome_dropped(conn, "ABCD", now, "feeder", dropped_at=now)
    row = get_outcome(conn, "ABCD", now, "feeder")
    assert row["dropped_at"] == now
