from src.signals.composite import compose, COMPONENT_WEIGHTS, compose_with_fallback

def test_weights_sum_to_one():
    assert abs(sum(COMPONENT_WEIGHTS.values()) - 1.0) < 1e-9

def test_composite_math():
    assert abs(compose(0.8, 0.4, 0.6) - 0.64) < 1e-9

def test_clamp_low():
    assert compose(0.0, 0.0, 0.0) == 0.0

def test_clamp_high():
    assert compose(1.0, 1.0, 1.0) == 1.0

def test_neutral_default_on_missing():
    """If a component is None (signal source failed), use 0.5 neutral (spec S7.4)."""
    assert abs(compose_with_fallback(0.8, None, 0.6) - 0.67) < 1e-9
