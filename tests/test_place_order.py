"""Unit tests for Schwab equity order sending. No live API."""

import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.integrations.schwab_auth import LOGIN_COMMAND
from src.integrations.schwab_client import (
    SchwabClient,
    build_equity_order,
    extract_placed_order_id,
    looks_like_option_symbol,
    normalize_equity_ticker,
)

import scripts.place_order as place_order_script


SECRET_MARKERS = (
    "SECRET_ACCESS",
    "SECRET_REFRESH",
    "APP_KEY_SECRET",
    "APP_SECRET_VALUE",
    "access_token",
    "refresh_token",
)


def _assert_no_secrets(text: str):
    lowered = text.lower()
    for marker in SECRET_MARKERS:
        assert marker.lower() not in lowered


def test_build_market_buy_defaults_to_day():
    spec = build_equity_order("aapl", "buy", 10, "market")
    assert spec["orderType"] == "MARKET"
    assert spec["duration"] == "DAY"
    assert spec["session"] == "NORMAL"
    assert spec["orderStrategyType"] == "SINGLE"
    leg = spec["orderLegCollection"][0]
    assert leg["instruction"] == "BUY"
    assert leg["quantity"] == 10
    assert leg["instrument"]["assetType"] == "EQUITY"
    assert leg["instrument"]["symbol"] == "AAPL"


def test_build_limit_sell_requires_and_includes_price():
    spec = build_equity_order("MSFT", "sell", 2, "limit", price=190)
    assert spec["orderType"] == "LIMIT"
    assert spec["price"] == "190.00"
    assert spec["duration"] == "DAY"
    assert spec["orderLegCollection"][0]["instruction"] == "SELL"


def test_limit_without_price_raises():
    with pytest.raises(ValueError, match="price"):
        build_equity_order("AAPL", "buy", 1, "limit")


def test_market_rejects_price():
    with pytest.raises(ValueError, match="price"):
        build_equity_order("AAPL", "buy", 1, "market", price=10)


def test_gtc_only_when_explicit():
    day = build_equity_order("AAPL", "buy", 1, "market")
    assert day["duration"] == "DAY"
    gtc = build_equity_order("AAPL", "buy", 1, "limit", price=10, tif="GTC")
    assert gtc["duration"] == "GOOD_TILL_CANCEL"


def test_rejects_bad_quantity_side_and_type():
    with pytest.raises(ValueError, match="quantity"):
        build_equity_order("AAPL", "buy", 0, "market")
    with pytest.raises(ValueError, match="quantity"):
        build_equity_order("AAPL", "buy", -3, "market")
    with pytest.raises(ValueError, match="quantity"):
        build_equity_order("AAPL", "buy", 1.5, "market")
    with pytest.raises(ValueError, match="side"):
        build_equity_order("AAPL", "hold", 1, "market")
    with pytest.raises(ValueError, match="order type"):
        build_equity_order("AAPL", "buy", 1, "stop")


def test_rejects_occ_and_option_like_symbols():
    occ_spaced = "AAPL  240119C00150000"
    occ_compact = "AAPL240119C00150000"
    assert looks_like_option_symbol(occ_spaced)
    assert looks_like_option_symbol(occ_compact)
    with pytest.raises(ValueError, match="Options symbols"):
        normalize_equity_ticker(occ_spaced)
    with pytest.raises(ValueError, match="Options symbols"):
        build_equity_order(occ_compact, "buy", 1, "market")
    with pytest.raises(ValueError, match="Options symbols"):
        build_equity_order("QQQ 240420P00500000", "buy", 1, "market")


def test_rejects_non_equity_tickers():
    with pytest.raises(ValueError, match="common-stock"):
        normalize_equity_ticker("BRK.BB")
    with pytest.raises(ValueError, match="common-stock"):
        normalize_equity_ticker("123")


def test_share_class_tickers_are_equities():
    assert normalize_equity_ticker("brk.b") == "BRK.B"
    spec = build_equity_order("BRK/B", "buy", 1, "market")
    assert spec["orderLegCollection"][0]["instrument"]["symbol"] == "BRK/B"


def test_extract_order_id_from_location_without_exposing_hash():
    location = "https://api.schwabapi.com/trader/v1/accounts/HASHVALUE123/orders/987654321"
    resp = SimpleNamespace(headers={"Location": location})
    assert extract_placed_order_id(resp) == "987654321"
    assert extract_placed_order_id(SimpleNamespace(headers={})) is None


def test_place_order_uses_first_account_hash_and_mocks_client():
    client = SchwabClient(token_path="/unused/token.json")
    inner = MagicMock()
    account_resp = MagicMock()
    account_resp.json.return_value = [
        {"hashValue": "FIRSTHASH"},
        {"hashValue": "SECONDHASH"},
    ]
    account_resp.raise_for_status.return_value = None
    inner.get_account_numbers.return_value = account_resp

    place_resp = MagicMock()
    place_resp.status_code = 201
    place_resp.headers = {
        "Location": "https://api.schwabapi.com/trader/v1/accounts/FIRSTHASH/orders/555",
    }
    inner.place_order.return_value = place_resp
    client._client = inner

    result = client.place_order("AAPL", "buy", 1, "market")

    inner.place_order.assert_called_once()
    args, kwargs = inner.place_order.call_args
    assert args[0] == "FIRSTHASH"
    spec = args[1] if len(args) > 1 else kwargs.get("order_spec")
    assert spec["orderType"] == "MARKET"
    assert spec["orderLegCollection"][0]["instrument"]["symbol"] == "AAPL"
    assert result.order_id == "555"
    assert result.status == "ACCEPTED"
    inner.get_account.assert_not_called()


def test_place_order_maps_refresh_reject_to_login_command():
    client = SchwabClient(token_path="/unused/token.json")
    inner = MagicMock()
    account_resp = MagicMock()
    account_resp.json.return_value = [{"hashValue": "H"}]
    inner.get_account_numbers.return_value = account_resp
    inner.place_order.side_effect = Exception("OAuthError: invalid_client: refresh token invalid")
    client._client = inner

    with pytest.raises(Exception) as exc:
        client.place_order("AAPL", "buy", 1, "market")
    assert LOGIN_COMMAND in str(exc.value)
    _assert_no_secrets(str(exc.value))


def test_place_order_http_error_does_not_dump_body():
    client = SchwabClient(token_path="/unused/token.json")
    inner = MagicMock()
    account_resp = MagicMock()
    account_resp.json.return_value = [{"hashValue": "H"}]
    inner.get_account_numbers.return_value = account_resp
    place_resp = MagicMock()
    place_resp.status_code = 400
    place_resp.headers = {}
    place_resp.text = "SECRET_ACCESS leaked body"
    inner.place_order.return_value = place_resp
    client._client = inner

    with pytest.raises(RuntimeError, match="HTTP 400") as exc:
        client.place_order("AAPL", "buy", 1, "market")
    _assert_no_secrets(str(exc.value))


def test_dry_run_prints_payload_and_never_places(monkeypatch, capsys):
    def fail_place(*_args, **_kwargs):
        raise AssertionError("place_order must not run on dry-run")

    def fail_connect(*_args, **_kwargs):
        raise AssertionError("connect must not run on dry-run")

    monkeypatch.setattr(SchwabClient, "place_order", fail_place)
    monkeypatch.setattr(SchwabClient, "connect", fail_connect)
    monkeypatch.setattr(place_order_script, "TOKEN_PATH", "C:/should-not-be-read.json")

    rc = place_order_script.main([
        "--ticker", "AAPL",
        "--side", "buy",
        "--quantity", "3",
        "--order-type", "market",
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "DRY-RUN" in out
    payload = json.loads(out.split("\n", 2)[-1])
    assert payload["orderType"] == "MARKET"
    assert payload["duration"] == "DAY"
    assert payload["orderLegCollection"][0]["quantity"] == 3
    _assert_no_secrets(out)


def test_dry_run_limit_requires_price(capsys):
    rc = place_order_script.main([
        "--ticker", "AAPL",
        "--side", "buy",
        "--quantity", "1",
        "--order-type", "limit",
    ])
    assert rc == 2
    err = capsys.readouterr().out
    assert "price" in err.lower()


def test_live_prints_only_order_id_and_status(monkeypatch, capsys):
    placed = SimpleNamespace(order_id="42", status="ACCEPTED")

    def fake_connect(self):
        return True

    def fake_place(self, **kwargs):
        assert kwargs["ticker"] == "AAPL"
        return placed

    monkeypatch.setattr(SchwabClient, "connect", fake_connect)
    monkeypatch.setattr(SchwabClient, "place_order", fake_place)
    monkeypatch.setattr(place_order_script, "TOKEN_PATH", "/unused/token.json")

    rc = place_order_script.main([
        "--ticker", "AAPL",
        "--side", "buy",
        "--quantity", "1",
        "--order-type", "market",
        "--i-mean-it",
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "order_id=42" in out
    assert "status=ACCEPTED" in out
    _assert_no_secrets(out)


def test_live_auth_failure_prints_login_command(monkeypatch, capsys):
    def fake_connect(self):
        print(f"Schwab token missing. Run {LOGIN_COMMAND}", flush=True)
        return False

    def fail_place(*_args, **_kwargs):
        raise AssertionError("place_order must not run when auth fails")

    monkeypatch.setattr(SchwabClient, "connect", fake_connect)
    monkeypatch.setattr(SchwabClient, "place_order", fail_place)
    monkeypatch.setattr(place_order_script, "TOKEN_PATH", "/unused/token.json")

    rc = place_order_script.main([
        "--ticker", "AAPL",
        "--side", "buy",
        "--quantity", "1",
        "--order-type", "market",
        "--i-mean-it",
    ])
    assert rc == 1
    out = capsys.readouterr().out
    assert LOGIN_COMMAND in out
    _assert_no_secrets(out)


def test_script_pins_repo_token_path():
    src = Path("scripts/place_order.py").read_text(encoding="utf-8")
    assert "resolve_schwab_token_path" in src
    assert "Path(__file__)" in src
    assert 'os.getenv("SCHWAB_TOKEN_PATH", "data/schwab_token.json")' not in src
    assert "data/schwab_token.json" not in src or "resolve_schwab_token_path" in src


def test_script_token_path_is_absolute_not_cwd(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SCHWAB_TOKEN_PATH", raising=False)
    reloaded = importlib.reload(place_order_script)
    from src.config import REPO_ROOT, resolve_schwab_token_path
    path = Path(resolve_schwab_token_path())
    assert path.is_absolute()
    assert path == REPO_ROOT / "data" / "schwab_token.json"
    assert tmp_path not in path.parents
    assert Path(reloaded.TOKEN_PATH).is_absolute()
    assert Path(reloaded.TOKEN_PATH) == path
    assert tmp_path not in Path(reloaded.TOKEN_PATH).parents
