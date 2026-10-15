from __future__ import annotations

import time
from dataclasses import dataclass

import jwt
from jwt import ExpiredSignatureError, InvalidTokenError

ALGORITHM = "HS256"


class TokenError(Exception):
    """The token is unusable: malformed, wrong signature, or too old to renew."""


@dataclass(frozen=True, slots=True)
class Token:
    value: str
    expires_at: int


@dataclass(frozen=True, slots=True)
class TokenConfig:
    secret: str
    ttl_seconds: int
    renew_within_seconds: int
    expired_grace_seconds: int


def issue(username: str, config: TokenConfig) -> Token:
    now = int(time.time())
    expires_at = now + config.ttl_seconds
    value = jwt.encode(
        {"sub": username, "iat": now, "exp": expires_at},
        config.secret,
        algorithm=ALGORITHM,
    )
    return Token(value=value, expires_at=expires_at)


def decode(token: str, config: TokenConfig, *, allow_expired: bool = False) -> dict:
    """Verify signature and claims.

    `allow_expired` skips only the expiry check - the signature is still
    verified, so an expired token cannot be forged. It exists for the refresh
    endpoint, which has to read a token that has already lapsed.
    """
    try:
        return jwt.decode(
            token,
            config.secret,
            algorithms=[ALGORITHM],
            options={"verify_exp": not allow_expired, "require": ["sub", "exp"]},
        )
    except ExpiredSignatureError:
        raise TokenError("Token has expired.") from None
    except InvalidTokenError as error:
        raise TokenError(f"Invalid token: {error}") from None


def username_of(token: str, config: TokenConfig) -> str:
    """For the middleware: the subject of a currently valid token."""
    claims = decode(token, config)
    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject:
        raise TokenError("Token has no subject.")
    return subject


def renew(token: str, config: TokenConfig) -> tuple[Token, bool]:
    """Return the token to use next, and whether a new one was minted.

    Three cases, in order:

    * Plenty of life left - hand the same token back untouched, so a client can
      call this on every app open without churning tokens.
    * Inside the renewal window (default: under 30 minutes left, i.e. 11h30
      into a 12h token) - mint a fresh one.
    * Already expired - mint a fresh one, but only if it lapsed within
      `expired_grace_seconds`. Past that the user has to sign in again,
      otherwise a leaked token would be renewable forever and the 12 hour
      lifetime would mean nothing.
    """
    claims = decode(token, config, allow_expired=True)

    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject:
        raise TokenError("Token has no subject.")

    expires_at = int(claims["exp"])
    now = int(time.time())
    remaining = expires_at - now

    if remaining > config.renew_within_seconds:
        return Token(value=token, expires_at=expires_at), False

    if remaining <= 0:
        expired_for = -remaining
        if expired_for > config.expired_grace_seconds:
            raise TokenError(
                "Token expired too long ago to refresh. Sign in again."
            )

    return issue(subject, config), True
