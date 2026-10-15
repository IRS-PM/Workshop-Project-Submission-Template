#!/usr/bin/env python3
import argparse
import math
import os

import duckdb


parser = argparse.ArgumentParser(description="Estimate one recipe from the lean graph marts.")
parser.add_argument("recipe_id", type=int)
parser.add_argument("--assumed-servings", type=float, required=True)
parser.add_argument("--requested-portions", type=float, required=True)
parser.add_argument("--halal-mode", choices=("off", "estimated", "certified"), default="estimated")
parser.add_argument("--require-cost", action="store_true")
args = parser.parse_args()
if not all(math.isfinite(v) and v > 0 for v in (args.assumed_servings, args.requested_portions)):
    parser.error("serving values must be finite and positive")

catalog = os.getenv("DBT_NONPROD_DUCKLAKE_CATALOG", "target/nonprod/ducklake/catalog.sqlite")
data = os.getenv("DBT_NONPROD_DUCKLAKE_DATA", "target/nonprod/ducklake/data")
connection = duckdb.connect(os.getenv("DBT_NONPROD_PATH", "target/nonprod.duckdb"), read_only=True)
connection.execute("INSTALL ducklake; LOAD ducklake")
connection.execute(f"ATTACH 'ducklake:sqlite:{catalog}' AS lake (DATA_PATH '{data}', READ_ONLY)")

query = r"""
with ranked as (
    select r.*, e.*, f.carbohydrate_g,
        row_number() over (
            partition by r.occurrence_id
            order by (e.price_basis = 'package_mass' and e.cost_basis_compatible) desc,
                     e.price_basis <> 'nutrition_only' desc,
                     e.selection_priority, e.nutrition_rank, e.confidence desc, e.candidate_key
        ) as candidate_rank
    from lake.main_mart.edge_requires r
    left join lake.main_mart.edge_fulfills e on e.canonical_key = r.normalized_name
      and (? = 'off'
        or (? = 'estimated' and e.halal_status in ('certified', 'retailer_claim', 'ingredient_screen_pass'))
        or (? = 'certified' and e.halal_status = 'certified'))
    left join lake.main_mart.node_food f using (food_key)
    where r.recipe_id = ? and not r.optional
), selected as (
    select *, quantity * ? * case unit
        when 'gram' then 1 when 'kilogram' then 1000 when 'ounce' then 28.3495
        when 'pound' then 453.592 when 'cup' then 240 when 'tablespoon' then 15
        when 'teaspoon' then 5 when 'pinch' then 0.36
    end as estimated_grams
    from ranked where candidate_rank = 1 or candidate_rank is null
), measured as (
    select *, carbohydrate_g * estimated_grams / 100 as estimated_carbs_g,
        case when price_basis = 'package_mass' and cost_basis_compatible
                  and package_mass_g > 0 and reference_price_minor > 0
             then reference_price_minor / 100.0 * estimated_grams / package_mass_g end as estimated_consumed_cost,
        case
            when choice_group is not null then 'choice_requires_selection'
            when candidate_key is null then 'no_eligible_candidate'
            when quantity is null then 'unknown_quantity'
            when estimated_grams is null then 'unsupported_unit'
            when carbohydrate_g is null or carbohydrate_g < 0 then 'missing_carbohydrate'
            when ? and (price_basis <> 'package_mass' or not cost_basis_compatible) then 'incompatible_or_missing_price_basis'
        end as partial_reason
    from selected
)
select
    recipe_id, ? as assumed_servings, ? as requested_portions, ? as halal_mode,
    count(*) as mandatory_occurrences,
    count(*) filter (where estimated_carbs_g is not null and choice_group is null) as carb_covered_occurrences,
    count(*) filter (where partial_reason is null) as fully_covered_occurrences,
    sum(estimated_carbs_g) filter (where choice_group is null) as estimated_carbs_g,
    sum(estimated_consumed_cost) filter (where choice_group is null) as partial_consumed_cost,
    list(candidate_key order by position) as selected_candidate_ids,
    list(distinct partial_reason) filter (where partial_reason is not null) as partial_reasons,
    'generic_query_fallback:v1' as conversion_version,
    case when count(*) > 0 and count(*) filter (where partial_reason is not null) = 0 then 'complete' else 'insufficient_data' end as result_status
from measured group by recipe_id
"""
scale = args.requested_portions / args.assumed_servings
row = connection.execute(query, [args.halal_mode] * 3 + [args.recipe_id, scale, args.require_cost, args.assumed_servings, args.requested_portions, args.halal_mode]).fetchone()
if row is None:
    raise SystemExit(f"recipe {args.recipe_id} has no mandatory requirements")
print(dict(zip((column[0] for column in connection.description), row, strict=True)))
