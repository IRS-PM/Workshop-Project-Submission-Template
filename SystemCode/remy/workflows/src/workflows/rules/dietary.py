"""Halal and vegetarian evidence checks.

Halal uses the ``halal_badge`` flag from ``EDGE_FULFILLS``.
Vegetarian screens ingredient text against the animal-derived lexicon
loaded from ``rules/data/animal_derived.json``.
"""

from __future__ import annotations

import json
import re
import unicodedata
from importlib import resources
from domain.types import CheckState

# ---------------------------------------------------------------------------
# Load animal-derived lexicon at import time
# ---------------------------------------------------------------------------

_DATA_FILE = resources.files("workflows.rules.data").joinpath("animal_derived.json")
_ANIMAL_DERIVED: dict[str, list[str]] = json.loads(_DATA_FILE.read_text("utf-8"))

# Flatten into a single set for fast lookup.
_ANIMAL_TERMS: set[str] = set()
for _terms in _ANIMAL_DERIVED.values():
    for _t in _terms:
        _ANIMAL_TERMS.add(_t.lower())


# ---------------------------------------------------------------------------
# Text normalisation (shared with allergen module)
# ---------------------------------------------------------------------------


def _normalise(text: str) -> str:
    """Normalise Unicode, case, punctuation, and whitespace."""
    nfkd = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in nfkd if not unicodedata.combining(c))
    cleaned = re.sub(r"[^\w\s]", " ", stripped.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


# ---------------------------------------------------------------------------
# Halal check
# ---------------------------------------------------------------------------


def check_halal_compliance(*, halal_badge: bool | None) -> CheckState:
    """Evaluate halal compliance from the retailer badge.

    Returns
    -------
    CheckState
        ``"pass"``  — ``halal_badge is True``.
        ``"fail"``  — ``halal_badge is False``.
        ``"unknown"`` — ``halal_badge is None`` (no evidence).
    """
    if halal_badge is True:
        return "pass"
    if halal_badge is False:
        return "fail"
    return "unknown"


# ---------------------------------------------------------------------------
# Vegetarian check
# ---------------------------------------------------------------------------


def check_vegetarian_compliance(
    *,
    vegetarian_evidence: str | None,
    ingredients_text: str | None,
) -> CheckState:
    """Evaluate vegetarian compliance.

    Logic
    -----
    1. If ``vegetarian_evidence`` is explicitly ``"false"`` or similar,
       reject immediately.
    2. Screen ingredient text against the animal-derived lexicon.
    3. Blank evidence with no ingredient text → ``unknown``.

    Returns
    -------
    CheckState
        ``"pass"``    — evidence positive and no animal-derived match.
        ``"fail"``    — evidence negative or animal-derived match.
        ``"unknown"`` — insufficient data.
    """
    # Explicit negative evidence.
    if vegetarian_evidence is not None:
        lower_ev = vegetarian_evidence.strip().lower()
        if lower_ev in {"false", "no", "non-vegetarian", "not vegetarian"}:
            return "fail"

    # No ingredient text and no positive evidence → unknown.
    if not ingredients_text:
        if vegetarian_evidence and vegetarian_evidence.strip().lower() in {
            "true",
            "yes",
            "vegetarian",
        }:
            return "pass"
        return "unknown"

    # Screen ingredient text against animal-derived lexicon.
    normalised = _normalise(ingredients_text)
    for term in _ANIMAL_TERMS:
        pattern = re.compile(r"\b" + re.escape(term) + r"\b")
        if pattern.search(normalised):
            return "fail"

    # Positive evidence or clean ingredient list.
    if vegetarian_evidence and vegetarian_evidence.strip().lower() in {
        "true",
        "yes",
        "vegetarian",
    }:
        return "pass"

    # Ingredient list present and clean, but no explicit evidence.
    return "unknown"
