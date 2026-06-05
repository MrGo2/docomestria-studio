"""Environment configuration for docomestria-studio."""

from __future__ import annotations

import os
from dataclasses import dataclass

try:  # pragma: no cover - optional convenience
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover
    pass


@dataclass(frozen=True)
class StudioConfig:
    """Runtime configuration loaded from environment variables.

    Notes
    -----
    `openrouter_api_key` is intentionally optional so the app can boot and
    render a friendly setup-required page when missing.
    """

    openrouter_api_key: str | None
    openrouter_model: str
    upload_max_mb: int
    host: str
    port: int
    debug: bool
    session_max_age_minutes: int

    @property
    def is_ready(self) -> bool:
        """True when all required configuration is present."""
        return bool(self.openrouter_api_key)


def load_config() -> StudioConfig:
    """Read configuration from environment variables."""
    return StudioConfig(
        openrouter_api_key=os.environ.get("OPENROUTER_API_KEY"),
        openrouter_model=os.environ.get(
            "OPENROUTER_MODEL", "google/gemini-2.5-flash-lite"
        ),
        upload_max_mb=int(os.environ.get("STUDIO_UPLOAD_MAX_MB", "20")),
        host=os.environ.get("STUDIO_HOST", "127.0.0.1"),
        port=int(os.environ.get("STUDIO_PORT", "5050")),
        debug=os.environ.get("STUDIO_DEBUG", "false").lower() in ("1", "true", "yes"),
        session_max_age_minutes=int(os.environ.get("STUDIO_SESSION_TTL_MIN", "60")),
    )


__all__ = ["StudioConfig", "load_config"]
