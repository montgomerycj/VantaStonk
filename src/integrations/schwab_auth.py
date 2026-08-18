"""
Schwab auth hygiene — pasteable login URL + token-age status.

Schwab refresh tokens die at 7 days. That is a Schwab hard limit; this
module only makes login pasteable and death obvious. It never prints
token secrets (access/refresh values).
"""

from __future__ import annotations

import json
import sys
import time
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal, Optional, TextIO, Union

LOGIN_COMMAND = "python scripts/schwab_login.py"
AUTH_URL_PATH = Path("data/schwab_auth_url.txt")

WARN_AFTER_DAYS = 5
DEAD_AFTER_DAYS = 7
SECONDS_PER_DAY = 86400.0

TokenStatus = Literal["ok", "warn", "dead", "missing"]
PathLike = Union[str, Path]


class SchwabAuthError(Exception):
    """Token missing, refresh dead, or Schwab rejected the refresh token."""

    def __init__(self, message: str, status: TokenStatus = "dead"):
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class TokenAge:
    status: TokenStatus
    age_days: Optional[float]
    path: Path
    message: str


def inspect_token(token_path: PathLike, now: Optional[float] = None) -> TokenAge:
    """
    Classify a Schwab token file by age.

    Reads ``creation_timestamp`` from the JSON wrapper schwab-py writes,
    falling back to file mtime. Never returns or embeds token secrets.
    """
    path = Path(token_path)
    if not path.exists():
        return TokenAge(
            status="missing",
            age_days=None,
            path=path,
            message=f"Schwab token missing. Run {LOGIN_COMMAND}",
        )

    created = _read_creation_time(path)
    clock = time.time() if now is None else now
    age_days = (clock - created) / SECONDS_PER_DAY

    if age_days >= DEAD_AFTER_DAYS:
        return TokenAge(
            status="dead",
            age_days=age_days,
            path=path,
            message=(
                f"Schwab refresh token is dead ({age_days:.1f}d >= {DEAD_AFTER_DAYS}d). "
                f"Run {LOGIN_COMMAND}"
            ),
        )
    if age_days >= WARN_AFTER_DAYS:
        return TokenAge(
            status="warn",
            age_days=age_days,
            path=path,
            message=(
                f"Schwab token is {age_days:.1f}d old "
                f"(warn at {WARN_AFTER_DAYS}d, dead at {DEAD_AFTER_DAYS}d). "
                f"Run {LOGIN_COMMAND} soon."
            ),
        )
    return TokenAge(
        status="ok",
        age_days=age_days,
        path=path,
        message=f"Schwab token age: {age_days:.1f}d (ok)",
    )


def require_usable_token(
    token_path: PathLike,
    now: Optional[float] = None,
    stream: Optional[TextIO] = None,
) -> TokenAge:
    """Print token-age status. Raise SchwabAuthError if missing or dead."""
    age = inspect_token(token_path, now=now)
    dest = sys.stdout if stream is None else stream
    print(age.message, file=dest, flush=True)
    if age.status in ("missing", "dead"):
        raise SchwabAuthError(age.message, status=age.status)
    return age


def is_refresh_rejected(exc: BaseException) -> bool:
    """True when schwab-py / authlib reports an invalid refresh token."""
    text = str(exc).lower()
    name = type(exc).__name__.lower()
    haystack = f"{name} {text}"
    if "invalid_client" in haystack:
        return True
    if "refresh token" in haystack and "invalid" in haystack:
        return True
    return False


def refresh_rejected_error(exc: BaseException) -> SchwabAuthError:
    return SchwabAuthError(
        f"Schwab refresh token rejected ({type(exc).__name__}). Run {LOGIN_COMMAND}",
        status="dead",
    )


def publish_auth_url(
    url: str,
    dest: PathLike = AUTH_URL_PATH,
    stdout: Optional[TextIO] = None,
    stderr: Optional[TextIO] = None,
) -> Path:
    """
    Print the OAuth authorize URL prominently, then write it to ``dest``.

    Call this BEFORE any browser-open attempt. Failure to write the file
    must not hide the URL already printed.
    """
    out = sys.stdout if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr
    path = Path(dest)
    banner = (
        "\n"
        "============================================================\n"
        "  Schwab authorization URL (paste into a browser):\n"
        "------------------------------------------------------------\n"
        f"  {url}\n"
        "------------------------------------------------------------\n"
        f"  Also saved to {path}\n"
        "  If the browser does not open, paste the URL above.\n"
        "============================================================\n"
    )
    print(banner, file=out, flush=True)
    print(banner, file=err, flush=True)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(url + "\n", encoding="utf-8")
    except OSError as exc:
        print(f"Could not write {path}: {exc}", file=out, flush=True)
    return path


def try_open_browser(url: str, opener: Optional[Callable[[str], bool]] = None) -> bool:
    """Best-effort browser open. Never raises. Failure does not hide the URL."""
    open_fn = webbrowser.open if opener is None else opener
    try:
        return bool(open_fn(url))
    except Exception as exc:
        print(
            f"Browser launch failed ({exc}). Paste the authorization URL above.",
            flush=True,
        )
        return False


def install_safe_browser_open(
    publish: Optional[Callable[[str], None]] = None,
) -> None:
    """
    Make schwab-py's webbrowser.get(...).open(...) failure-safe.

    ``client_from_login_flow`` calls ``webbrowser.get().open()``, not
    ``webbrowser.open()``. If get() or open() raises, schwab-py never
    waits for the OAuth callback — so a failed auto-launch would abort
    paste-the-URL as well. Swallow those errors after the URL is public.
    """
    original_get = webbrowser.get

    def safe_get(using=None):
        try:
            controller = original_get(using)
        except Exception:
            controller = _DummyBrowser()
        original_open = controller.open

        def safe_open(url, *args, **kwargs):
            if publish is not None:
                publish(url)
            try:
                return bool(original_open(url, *args, **kwargs))
            except Exception as exc:
                print(
                    f"Browser launch failed ({exc}). Paste the authorization URL above.",
                    flush=True,
                )
                return False

        controller.open = safe_open
        return controller

    webbrowser.get = safe_get  # type: ignore[assignment]


def prepare_login_flow(auth_module, api_key: str, callback_url: str, dest: PathLike = AUTH_URL_PATH):
    """
    Print/save the authorize URL, then pin that same OAuth context for
    ``client_from_login_flow`` so state matches.

    Browser open is left to schwab-py (after its callback server is up).
    Opening earlier races the redirect listener.
    """
    auth_context = auth_module.get_auth_context(api_key, callback_url)
    url = auth_context.authorization_url
    publish_auth_url(url, dest)
    auth_module.get_auth_context = lambda *args, **kwargs: auth_context
    install_safe_browser_open()
    return auth_context


class _DummyBrowser:
    def open(self, url, *args, **kwargs):
        return False


def _read_creation_time(path: Path) -> float:
    """creation_timestamp from the token wrapper, else mtime. No secrets."""
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        timestamp = data.get("creation_timestamp")
        if timestamp is not None:
            return float(timestamp)
    except (OSError, json.JSONDecodeError, TypeError, ValueError, AttributeError):
        pass
    return path.stat().st_mtime
