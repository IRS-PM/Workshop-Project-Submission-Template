with failures as (
    select 'mapped_profile_count' as failure
    from {{ ref('stg_price_mapped_nutrients') }} having count(*) <> 10845
    union all
    select 'retail_listing_count'
    from {{ ref('stg_retail_listing') }} having count(*) <> 5211
    union all
    select 'invalid_nutrient'
    from {{ ref('stg_price_mapped_nutrients') }}
    where least(protein_g, fat_g, carbohydrate_g, energy_kcal, fiber_g, sodium_mg, saturated_fat_g, sugars_g, cholesterol_mg) < 0
    union all
    select 'unsafe_food_fulfillment'
    from {{ ref('edge_fulfills') }}
    where approval_status <> 'accepted' or match_method in ('ingredient_text_only', 'strong_fuzzy_name')
       or (match_method = 'rule_based_substitution' and rule_id is null)
    union all
    select 'invalid_consumed_cost_basis'
    from {{ ref('edge_fulfills') }}
    where cost_basis_compatible and (price_basis <> 'package_mass' or package_mass_g <= 0 or reference_price_minor <= 0)
    union all
    select 'span_reference_used_for_cost'
    from {{ ref('edge_fulfills') }}
    where price_basis = 'span_reference' and cost_basis_compatible
    union all
    select 'graph_allocation_exceeded'
    from {{ ref('graph_quality_manifest') }} where not within_allocation
)
select * from failures
