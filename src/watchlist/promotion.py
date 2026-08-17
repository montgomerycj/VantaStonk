"""Promotion candidate detection: Feeder → Core (manual approval).

The system never writes Core. `is_promotion_candidate` is detect-only;
the user promotes by editing `data/watchlist_core.json` by hand.
"""

PROMOTION_SCORE_THRESHOLD = 0.6
PROMOTION_DAYS_SUSTAINED = 3
PROMOTION_CHASING_MAX = 5.0        # 5-day move < 5% (aligned with chasing filter)
PROMOTION_VOLUME_MIN = 0.3         # volume_anomaly component >=0.3


def is_promotion_candidate(
    recent_composites: list[float],
    five_day_move_pct: float,
    volume_anomaly_component: float,
) -> bool:
    if len(recent_composites) < PROMOTION_DAYS_SUSTAINED:
        return False
    if not all(c >= PROMOTION_SCORE_THRESHOLD for c in recent_composites[-PROMOTION_DAYS_SUSTAINED:]):
        return False
    if abs(five_day_move_pct) >= PROMOTION_CHASING_MAX:
        return False
    if volume_anomaly_component < PROMOTION_VOLUME_MIN:
        return False
    return True
