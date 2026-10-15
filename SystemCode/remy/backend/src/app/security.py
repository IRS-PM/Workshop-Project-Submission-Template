from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

# Argon2id with the library defaults, which track the OWASP guidance. The
# resulting PHC string carries its own salt and parameters, which is why
# app_user has no separate salt column.
_hasher = PasswordHasher()

# Verified against when the username does not exist, so that a miss costs the
# same wall-clock time as a wrong password. Without it, response latency alone
# tells an attacker which usernames are registered.
_DUMMY_HASH = _hasher.hash("a password that is never correct")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False
    return True


def waste_time() -> None:
    """Burn one Argon2 verification so that a missing user is not faster."""
    try:
        _hasher.verify(_DUMMY_HASH, "wrong")
    except VerifyMismatchError:
        pass


def needs_rehash(password_hash: str) -> bool:
    """True when the stored hash predates the current cost parameters."""
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return False
