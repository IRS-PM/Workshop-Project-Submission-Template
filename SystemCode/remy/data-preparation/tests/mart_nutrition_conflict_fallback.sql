with integration_failures as (
    select cast(p.fdc_id as varchar) as failure
    from {{ ref('int_fdc_nutrition_profiles') }} p
    join {{ ref('int_nutrition_conflicts') }} c using (fdc_id)
    where c.resolution_status = 'review_required'
      and p.nutrition_source = 'crawler_fdc_profile'
), synthetic_profiles(fdc_id, crawler_contract_valid, canonical_value) as (
    values (1, true, 12.0)
), synthetic_conflicts(fdc_id, resolution_status) as (
    values (1, 'review_required')
), synthetic_selection as (
    select
        p.fdc_id,
        case
            when crawler_contract_valid and not exists (
                select 1 from synthetic_conflicts c
                where c.fdc_id = p.fdc_id and c.resolution_status = 'review_required'
            ) then 'crawler_fdc_profile'
            else 'fooddata_central'
        end as nutrition_source
    from synthetic_profiles p
)
select failure from integration_failures
union all
select 'synthetic_conflict_did_not_fallback'
from synthetic_selection
where nutrition_source <> 'fooddata_central'
