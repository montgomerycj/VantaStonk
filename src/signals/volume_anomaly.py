"""Relative volume (RVOL) anomaly signal. Catches accumulation, rejects late-to-party."""

PRICE_FILTER_THRESHOLD = 5.0  # 5-day move %, aligned with chasing filter


def compute_rvol(today: float, avg_30d: float) -> float:
    if avg_30d <= 0:
        return 0.0
    return today / avg_30d


def passes_price_filter(move_pct: float) -> bool:
    """Only score RVOL spikes if 5-day price move is below the chasing threshold."""
    return abs(move_pct) < PRICE_FILTER_THRESHOLD


def score_volume_anomaly(rvol: float) -> float:
    if rvol < 1.5:
        return 0.0
    if rvol < 2.0:
        return 0.3
    if rvol < 3.0:
        return 0.6
    if rvol < 5.0:
        return 0.85
    return 1.0
