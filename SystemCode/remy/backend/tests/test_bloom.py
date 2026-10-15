import random
import string

from app.bloom import BloomFilter


def _names(n: int, seed: int) -> list[str]:
    rng = random.Random(seed)
    return [
        "".join(rng.choices(string.ascii_lowercase + string.digits, k=12))
        for _ in range(n)
    ]


def test_no_false_negatives():
    """The property the sign up path depends on: anything added is always found."""
    bloom = BloomFilter(capacity=5_000, error_rate=0.01)
    added = _names(5_000, seed=1)
    for name in added:
        bloom.add(name)
    assert all(name in bloom for name in added)


def test_false_positive_rate_within_budget():
    bloom = BloomFilter(capacity=10_000, error_rate=0.01)
    for name in _names(10_000, seed=2):
        bloom.add(name)

    absent = _names(20_000, seed=99)
    false_positives = sum(1 for name in absent if name in bloom)
    rate = false_positives / len(absent)
    # Generous headroom over the configured 1%: this asserts the sizing maths is
    # right, not that the rate is exactly nominal.
    assert rate < 0.03, f"false positive rate {rate:.4f} is worse than expected"


def test_miss_is_definitive_on_empty_filter():
    bloom = BloomFilter(capacity=1_000, error_rate=0.01)
    assert "nobody" not in bloom
    bloom.add("somebody")
    assert "somebody" in bloom


def test_stats_track_fill():
    bloom = BloomFilter(capacity=1_000, error_rate=0.01)
    assert bloom.stats["fill_ratio"] == 0.0
    for name in _names(500, seed=3):
        bloom.add(name)
    assert len(bloom) == 500
    assert 0.0 < bloom.stats["fill_ratio"] < 1.0


def test_rejects_bad_sizing():
    for bad in ({"capacity": 0}, {"error_rate": 0.0}, {"error_rate": 1.0}):
        try:
            BloomFilter(**bad)
        except ValueError:
            continue
        raise AssertionError(f"expected ValueError for {bad}")
