with conflicted_ids as (
    select distinct fdc_id
    from {{ ref('int_nutrition_conflicts') }}
    where resolution_status = 'review_required'
), crawler as (
    select *,
        energy_kcal is not null and protein_g is not null and fat_g is not null
        and saturated_fat_g is not null and carbohydrate_g is not null
        and fiber_g is not null and sugars_g is not null and sodium_mg is not null
        and least(energy_kcal, protein_g, fat_g, saturated_fat_g, carbohydrate_g, fiber_g, sugars_g, sodium_mg) >= 0
        and not exists (select 1 from conflicted_ids x where x.fdc_id = c.fdc_id)
        as contract_valid
    from {{ ref('stg_price_mapped_nutrients') }} c
), ids as (
    select fdc_id from {{ ref('int_fdc_canonical_nutrition') }}
    union
    select fdc_id from crawler
)
select
    ids.fdc_id,
    case when c.contract_valid then c.energy_kcal else f.energy_kcal end as energy_kcal,
    case when c.contract_valid then c.protein_g else f.protein_g end as protein_g,
    case when c.contract_valid then c.fat_g else f.fat_g end as fat_g,
    case when c.contract_valid then c.saturated_fat_g else f.saturated_fat_g end as saturated_fat_g,
    case when c.contract_valid then c.carbohydrate_g else f.carbohydrate_g end as carbohydrate_g,
    case when c.contract_valid then c.fiber_g else f.fiber_g end as fiber_g,
    case when c.contract_valid then c.sugars_g else f.sugars_g end as sugars_g,
    case when c.contract_valid then c.sodium_mg else f.sodium_mg end as sodium_mg,
    case when c.contract_valid then c.cholesterol_mg else f.cholesterol_mg end as cholesterol_mg,
    case when c.contract_valid then 'crawler_fdc_profile' else 'fooddata_central' end as nutrition_source,
    case
        when c.contract_valid then c.source_snapshot_id
        else concat(
            'fooddata_central:selection_v1:',
            sha256(concat_ws('|',
                cast(ids.fdc_id as varchar),
                coalesce(cast(f.energy_kcal as varchar), 'null'),
                coalesce(cast(f.protein_g as varchar), 'null'),
                coalesce(cast(f.fat_g as varchar), 'null'),
                coalesce(cast(f.saturated_fat_g as varchar), 'null'),
                coalesce(cast(f.carbohydrate_g as varchar), 'null'),
                coalesce(cast(f.fiber_g as varchar), 'null'),
                coalesce(cast(f.sugars_g as varchar), 'null'),
                coalesce(cast(f.sodium_mg as varchar), 'null'),
                coalesce(cast(f.cholesterol_mg as varchar), 'null')
            ))
        )
    end as nutrition_version,
    'per_100g' as nutrition_basis,
    case
        when c.contract_valid then 'validated'
        when f.fdc_id is null then 'missing'
        when f.energy_kcal is null or f.protein_g is null or f.fat_g is null
          or f.saturated_fat_g is null or f.carbohydrate_g is null or f.fiber_g is null
          or f.sugars_g is null or f.sodium_mg is null then 'incomplete'
        else 'validated'
    end as nutrition_status
from ids
left join crawler c using (fdc_id)
left join {{ ref('int_fdc_canonical_nutrition') }} f using (fdc_id)
