from src.signals.volume_anomaly import (
    compute_rvol, score_volume_anomaly, passes_price_filter,
)

def test_rvol():
    assert abs(compute_rvol(today=3_000_000, avg_30d=1_000_000) - 3.0) < 1e-9
    assert compute_rvol(today=100, avg_30d=0) == 0.0

def test_score_bands():
    assert score_volume_anomaly(1.0) == 0.0
    assert score_volume_anomaly(1.75) == 0.3
    assert score_volume_anomaly(2.5) == 0.6
    assert score_volume_anomaly(4.0) == 0.85
    assert score_volume_anomaly(10.0) == 1.0

def test_price_filter():
    assert passes_price_filter(move_pct=4.5) is True
    assert passes_price_filter(move_pct=-4.5) is True
    assert passes_price_filter(move_pct=5.5) is False
    assert passes_price_filter(move_pct=-5.5) is False
