from collections import defaultdict
from typing import Any
from .models import FoodFacts, NutrientProfile, RetailSKU

QUERY_A = """
UNWIND $normalized_names AS normalized_name
MATCH (fc:FoodConcept)
WHERE fc.canonical_key = normalized_name
   OR toLower(replace(fc.canonical_key, '_', ' ')) CONTAINS normalized_name
RETURN normalized_name, fc.canonical_key AS canonical_key
"""

QUERY_A2 = """
UNWIND $unresolved AS unresolved_name
MATCH (fc:FoodConcept)
WHERE toLower(fc.canonical_key) STARTS WITH unresolved_name
   OR toLower(fc.canonical_key) CONTAINS unresolved_name
RETURN unresolved_name, fc.canonical_key AS canonical_key
LIMIT 20
"""

QUERY_B = """
UNWIND $canonical_keys AS canonical_key
MATCH (fc:FoodConcept {canonical_key: canonical_key})
OPTIONAL MATCH (f:Food)-[ful:FULFILLS {approval_status: 'accepted'}]->(fc)
WITH canonical_key, fc, f, ful
CALL {
  WITH f
  OPTIONAL MATCH (f)-[hc:HAS_COMPONENT]->(component:Component)
  RETURN collect(DISTINCT {grams_per_tbsp: coalesce(hc.grams_per_tbsp, component.grams_per_tbsp),
                           grams_per_piece: coalesce(hc.grams_per_piece, component.grams_per_piece)}) AS conversions
}
RETURN canonical_key, toString(f.fdc_id) AS fdc_id, f.food_key AS food_key,
       f.description AS description, f.energy_kcal AS energy_kcal, f.protein_g AS protein_g,
       f.carbohydrate_g AS carbohydrate_g, f.fat_g AS fat_g, f.fiber_g AS fiber_g,
       f.sugars_g AS sugars_g, f.sodium_mg AS sodium_mg,
       ful.candidate_key AS candidate_key, ful.confidence AS confidence,
       ful.price_basis AS price_basis, ful.cost_basis_compatible AS cost_basis_compatible,
       ful.reference_price_minor AS reference_price_minor, ful.currency AS currency,
       ful.package_mass_g AS package_mass_g, ful.package_count AS package_count,
       ful.retailer AS retailer, ful.listing_name AS listing_name, conversions
"""


class CostNutritionRepository:
    def __init__(self, driver):
        self.driver = driver

    def resolve_candidates(self, normalized: list[str]) -> dict[str, list[str]]:
        """Find FoodConcept keys for each already-normalized search term."""
        with self.driver.session() as session:
            rows = session.run(QUERY_A, normalized_names=normalized)
            result = defaultdict(list)
            for row in rows:
                result[row["normalized_name"]].append(row["canonical_key"])
            unresolved = [name for name in normalized if not result[name]]
            if unresolved:
                rows = session.run(QUERY_A2, unresolved=unresolved)
                for row in rows:
                    result[row["unresolved_name"]].append(row["canonical_key"])
        return dict(result)

    def fetch_food_facts(self, canonical_keys: list[str]) -> dict[str, FoodFacts]:
        with self.driver.session() as session:
            rows = session.run(QUERY_B, canonical_keys=list(dict.fromkeys(canonical_keys)))
            grouped: dict[str, FoodFacts] = {}
            for row in rows:
                data = dict(row)
                key = data["canonical_key"]
                facts = grouped.setdefault(key, FoodFacts(
                    canonical_key=key, canonical_name=key.replace("_", " "),
                    fdc_id=data.get("fdc_id"), description=data.get("description"),
                    nutrients=NutrientProfile(
                        calories_kcal=data.get("energy_kcal"), protein_g=data.get("protein_g"),
                        carbs_g=data.get("carbohydrate_g"), fat_g=data.get("fat_g"),
                        fiber_g=data.get("fiber_g"), sugar_g=data.get("sugars_g"),
                        sodium_mg=data.get("sodium_mg")),
                ))
                conversions = data.get("conversions") or []
                for conversion in conversions:
                    facts.grams_per_tbsp = facts.grams_per_tbsp or conversion.get("grams_per_tbsp")
                    facts.grams_per_piece = facts.grams_per_piece or conversion.get("grams_per_piece")
                if data.get("candidate_key") is not None:
                    facts.packages.append(RetailSKU(
                        retailer=data.get("retailer"), listing_name=data.get("listing_name") or data.get("description"),
                        reference_price_minor=data.get("reference_price_minor"), currency=data.get("currency"),
                        package_mass_g=data.get("package_mass_g"), package_count=data.get("package_count"),
                        price_basis=data.get("price_basis"), cost_basis_compatible=data.get("cost_basis_compatible"),
                        confidence=data.get("confidence"), fdc_id=str(data.get("fdc_id") or "")))
            return grouped
