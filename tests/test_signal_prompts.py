from src.signals.prompts import ROTATING_PROMPTS, pick_prompts_for_run

def test_prompt_set_size():
    assert 5 <= len(ROTATING_PROMPTS) <= 7

def test_each_prompt_has_id_and_text():
    for p in ROTATING_PROMPTS:
        assert p.prompt_id
        assert len(p.text) > 20
        assert p.text.strip() == p.text

def test_pick_prompts_for_run_is_stable():
    """Given the same date, same prompts. Different dates, different subsets."""
    a = pick_prompts_for_run("2026-04-20")
    b = pick_prompts_for_run("2026-04-20")
    assert a == b
    c = pick_prompts_for_run("2026-04-21")
    assert {p.prompt_id for p in a} | {p.prompt_id for p in c} <= {p.prompt_id for p in ROTATING_PROMPTS}

def test_pick_selects_5_per_run():
    picks = pick_prompts_for_run("2026-04-20")
    assert len(picks) == 5
