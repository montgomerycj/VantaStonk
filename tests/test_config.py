from pathlib import Path

from src.config import REPO_ROOT, Settings, resolve_schwab_token_path


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


def test_schwab_token_path_is_repo_absolute(monkeypatch, tmp_path):
    monkeypatch.delenv("SCHWAB_TOKEN_PATH", raising=False)
    monkeypatch.chdir(tmp_path)
    s = Settings.from_env()
    path = Path(s.schwab_token_path)
    assert path.is_absolute()
    assert path == REPO_ROOT / "data" / "schwab_token.json"
    assert path == Path(resolve_schwab_token_path())
    assert tmp_path not in path.parents


def test_relative_env_token_path_stays_repo_rooted(monkeypatch, tmp_path):
    monkeypatch.setenv("SCHWAB_TOKEN_PATH", "data/schwab_token.json")
    monkeypatch.chdir(tmp_path)
    path = Path(resolve_schwab_token_path())
    assert path.is_absolute()
    assert path == REPO_ROOT / "data" / "schwab_token.json"
    assert path != tmp_path / "data" / "schwab_token.json"


def test_absolute_env_token_path_is_honored(monkeypatch, tmp_path):
    override = tmp_path / "custom_token.json"
    monkeypatch.setenv("SCHWAB_TOKEN_PATH", str(override))
    assert Path(resolve_schwab_token_path()) == override
