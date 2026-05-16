import os
from src.config import Settings

def test_defaults(monkeypatch):
    for key in ("USE_REAL_PROMPT_PULSE", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
                "XAI_API_KEY", "SCHWAB_APP_KEY", "SCHWAB_APP_SECRET", "SCHWAB_TOKEN_PATH"):
        monkeypatch.delenv(key, raising=False)
    s = Settings.from_env()
    assert s.use_real_prompt_pulse is False
    assert s.openai_api_key == ""
    assert s.anthropic_api_key == ""
    assert s.xai_api_key == ""

def test_flag_true(monkeypatch):
    monkeypatch.setenv("USE_REAL_PROMPT_PULSE", "true")
    s = Settings.from_env()
    assert s.use_real_prompt_pulse is True
