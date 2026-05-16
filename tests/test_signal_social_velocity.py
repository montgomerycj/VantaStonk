import json
from pathlib import Path
from src.signals.social_velocity import (
    parse_apewisdom_response,
    compute_velocity,
    score_velocity,
    passes_noise_floor,
)

FIX = Path(__file__).parent / "fixtures/apewisdom/apewisdom_sample.json"

def test_parse():
    rows = parse_apewisdom_response(json.loads(FIX.read_text()))
    assert len(rows) == 4
    assert rows[0].ticker == "AAPL"
    assert rows[0].mentions == 120

def test_velocity_math():
    assert abs(compute_velocity(60, 20) - 3.0) < 1e-9
    assert compute_velocity(10, 0) == 0.0

def test_velocity_scoring_bands():
    assert score_velocity(1.0) == 0.0
    assert score_velocity(1.75) == 0.3
    assert score_velocity(3.0) == 0.6
    assert score_velocity(7.0) == 0.9
    assert score_velocity(15.0) == 1.0

def test_noise_floor():
    assert passes_noise_floor(mentions_today=4) is False
    assert passes_noise_floor(mentions_today=5) is True
