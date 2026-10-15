import re
import unicodedata
import inflect
from difflib import SequenceMatcher
from .exceptions import AmbiguousIngredient, UnresolvableIngredient
from .synonyms import ALIASES

p = inflect.engine()

def _clean(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(c for c in value if not unicodedata.combining(c)).lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value)).strip()


def normalize_name(value: str) -> str:
    return " ".join(p.singular_noun(w) or w for w in _clean(value).split())


def _pipeline_singular(value: str) -> str:
    # Same rule as the end of recipe_normalize in data-preparation/macros/recipe_normalization.sql,
    # which wrote the FoodConcept keys: "tomatoes" -> "tomatoe", "bay leaves" -> "bay leave".
    value = re.sub(r"\b([a-z]{4,})ies\b", r"\1y", value)
    return re.sub(r"\b([a-z]{5,})s\b", r"\1", value)


def singular_forms(name: str) -> list[str]:
    """Singular spellings of an ingredient name, best first.

    The first is the proper singular. The others are how the data pipeline stores the
    same food, so "bay leaves" and "bay leaf" both find the key "bay leave".
    """
    singular = normalize_name(name)
    if not singular:
        return []
    *head, last = singular.split()
    plural = " ".join([*head, p.plural_noun(last) or last])
    return list(dict.fromkeys([singular, _pipeline_singular(_clean(name)), _pipeline_singular(plural)]))


# Aliases are compared with normalized names and keys, so normalize both sides too.
_ALIASES = {normalize_name(name): normalize_name(target) for name, target in ALIASES.items()}


def search_terms(name: str) -> list[str]:
    """Every spelling to look up for an ingredient: its singular forms, then its alias's."""
    forms = singular_forms(name)
    alias = _ALIASES.get(forms[0]) if forms else None
    return list(dict.fromkeys(forms + (singular_forms(alias) if alias else [])))


def _token_score(a: str, b: str) -> float:
    sa, sb = set(a.split()), set(b.split())
    token = len(sa & sb) / max(len(sa | sb), 1)
    return max(SequenceMatcher(None, a, b).ratio(), token)


def resolve(name: str, canonical_keys: list[str], fuzzy_candidates: list[str] | None = None) -> tuple[str, str, float | None]:
    forms = singular_forms(name)
    normalized = forms[0] if forms else ""
    normalized_keys = {normalize_name(k): k for k in canonical_keys}
    for form in forms:
        if form in normalized_keys:
            return normalized_keys[form], "exact", 1.0
    alias = _ALIASES.get(normalized)
    for form in singular_forms(alias) if alias else []:
        if form in normalized_keys:
            return normalized_keys[form], "alias", 1.0
    candidates = fuzzy_candidates if fuzzy_candidates is not None else canonical_keys
    scored = sorted(((key, _token_score(normalized, normalize_name(key))) for key in candidates),
                    key=lambda x: (-x[1], x[0]))[:20]
    if not scored:
        raise UnresolvableIngredient(f"Ingredient '{name}' could not be resolved")
    if scored[0][1] < 0.86 or (len(scored) > 1 and scored[0][1] - scored[1][1] < 0.05):
        raise AmbiguousIngredient(f"Ingredient '{name}' is ambiguous", [{"field": "name", "issue": str(scored[:3])}])
    return scored[0][0], "fuzzy", scored[0][1]
