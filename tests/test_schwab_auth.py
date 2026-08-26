"""Unit tests for Schwab auth hygiene. No live OAuth."""

import io
import json
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.integrations import schwab_client as schwab_client_mod
from src.integrations.schwab_auth import (
    LOGIN_COMMAND,
    SchwabAuthError,
    inspect_token,
    is_refresh_rejected,
    prepare_login_flow,
    publish_auth_url,
    require_usable_token,
    try_open_browser,
)
from src.integrations.schwab_client import SchwabClient


NOW = 1_700_000_000.0
DAY = 86400.0


def _write_token(path, age_days, include_timestamp=True):
    payload = {
        "token": {
            "access_token": "SECRET_ACCESS",
            "refresh_token": "SECRET_REFRESH",
        }
    }
    if include_timestamp:
        payload["creation_timestamp"] = NOW - (age_days * DAY)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_inspect_missing(tmp_path):
    age = inspect_token(tmp_path / "nope.json", now=NOW)
    assert age.status == "missing"
    assert age.age_days is None
    assert LOGIN_COMMAND in age.message
    assert "SECRET" not in age.message


def test_inspect_ok(tmp_path):
    path = _write_token(tmp_path / "t.json", age_days=1.0)
    age = inspect_token(path, now=NOW)
    assert age.status == "ok"
    assert age.age_days == pytest.approx(1.0)
    assert "ok" in age.message
    assert "SECRET" not in age.message


def test_inspect_warn_at_five_days(tmp_path):
    path = _write_token(tmp_path / "t.json", age_days=5.0)
    age = inspect_token(path, now=NOW)
    assert age.status == "warn"
    assert LOGIN_COMMAND in age.message


def test_inspect_dead_at_seven_days(tmp_path):
    path = _write_token(tmp_path / "t.json", age_days=7.0)
    age = inspect_token(path, now=NOW)
    assert age.status == "dead"
    assert LOGIN_COMMAND in age.message


def test_inspect_dead_after_seven_days(tmp_path):
    path = _write_token(tmp_path / "t.json", age_days=8.5)
    age = inspect_token(path, now=NOW)
    assert age.status == "dead"


def test_inspect_falls_back_to_mtime(tmp_path):
    path = _write_token(tmp_path / "t.json", age_days=0, include_timestamp=False)
    mtime = NOW - (6 * DAY)
    # utime wants (atime, mtime)
    import os
    os.utime(path, (mtime, mtime))
    age = inspect_token(path, now=NOW)
    assert age.status == "warn"
    assert age.age_days == pytest.approx(6.0)


def test_require_usable_token_raises_when_dead(tmp_path):
    path = _write_token(tmp_path / "t.json", age_days=9.0)
    buf = io.StringIO()
    with pytest.raises(SchwabAuthError) as exc:
        require_usable_token(path, now=NOW, stream=buf)
    assert exc.value.status == "dead"
    assert LOGIN_COMMAND in str(exc.value)
    assert LOGIN_COMMAND in buf.getvalue()


def test_require_usable_token_ok(tmp_path):
    path = _write_token(tmp_path / "t.json", age_days=0.5)
    buf = io.StringIO()
    age = require_usable_token(path, now=NOW, stream=buf)
    assert age.status == "ok"
    assert "ok" in buf.getvalue()


def test_is_refresh_rejected():
    assert is_refresh_rejected(Exception("OAuthError: invalid_client: refresh token invalid"))
    assert is_refresh_rejected(Exception("refresh token invalid"))
    assert not is_refresh_rejected(Exception("connection reset"))


def test_publish_auth_url_prints_and_writes(tmp_path, capsys):
    dest = tmp_path / "schwab_auth_url.txt"
    url = "https://api.schwabapi.com/v1/oauth/authorize?response_type=code&client_id=fake"
    publish_auth_url(url, dest)
    captured = capsys.readouterr()
    assert url in captured.out
    assert url in captured.err
    assert dest.read_text(encoding="utf-8").strip() == url


def test_try_open_browser_failure_does_not_raise():
    def boom(_url):
        raise RuntimeError("no display")

    assert try_open_browser("https://example.invalid/auth", opener=boom) is False


def test_prepare_login_flow_prints_before_pinning(tmp_path, capsys):
    import webbrowser

    url = "https://api.schwabapi.com/v1/oauth/authorize?state=abc"
    ctx = SimpleNamespace(authorization_url=url, callback_url="https://127.0.0.1:8182/", state="abc")

    class FakeAuth:
        def get_auth_context(self, api_key, callback_url, state=None):
            return ctx

    auth = FakeAuth()
    dest = tmp_path / "url.txt"
    original_get = webbrowser.get
    try:
        returned = prepare_login_flow(auth, "key", "https://127.0.0.1:8182/", dest)
        captured = capsys.readouterr()
        assert returned is ctx
        assert url in captured.out
        assert dest.read_text(encoding="utf-8").strip() == url
        assert auth.get_auth_context() is ctx
    finally:
        webbrowser.get = original_get


def test_connect_missing_token_returns_false(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(schwab_client_mod, "APP_KEY", "k")
    monkeypatch.setattr(schwab_client_mod, "APP_SECRET", "s")

    def fail_if_called(**kwargs):
        raise AssertionError("client_from_token_file should not run for a missing token")

    monkeypatch.setattr(schwab_client_mod.auth, "client_from_token_file", fail_if_called)
    client = SchwabClient(token_path=str(tmp_path / "missing.json"))
    assert client.connect() is False
    out = capsys.readouterr().out
    assert LOGIN_COMMAND in out
    assert "missing" in out.lower()


def test_connect_dead_token_returns_false(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(schwab_client_mod, "APP_KEY", "k")
    monkeypatch.setattr(schwab_client_mod, "APP_SECRET", "s")
    path = tmp_path / "t.json"
    path.write_text(
        json.dumps({
            "creation_timestamp": time.time() - (8.0 * DAY),
            "token": {"access_token": "SECRET_ACCESS", "refresh_token": "SECRET_REFRESH"},
        }),
        encoding="utf-8",
    )

    def fail_if_called(**kwargs):
        raise AssertionError("client_from_token_file should not run for a dead token")

    monkeypatch.setattr(schwab_client_mod.auth, "client_from_token_file", fail_if_called)
    client = SchwabClient(token_path=str(path))
    assert client.connect() is False
    out = capsys.readouterr().out
    assert LOGIN_COMMAND in out
    assert "dead" in out.lower()
    assert "SECRET" not in out


def test_login_script_keeps_windows_safe_flags():
    src = Path("scripts/schwab_login.py").read_text(encoding="utf-8")
    assert "interactive=False" in src
    assert "freeze_support" in src
    assert 'if __name__ == "__main__"' in src
    assert "resolve_schwab_token_path" in src
    assert 'os.getenv("SCHWAB_TOKEN_PATH", "data/schwab_token.json")' not in src


def test_connect_maps_invalid_client_to_login_command(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(schwab_client_mod, "APP_KEY", "k")
    monkeypatch.setattr(schwab_client_mod, "APP_SECRET", "s")
    path = _write_token(tmp_path / "t.json", age_days=1.0)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["creation_timestamp"] = time.time() - DAY
    path.write_text(json.dumps(payload), encoding="utf-8")

    def boom(**kwargs):
        raise Exception("OAuthError: invalid_client: refresh token invalid")

    monkeypatch.setattr(schwab_client_mod.auth, "client_from_token_file", boom)
    client = SchwabClient(token_path=str(path))
    assert client.connect() is False
    out = capsys.readouterr().out
    assert LOGIN_COMMAND in out
    assert "SECRET" not in out
