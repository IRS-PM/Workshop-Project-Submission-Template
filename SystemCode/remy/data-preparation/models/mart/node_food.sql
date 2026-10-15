with selected_ids as (
    select distinct try_cast(regexp_replace(food_key, '^fdc:', '') as bigint) as fdc_id
    from {{ ref('edge_fulfills') }}
    union
    select distinct try_cast(fdc_id as bigint)
    from {{ ref('stg_food_component') }}
    where try_cast(fdc_id as bigint) is not null
), food as (
    select * from {{ ref('stg_food') }}
    qualify row_number() over (partition by try_cast(fdc_id as bigint) order by description) = 1
), branded as (
    select * from {{ ref('stg_branded_food') }}
    qualify row_number() over (partition by try_cast(fdc_id as bigint) order by modified_date desc nulls last) = 1
)
select
    s.fdc_id,
    concat('fdc:', cast(s.fdc_id as varchar)) as food_key,
    f.description,
    f.data_type,
    b.brand_name,
    b.brand_owner,
    b.ingredients,
    try_cast(b.serving_size as double) as serving_size,
    b.serving_size_unit,
    b.household_serving_fulltext,
    b.package_weight,
    n.energy_kcal,
    n.protein_g,
    n.fat_g,
    n.saturated_fat_g,
    n.carbohydrate_g,
    n.fiber_g,
    n.sugars_g,
    n.sodium_mg,
    n.cholesterol_mg,
    coalesce(n.nutrition_source, 'fooddata_central') as nutrition_source,
    coalesce(n.nutrition_basis, 'per_100g') as nutrition_basis,
    coalesce(n.nutrition_version, concat('fooddata_central:selection_v1:', sha256(concat(cast(s.fdc_id as varchar), '|missing_profile')))) as nutrition_version,
    coalesce(n.nutrition_status, 'missing') as nutrition_status,
    'fooddata_central' as source
from selected_ids s
left join food f on try_cast(f.fdc_id as bigint) = s.fdc_id
left join branded b on try_cast(b.fdc_id as bigint) = s.fdc_id
left join {{ ref('int_fdc_nutrition_profiles') }} n on n.fdc_id = s.fdc_id
