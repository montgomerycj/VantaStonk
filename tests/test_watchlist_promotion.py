from src.watchlist.promotion import (
    is_promotion_candidate, PROMOTION_SCORE_THRESHOLD, PROMOTION_DAYS_SUSTAINED,
)

def test_all_conditions_met():
    recent_composites = [0.7, 0.65, 0.8]  # all >=0.6
    assert is_promotion_candidate(
        recent_composites=recent_composites,
        five_day_move_pct=3.0,             # passes chasing
        volume_anomaly_component=0.5,      # >=0.3
    ) is True

def test_insufficient_days():
    assert is_promotion_candidate(
        recent_composites=[0.8, 0.9],  # only 2 days
        five_day_move_pct=3.0,
        volume_anomaly_component=0.5,
    ) is False

def test_score_dipped():
    assert is_promotion_candidate(
        recent_composites=[0.7, 0.55, 0.8],  # middle <0.6
        five_day_move_pct=3.0,
        volume_anomaly_component=0.5,
    ) is False

def test_chasing():
    assert is_promotion_candidate(
        recent_composites=[0.7, 0.7, 0.7],
        five_day_move_pct=6.0,  # >5% = chasing
        volume_anomaly_component=0.5,
    ) is False

def test_no_tape_confirmation():
    assert is_promotion_candidate(
        recent_composites=[0.7, 0.7, 0.7],
        five_day_move_pct=3.0,
        volume_anomaly_component=0.2,  # <0.3
    ) is False
