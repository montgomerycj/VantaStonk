"""Composite prompt_pulse score combining three signal components."""

COMPONENT_WEIGHTS = {
    "ai_sampling": 0.5,
    "social_velocity": 0.3,
    "volume_anomaly": 0.2,
}
NEUTRAL = 0.5


def compose(ai_sampling: float, social_velocity: float, volume_anomaly: float) -> float:
    s = (
        COMPONENT_WEIGHTS["ai_sampling"] * ai_sampling
        + COMPONENT_WEIGHTS["social_velocity"] * social_velocity
        + COMPONENT_WEIGHTS["volume_anomaly"] * volume_anomaly
    )
    return max(0.0, min(1.0, s))


def compose_with_fallback(ai_sampling, social_velocity, volume_anomaly) -> float:
    """Use 0.5 neutral for any None component (degraded signal source)."""
    return compose(
        NEUTRAL if ai_sampling is None else ai_sampling,
        NEUTRAL if social_velocity is None else social_velocity,
        NEUTRAL if volume_anomaly is None else volume_anomaly,
    )
