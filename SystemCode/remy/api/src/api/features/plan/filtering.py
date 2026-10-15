from domain.units import to_grams
from domain.nutrients import calculate_portion_nutrients, sum_nutrition
from workflows.rules.allergen import resolve_allergen_key, check_allergen_compliance
from workflows.rules.dietary import check_halal_compliance, check_vegetarian_compliance
from .exceptions import UnknownAllergen, UnknownDietary, UnknownNutrient, NoCandidates, \
    UnsupportedUnit
from .models import Recipe, Ingredient

SUPPORTED_NUTRIENTS = {
    "calories": ("energy_kcal", "kcal"), "protein": ("protein_g", "g"),
    "carbs": ("carbohydrate_g", "g"), "fat": ("fat_g", "g"),
    "saturated_fat": ("saturated_fat_g", "g"), "fiber": ("fiber_g", "g"),
    "sugar": ("sugars_g", "g"), "sodium": ("sodium_mg", "mg"),
    "cholesterol": ("cholesterol_mg", "mg"),
}
MASS_UNITS = {"g", "gram", "grams", "kg", "kilogram", "kilograms", "mg",
              "milligram", "milligrams", "oz", "ounce", "ounces", "lb", "pound", "pounds"}


def unit_for_nutrient_key(key: str) -> str | None:
    if key.endswith("_g"): return "g"
    if key.endswith("_mg"): return "mg"
    if key.endswith("_kcal") or key == "calories": return "kcal"
    return None


def canonicalize_calories(nutrients: dict) -> dict:
    if nutrients.get("calories") is None:
        if nutrients.get("calories_kcal") is not None:
            nutrients["calories"] = nutrients["calories_kcal"]
        elif nutrients.get("energy_kcal") is not None:
            nutrients["calories"] = nutrients["energy_kcal"]
    return nutrients


def _normalise_food_nutrients(i: Ingredient):
    if not i.nutrients or not i.nutrition_basis:
        return None
    basis = i.nutrition_basis.strip().lower().replace("_", " ")
    # values = {"calories": i.nutrients.get("energy_kcal"),
    #           "protein_g": i.nutrients.get("protein_g"), "fat_g": i.nutrients.get("fat_g"),
    #           "saturated_fat_g": i.nutrients.get("saturated_fat_g"),
    #           "carbs_g": i.nutrients.get("carbohydrate_g"), "fiber_g": i.nutrients.get("fiber_g"),
    #           "sugar_g": i.nutrients.get("sugars_g"), "sodium_mg": i.nutrients.get("sodium_mg"),
    #           "cholesterol_mg": i.nutrients.get("cholesterol_mg")}
    values = i.nutrients
    if basis in {"per 100 g", "per 100g", "100 g", "100g"}:
        return values
    if basis in {"per serving", "serving"} and i.serving_size and i.serving_size_unit == "g":
        return {k: (v * 100.0 / i.serving_size if v is not None else None) for k, v in
                values.items()}
    return None


def filter_candidates(recipes, request) -> list[Recipe]:
    for n in request.nutrients or []:
        if n.code not in SUPPORTED_NUTRIENTS:
            raise UnknownNutrient(f"Unknown nutrient: {n.code}")
    allergens = []
    for a in request.allergies or []:
        key = resolve_allergen_key(a.code)
        if key is None: raise UnknownAllergen(f"Unknown allergen: {a.code}")
        allergens.append(key)
    for d in request.dietary or []:
        if d.code not in {"halal", "vegetarian"}: raise UnknownDietary(
            f"Unknown dietary code: {d.code}")

    good, unsupported, conversion_failures = [], 0, 0
    for recipe in recipes:
        portions, failed = [], False
        for i in recipe.ingredients:
            # if (i.unit or "").strip().lower() not in MASS_UNITS:
            #     conversion_failures += 1
            #     failed = True
            #     break
            try:
                grams, _ = to_grams(i.quantity, i.unit)
            except Exception:
                failed = True
                break
            normalised = _normalise_food_nutrients(i)
            if normalised is None:
                failed = True
                break
            for key, value in normalised.items():
                if value is None:
                    continue
                nutrient_unit = unit_for_nutrient_key(key)
                if nutrient_unit is None:
                    continue
                portions.append(calculate_portion_nutrients(
                    nutrition_per_100g={key: value},
                    quantity_g=grams,
                    unit=nutrient_unit, servings=1
                ))
        if failed:
            unsupported += 1
            continue
        recipe.nutrients = canonicalize_calories(sum_nutrition([p for p in portions if p]))
        declared = " ".join((i.ingredients or i.text or i.canonical_key or "") for i in recipe.ingredients)
        flags = {str(x) for i in recipe.ingredients for x in (i.potential_allergens or [])}
        if flags.intersection(allergens) or any(s == "fail" for _, s in check_allergen_compliance(
                allergens=allergens, declared_ingredients_text=declared,
                precautionary_text=" ".join(flags))):
            continue
        # ponytail: best-effort screening, not certification; unknowns remain explicitly unverified.
        for d in request.dietary or []:
            if d.code == "halal":
                states = [check_halal_compliance(halal_badge=(
                    False if (i.halal_status or "").lower() in {"fail", "false", "no", "non_compliant", "not_halal", "haram"}
                    else True if (i.halal_status or "").lower() in {"pass", "halal", "compliant", "true", "yes", "certified", "retailer_claim", "ingredient_screen_pass"}
                    else None
                )) for i in recipe.ingredients]
            else:
                states = [check_vegetarian_compliance(
                    vegetarian_evidence=(
                        "false" if i.may_non_vegetarian or i.vegetarian_concerns or i.vegetarian_status == "potential_not_vegetarian"
                        else "true" if (i.vegetarian_status or "").lower() in {"pass", "vegetarian", "compliant", "true", "yes", "retailer_claim", "ingredient_screen_pass"}
                        else i.vegetarian_status),
                    ingredients_text=i.ingredients or i.text or i.canonical_key
                ) for i in recipe.ingredients]
            if any(s == "fail" for s in states):
                failed = True
                break
        if not failed:
            good.append(recipe)
    if not good:
        if conversion_failures:
            raise UnsupportedUnit("No deterministic recipe unit conversions")
        if unsupported and recipes:
            raise NoCandidates("No candidates with usable nutrition data")
        raise NoCandidates("No recipes match the requested restrictions and usable nutrition data")
    return good
