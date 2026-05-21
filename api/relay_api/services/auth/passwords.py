"""argon2id password hashing.

Lifted from Powerloom verbatim — pure primitive, no domain coupling.

argon2-cffi's PHC encoded hash carries params in the string itself
(`$argon2id$v=19$m=65536,t=3,p=4$…`) so verify is self-contained and
rehash-on-login is trivial when we bump params in the future.

Parameter choice (OWASP cheat sheet, Apr 2026):
    memory_cost = 65536  (64 MiB)
    time_cost   = 3
    parallelism = 4
Gives ~0.1s on a typical small instance — intentional. Attackers pay the same.
"""
from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

# Singleton — argon2-cffi's PasswordHasher is thread-safe and holds no
# per-call state. Reusing avoids re-reading defaults every hash.
_hasher = PasswordHasher(
    memory_cost=65536,  # 64 MiB
    time_cost=3,
    parallelism=4,
)


class InvalidPassword(Exception):
    """Raised by `verify_password` when the hash does not match. Routes
    translate to 401 without revealing which field was wrong."""


def hash_password(raw: str) -> str:
    """Hash `raw` with argon2id. Returns the PHC-encoded string."""
    return _hasher.hash(raw)


def verify_password(raw: str, *, hashed: str) -> None:
    """Raise InvalidPassword if the password does not match. Silent on
    success — callers never need the return value."""
    try:
        _hasher.verify(hashed, raw)
    except VerifyMismatchError as e:
        raise InvalidPassword("password does not match") from e
    except Exception as e:
        # Malformed hash, unsupported algo, etc. Treat as mismatch.
        raise InvalidPassword(f"password verify failed: {e}") from e


def needs_rehash(hashed: str) -> bool:
    """True when the stored hash was produced with older parameters than
    the current defaults. Call after a successful verify and re-hash if
    True — transparent parameter rollover."""
    return _hasher.check_needs_rehash(hashed)
