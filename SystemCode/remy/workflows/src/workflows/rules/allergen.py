"""Allergen matching against controlled aliases and precautionary patterns.

The canonical allergen keys come from the data-preparation contract test
(``mart_allergen_screening_contract.sql``).  Aliases are loaded at import
time from ``rules/data/allergen_aliases.json``.
"""

from __future__ import annotations

import json
import re
import unicodedata
from importlib import resources
from domain.types import CheckState

# ---------------------------------------------------------------------------
# Load allergen alias dictionary at import time
# ---------------------------------------------------------------------------

_ALIAS_FILE = resources.files("workflows.rules.data").joinpath("allergen_aliases.json")
_ALLERGEN_ALIASES: dict[str, list[str]] = json.loads(_ALIAS_FILE.read_text("utf-8"))

# Pre-compile a flat lookup: alias_term → canonical_key
_ALIAS_LOOKUP: dict[str, str] = {}
for _key, _aliases in _ALLERGEN_ALIASES.items():
    for _alias in _aliases:
        _ALIAS_LOOKUP[_alias.lower()] = _key

# Precautionary statement patterns (case-insensitive).
_PRECAUTIONARY_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bmay\s+contain\b", re.IGNORECASE),
    re.compile(r"\bprocessed\s+in\s+a\s+facility\b", re.IGNORECASE),
    re.compile(r"\bhandles\b", re.IGNORECASE),
    re.compile(r"\bmade\s+on\s+shared\s+equipment\b", re.IGNORECASE),
    re.compile(r"\bcross[\s-]?contaminat", re.IGNORECASE),
]


# ---------------------------------------------------------------------------
# Text normalisation
# ---------------------------------------------------------------------------


def normalize_text(text: str) -> str:
    """Normalise Unicode, case, punctuation, and whitespace."""
    # NFKD → strip combining marks → lowercase
    nfkd = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in nfkd if not unicodedata.combining(c))
    # Replace punctuation with spaces, collapse whitespace
    cleaned = re.sub(r"[^\w\s]", " ", stripped.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve_allergen_key(user_term: str) -> str | None:
    """Map a user-supplied allergen name to a canonical key, or ``None``."""
    normalised = normalize_text(user_term)
    return _ALIAS_LOOKUP.get(normalised)


def check_allergen(
    *,
    allergen_key: str,
    ingredients_text: str | None,
    precautionary_text: str | None,
) -> CheckState:
    """Check a single allergen against ingredient text and evidence.

    Returns
    -------
    CheckState
        ``"fail"`` if the allergen is detected (declared or precautionary),
        ``"unknown"`` if ingredient data is missing or incomplete,
        ``"pass"`` if no match is found.
    """
    aliases = _ALLERGEN_ALIASES.get(allergen_key, [allergen_key])

    # Missing ingredient declaration → cannot infer safety.
    if not ingredients_text and not precautionary_text:
        return "unknown"

    combined = ""
    if ingredients_text:
        combined += ingredients_text
    if precautionary_text:
        combined += " " + precautionary_text

    normalised = normalize_text(combined)

    # Whole-token match against each alias.
    for alias in aliases:
        pattern = re.compile(r"\b" + re.escape(normalize_text(alias)) + r"\b")
        if pattern.search(normalised):
            return "fail"

    # Precautionary pattern + allergen alias co-occurrence.
    for prec_pattern in _PRECAUTIONARY_PATTERNS:
        if prec_pattern.search(combined):
            # Re-check if any alias appears in the precautionary context.
            for alias in aliases:
                pattern = re.compile(r"\b" + re.escape(normalize_text(alias)) + r"\b")
                if pattern.search(normalised):
                    return "fail"

    return "pass"


def check_allergen_compliance(
    *,
    allergens: list[str],
    declared_ingredients_text: str | None,
    precautionary_text: str | None,
) -> list[tuple[str, CheckState]]:
    """Check all user-required allergens against a food candidate.

    Parameters
    ----------
    allergens
        Canonical allergen keys from the user's constraints.
    declared_ingredients_text
        The food's declared ingredient list (may be ``None``).
    precautionary_text
        Pre-screened allergen evidence from ``EDGE_FULFILLS`` (may be ``None``).

    Returns
    -------
    list[tuple[str, CheckState]]
        One ``(allergen_key, state)`` pair per required allergen.
    """
    return [
        (
            allergen_key,
            check_allergen(
                allergen_key=allergen_key,
                ingredients_text=declared_ingredients_text,
                precautionary_text=precautionary_text,
            ),
        )
        for allergen_key in allergens
    ]
