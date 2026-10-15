with flattened as (
    select e.candidate_key, e.may_allergic, e.allergen_screening_status, allergen
    from {{ ref('edge_fulfills') }} e
    left join unnest(e.potential_allergens) as flags(allergen) on true
), failures as (
    select 'flag_without_allergen' as failure, candidate_key
    from {{ ref('edge_fulfills') }}
    where may_allergic and len(potential_allergens) = 0
    union all
    select 'allergen_without_flag', candidate_key
    from {{ ref('edge_fulfills') }}
    where not may_allergic and len(potential_allergens) > 0
    union all
    select 'unsafe_free_from_inference', candidate_key
    from {{ ref('edge_fulfills') }}
    where allergen_screening_status not in ('potential_contains', 'unknown')
    union all
    select 'unknown_allergen_key', candidate_key
    from flattened
    where allergen not in ('peanut', 'tree_nut', 'milk', 'egg', 'wheat_gluten', 'soy',
                           'fish', 'shellfish', 'sesame', 'mustard', 'celery', 'lupin', 'sulphites')
)
select * from failures
