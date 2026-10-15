import dataclasses
import time

import jwt
import pytest

from app import tokens
from app.tokens import TokenConfig, TokenError

HALF_DAY = 12 * 60 * 60

CONFIG = TokenConfig(
    secret="test-secret-long-enough-for-hs256-hmac",
    ttl_seconds=HALF_DAY,
    renew_within_seconds=30 * 60,
    expired_grace_seconds=7 * 24 * 60 * 60,
)


def _token_aged(seconds_old: int, config: TokenConfig = CONFIG, sub: str = "tung") -> str:
    """A token that was issued `seconds_old` seconds ago, signed for real."""
    issued = int(time.time()) - seconds_old
    return jwt.encode(
        {"sub": sub, "iat": issued, "exp": issued + config.ttl_seconds},
        config.secret,
        algorithm=tokens.ALGORITHM,
    )


def test_issued_token_lasts_twelve_hours():
    token = tokens.issue("tung", CONFIG)
    assert abs(token.expires_at - (int(time.time()) + HALF_DAY)) <= 2
    assert tokens.username_of(token.value, CONFIG) == "tung"


def test_fresh_token_is_returned_unchanged():
    """Called early, refresh is a no-op so clients can poll it on every open."""
    original = _token_aged(60)
    token, minted = tokens.renew(original, CONFIG)
    assert minted is False
    assert token.value == original


def test_token_at_11h30_is_renewed():
    """The case the 30 minute window exists for."""
    token, minted = tokens.renew(_token_aged(11 * 3600 + 30 * 60 + 1), CONFIG)
    assert minted is True
    assert tokens.username_of(token.value, CONFIG) == "tung"


def test_token_just_inside_the_window_is_not_renewed():
    # 11h29 old: 31 minutes left, one minute more than the window.
    _, minted = tokens.renew(_token_aged(11 * 3600 + 29 * 60), CONFIG)
    assert minted is False


def test_expired_token_within_grace_is_renewed():
    token, minted = tokens.renew(_token_aged(HALF_DAY + 3600), CONFIG)
    assert minted is True
    assert tokens.username_of(token.value, CONFIG) == "tung"


def test_expired_token_past_grace_is_refused():
    too_old = HALF_DAY + CONFIG.expired_grace_seconds + 60
    with pytest.raises(TokenError, match="expired too long ago"):
        tokens.renew(_token_aged(too_old), CONFIG)


def test_zero_grace_refuses_any_expired_token():
    config = dataclasses.replace(CONFIG, expired_grace_seconds=0)
    with pytest.raises(TokenError):
        tokens.renew(_token_aged(HALF_DAY + 5, config), config)


def test_expired_token_is_rejected_for_normal_use():
    """Refresh tolerates expiry; the middleware path must not."""
    with pytest.raises(TokenError, match="expired"):
        tokens.username_of(_token_aged(HALF_DAY + 60), CONFIG)


def test_signature_is_verified_even_when_expiry_is_ignored():
    """An attacker cannot forge an expired token and trade it for a live one."""
    forged = jwt.encode(
        {"sub": "admin", "iat": 0, "exp": 1},
        "not-the-real-secret-but-long-enough-to-sign",
        algorithm=tokens.ALGORITHM,
    )
    with pytest.raises(TokenError, match="Invalid token"):
        tokens.renew(forged, CONFIG)


def test_none_algorithm_is_rejected():
    """The classic JWT downgrade: an unsigned token must not be accepted."""
    unsigned = jwt.encode({"sub": "admin", "exp": int(time.time()) + 999}, key="", algorithm="none")
    with pytest.raises(TokenError):
        tokens.username_of(unsigned, CONFIG)


def test_token_without_subject_is_rejected():
    no_sub = jwt.encode(
        {"iat": 0, "exp": int(time.time()) + 999}, CONFIG.secret, algorithm=tokens.ALGORITHM
    )
    with pytest.raises(TokenError):
        tokens.username_of(no_sub, CONFIG)
