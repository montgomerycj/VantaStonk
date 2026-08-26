"""Environment-backed settings for VantaStonk v2 subsystems."""

import os
from dataclasses import dataclass
from pathlib import Path

# src/config.py → repo root. Auth files resolve from here, never process cwd.
REPO_ROOT = Path(__file__).resolve().parent.parent


def _bool(val: str) -> bool:
    return str(val).lower() in ("1", "true", "yes", "on")


def resolve_schwab_token_path(raw: str | None = None) -> str:
    """Absolute Schwab token path, rooted at the repo unless already absolute.

    Relative values (the default ``data/schwab_token.json``, or a relative
    ``SCHWAB_TOKEN_PATH``) join to the repo root so a leftover process cwd
    cannot write or read another project's token.
    """
    value = raw if raw is not None else os.getenv("SCHWAB_TOKEN_PATH")
    if not value:
        value = "data/schwab_token.json"
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = REPO_ROOT / path
    return str(path)


@dataclass
class Settings:
    use_real_prompt_pulse: bool
    openai_api_key: str
    anthropic_api_key: str
    xai_api_key: str
    schwab_app_key: str
    schwab_app_secret: str
    schwab_token_path: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            use_real_prompt_pulse=_bool(os.getenv("USE_REAL_PROMPT_PULSE", "false")),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            xai_api_key=os.getenv("XAI_API_KEY", ""),
            schwab_app_key=os.getenv("SCHWAB_APP_KEY", ""),
            schwab_app_secret=os.getenv("SCHWAB_APP_SECRET", ""),
            schwab_token_path=resolve_schwab_token_path(),
        )
