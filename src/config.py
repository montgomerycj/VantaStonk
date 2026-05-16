"""Environment-backed settings for VantaStonk v2 subsystems."""

import os
from dataclasses import dataclass


def _bool(val: str) -> bool:
    return str(val).lower() in ("1", "true", "yes", "on")


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
            schwab_token_path=os.getenv("SCHWAB_TOKEN_PATH", "data/schwab_token.json"),
        )
