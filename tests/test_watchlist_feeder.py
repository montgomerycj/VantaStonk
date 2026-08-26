from src.watchlist.feeder import (
    FeederEntry, load_feeder, save_feeder, regenerate_feeder, FEEDER_MAX,
    should_prune,
)

def test_load_missing(tmp_path):
    assert load_feeder(tmp_path / "f.json") == []

def test_save_and_load(tmp_path):
    p = tmp_path / "f.json"
    e = FeederEntry(ticker="ABCD", composite_score=0.72,
                    signals={"ai_sampling": 0.8, "social_velocity": 0.4, "volume_anomaly": 0.6},
                    first_seen="2026-04-18", days_on_feeder=2)
    save_feeder(p, [e])
    loaded = load_feeder(p)
    assert loaded[0].ticker == "ABCD"
    assert loaded[0].days_on_feeder == 2

def test_regenerate_takes_top_N():
    # 60 scored candidates, should yield top FEEDER_MAX (40)
    scored = [(f"T{i:03d}", 1.0 - i * 0.01) for i in range(60)]
    existing = {}  # no prior Feeder
    new = regenerate_feeder(scored, existing, run_date="2026-04-20")
    assert len(new) == FEEDER_MAX
    assert new[0].ticker == "T000"
    assert new[-1].ticker == "T039"

def test_regenerate_preserves_first_seen():
    scored = [("ABCD", 0.8)]
    existing = {"ABCD": FeederEntry(ticker="ABCD", composite_score=0.7,
                                    signals={}, first_seen="2026-04-18", days_on_feeder=2)}
    new = regenerate_feeder(scored, existing, run_date="2026-04-20")
    assert new[0].first_seen == "2026-04-18"
    assert new[0].days_on_feeder == 3

def test_should_prune():
    # 3 consecutive scores <0.3 → prune
    assert should_prune([0.25, 0.28, 0.22]) is True
    assert should_prune([0.25, 0.35, 0.22]) is False
    assert should_prune([0.25, 0.28]) is False  # <3 scores
