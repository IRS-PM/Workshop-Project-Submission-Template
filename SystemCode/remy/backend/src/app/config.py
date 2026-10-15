from __future__ import annotations

import logging
import os
import secrets
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from app.tokens import TokenConfig

_log = logging.getLogger(__name__)

HALF_DAY_SECONDS = 12 * 60 * 60
MIN_SECRET_BYTES = 32

# src/app/config.py -> src/app -> src -> backend/. Anchored to this file rather
# than the working directory, because the app is started from several places
# (backend/ by hand, SystemCode/ by `uv run`, / in the container) and a
# cwd-relative lookup silently finds nothing from most of them.
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


@dataclass(frozen=True, slots=True)
class CookieConfig:
    name: str
    secure: bool
    samesite: str


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    database_password: str | None
    cors_origins: tuple[str, ...]
    bloom_capacity: int
    bloom_error_rate: float
    tokens: TokenConfig
    cookie: CookieConfig


def _jwt_secret() -> str:
    secret = os.environ.get("REMY_JWT_SECRET", "").strip()
    if secret:
        if len(secret.encode()) < MIN_SECRET_BYTES:
            _log.warning(
                "REMY_JWT_SECRET is only %d bytes. Use at least %d "
                "(`openssl rand -base64 48`).",
                len(secret.encode()),
                MIN_SECRET_BYTES,
            )
        return secret

    _log.warning(
        "REMY_JWT_SECRET is not set. Generated a random key for this process; "
        "all tokens become invalid when it restarts, and separate workers will "
        "reject each other's tokens. Set REMY_JWT_SECRET for anything real."
    )
    return secrets.token_urlsafe(48)


def load_settings() -> Settings:
    # override=False so a real environment variable always beats the file: a
    # deployment injects its own config, and a stray .env in the image must not
    # quietly replace it. Missing file is not an error - production has no .env.
    load_dotenv(ENV_FILE, override=False)

    return Settings(
        database_url=os.environ.get(
            "REMY_DATABASE_URL",
            "postgresql://localhost:5432/remy_main",
        ),
        # Kept out of the URL so it can live in .env on its own. Overrides any
        # password in REMY_DATABASE_URL when set.
        database_password=os.environ.get("POSTGRES_PASSWORD") or None,
        cors_origins=tuple(
            origin.strip()
            for origin in os.environ.get(
                "REMY_CORS_ORIGINS", "http://localhost:3000,http://localhost:3100"
            ).split(",")
            if origin.strip()
        ),
        bloom_capacity=int(os.environ.get("REMY_BLOOM_CAPACITY", "100000")),
        bloom_error_rate=float(os.environ.get("REMY_BLOOM_ERROR_RATE", "0.01")),
        tokens=TokenConfig(
            secret=_jwt_secret(),
            ttl_seconds=int(os.environ.get("REMY_JWT_TTL_SECONDS", HALF_DAY_SECONDS)),
            # 30 minutes: a token that is 11h30 into its 12h life renews.
            renew_within_seconds=int(
                os.environ.get("REMY_JWT_RENEW_WITHIN_SECONDS", 30 * 60)
            ),
            # How long after expiry a token can still be traded for a new one.
            # 0 disables it, so an expired token always means signing in again.
            expired_grace_seconds=int(
                os.environ.get("REMY_JWT_EXPIRED_GRACE_SECONDS", 7 * 24 * 60 * 60)
            ),
        ),
        cookie=CookieConfig(
            name=os.environ.get("REMY_COOKIE_NAME", "remy_session"),
            secure=os.environ.get("REMY_COOKIE_SECURE", "false").lower() == "true",
            samesite=os.environ.get("REMY_COOKIE_SAMESITE", "strict").lower(),
        ),
    )
