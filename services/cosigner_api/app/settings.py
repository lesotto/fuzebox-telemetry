"""Runtime configuration for the Cosigner API.

Every config value has an env-var override and a sensible default.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    """Cosigner API settings.

    Example:
        >>> s = Settings(database_url="postgresql+asyncpg://u:p@h/d", signing_provider="static")
        >>> s.signing_provider
        'static'
    """

    database_url: str
    signing_provider: str  # "static" | "kms" | "vault"
    static_signing_key: str
    kms_key_id: str | None
    kms_region: str | None
    vault_addr: str | None
    vault_token: str | None
    vault_key: str | None
    allow_static_signing_in_prod: bool
    environment: str  # "dev" | "staging" | "prod"
    request_timeout_seconds: float


def _bool(env: str, default: bool) -> bool:
    val = os.getenv(env)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load settings from the environment. Cached per-process."""

    return Settings(
        database_url=os.getenv(
            "FUZEBOX_DATABASE_URL",
            "postgresql+asyncpg://fuzebox:fuzebox@localhost:5432/fuzebox",
        ),
        signing_provider=os.getenv("FUZEBOX_SIGNING_PROVIDER", "static"),
        static_signing_key=os.getenv(
            "FUZEBOX_STATIC_SIGNING_KEY", "dev-static-signing-key-do-not-use-in-prod"
        ),
        kms_key_id=os.getenv("FUZEBOX_KMS_KEY_ID"),
        kms_region=os.getenv("FUZEBOX_KMS_REGION"),
        vault_addr=os.getenv("FUZEBOX_VAULT_ADDR"),
        vault_token=os.getenv("FUZEBOX_VAULT_TOKEN"),
        vault_key=os.getenv("FUZEBOX_VAULT_KEY"),
        allow_static_signing_in_prod=_bool("FUZEBOX_ALLOW_STATIC_SIGNING", False),
        environment=os.getenv("FUZEBOX_ENVIRONMENT", "dev"),
        request_timeout_seconds=float(os.getenv("FUZEBOX_REQUEST_TIMEOUT", "5")),
    )


def reset_settings_cache() -> None:
    """Clear the settings cache. For tests only."""

    get_settings.cache_clear()
