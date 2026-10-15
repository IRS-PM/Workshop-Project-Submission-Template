// Warning-screen only: excludes candidates with detected peanut/tree-nut terms.
// It does not prove a meal is allergy-safe; missing exact-listing evidence remains unknown.
// Parameters used for validation:
// excluded_allergens=['peanut','tree_nut'], assumed_recipe_servings=1.0,
// requested_portions=1.0, min_carbs_g=300.0, max_carbs_g=500.0,
// halal_mode='none', vegetarian_mode='warning', limit=25.
MATCH (recipe:Recipe)
OPTIONAL MATCH (recipe)-[req:REQUIRES]->(concept:FoodConcept)
WHERE req IS NULL OR NOT coalesce(req.optional, false)
CALL (req, concept) {
  OPTIONAL MATCH (food:Food)-[candidate:FULFILLS]->(concept)
  WHERE req IS NOT NULL
    AND candidate.approval_status = 'accepted'
    AND candidate.kind = 'direct'
    AND req.choice_group IS NULL
    AND req.quantity > 0
    AND req.unit IN ['gram','kilogram','ounce','pound','cup','tablespoon','teaspoon','pinch']
    AND food.carbohydrate_g >= 0
    AND (req.required_state IS NULL OR candidate.required_state = req.required_state)
    AND none(allergen IN coalesce(candidate.potential_allergens, [])
             WHERE allergen IN $excluded_allergens)
    AND ($halal_mode = 'none'
      OR ($halal_mode = 'estimated' AND candidate.halal_status IN
          ['certified', 'retailer_claim', 'ingredient_screen_pass'])
      OR ($halal_mode = 'certified_only' AND candidate.halal_status = 'certified'
          AND candidate.halal_valid_until > datetime()))
    AND ($vegetarian_mode = 'none'
      OR ($vegetarian_mode = 'warning'
          AND candidate.vegetarian_status <> 'potential_not_vegetarian')
      OR ($vegetarian_mode = 'estimated' AND candidate.vegetarian_status IN
          ['retailer_claim', 'ingredient_screen_pass']))
  WITH food, candidate
  ORDER BY candidate.selection_priority,
           candidate.nutrition_rank,
           CASE WHEN food.nutrition_status = 'validated' THEN 0 ELSE 1 END,
           candidate.confidence DESC,
           food.food_key,
           candidate.candidate_key
  LIMIT 1
  RETURN food, candidate
}
WITH recipe, req, food, candidate,
  CASE req.unit
    WHEN 'gram' THEN 1.0 WHEN 'kilogram' THEN 1000.0
    WHEN 'ounce' THEN 28.3495 WHEN 'pound' THEN 453.592
    WHEN 'cup' THEN 240.0 WHEN 'tablespoon' THEN 15.0
    WHEN 'teaspoon' THEN 5.0 WHEN 'pinch' THEN 0.36
  END AS grams_per_unit
WITH recipe, req, food, candidate,
  CASE WHEN req IS NOT NULL AND $assumed_recipe_servings > 0
             AND $requested_portions > 0
    THEN req.quantity * grams_per_unit * toFloat($requested_portions)
         / $assumed_recipe_servings
  END AS grams
WITH recipe, collect(CASE WHEN req IS NULL THEN null ELSE {
  occurrence_id: req.occurrence_id,
  ingredient: req.raw_text,
  food_key: food.food_key,
  candidate_key: candidate.candidate_key,
  potential_allergens: candidate.potential_allergens,
  allergen_screening_status: candidate.allergen_screening_status,
  halal_status: candidate.halal_status,
  vegetarian_status: candidate.vegetarian_status,
  vegetarian_concerns: candidate.vegetarian_concerns,
  estimated_grams: grams,
  carbs_g: food.carbohydrate_g * grams / 100.0
} END) AS ingredients
WITH recipe, ingredients,
  [item IN ingredients WHERE item.carbs_g IS NULL] AS unresolved,
  reduce(total = 0.0, item IN ingredients | total + coalesce(item.carbs_g, 0.0)) AS carbs
WHERE size(ingredients) > 0
  AND size(unresolved) = 0
  AND carbs > $min_carbs_g
  AND carbs < $max_carbs_g
RETURN recipe.recipe_id AS recipe_id,
       recipe.Title AS recipe,
       round(carbs, 2) AS estimated_carbs_g,
       size(ingredients) AS mandatory_occurrences,
       'warning_screen_only_not_allergy_safe' AS allergy_result,
       $halal_mode AS halal_mode,
       $vegetarian_mode AS vegetarian_mode,
       ingredients
ORDER BY estimated_carbs_g, recipe_id
LIMIT $limit;
