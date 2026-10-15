from __future__ import annotations

import hashlib
import math


class BloomFilter:
    """A fixed-size Bloom filter over UTF-8 strings.

    The error is one-sided: a miss is *definitive*, a hit is only probable.
    That asymmetry is the entire reason this exists on the sign up path - a miss
    means the username is certainly free, so the request can skip asking the
    database whether it is taken. A hit has to go and check, because it might be
    one of the false positives.

    Two consequences worth remembering:

    * There is no remove(). Bits are shared between entries, so clearing one
      entry's bits would punch holes in others. A deleted account therefore
      leaves a permanent false positive behind until the filter is rebuilt.
    * The unique constraint on app_user.username, not this filter, is what
      actually prevents duplicates.
    """

    __slots__ = ("_bits", "_size", "_hashes", "_added")

    def __init__(self, capacity: int = 100_000, error_rate: float = 0.01) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        if not 0.0 < error_rate < 1.0:
            raise ValueError("error_rate must be between 0 and 1 exclusive")

        # Optimal sizing for a target false positive rate p over n items:
        #   m = -n ln(p) / (ln 2)^2 bits,  k = (m/n) ln 2 hash functions.
        self._size = max(8, math.ceil(-capacity * math.log(error_rate) / (math.log(2) ** 2)))
        self._hashes = max(1, round((self._size / capacity) * math.log(2)))
        self._bits = bytearray((self._size + 7) // 8)
        self._added = 0

    def _offsets(self, value: str):
        """Kirsch-Mitzenmacher: k indexes derived from one 128-bit digest.

        Cheaper than running k separate hashes, with the same false positive
        behaviour. h2 is forced odd so that, as i climbs, the stride keeps
        landing on fresh positions instead of cycling through a few.
        """
        digest = hashlib.blake2b(value.encode("utf-8"), digest_size=16).digest()
        h1 = int.from_bytes(digest[:8], "big")
        h2 = int.from_bytes(digest[8:], "big") | 1
        for i in range(self._hashes):
            yield (h1 + i * h2) % self._size

    def add(self, value: str) -> None:
        for offset in self._offsets(value):
            self._bits[offset >> 3] |= 1 << (offset & 7)
        self._added += 1

    def __contains__(self, value: str) -> bool:
        """False means certainly absent. True means probably present."""
        return all(
            self._bits[offset >> 3] >> (offset & 7) & 1
            for offset in self._offsets(value)
        )

    def __len__(self) -> int:
        return self._added

    @property
    def stats(self) -> dict[str, float | int]:
        set_bits = sum(byte.bit_count() for byte in self._bits)
        load = set_bits / self._size
        return {
            "bits": self._size,
            "hash_functions": self._hashes,
            "added": self._added,
            "fill_ratio": round(load, 4),
            # Actual false positive probability at the current fill, which is
            # what matters operationally - the configured rate is only the
            # value at full capacity.
            "false_positive_rate": round(load**self._hashes, 6),
        }
