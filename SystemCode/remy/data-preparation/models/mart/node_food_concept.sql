with requirements as (
    select distinct normalized_name as canonical_key
    from {{ ref('edge_requires') }}
), fulfillment as (
    select
        canonical_key,
        count(*) as candidate_count,
        count(*) filter (where price_basis <> 'nutrition_only') as price_reference_count,
        count(*) filter (where price_basis = 'package_mass' and cost_basis_compatible) as cost_ready_count
    from {{ ref('edge_fulfills') }}
    where approval_status = 'accepted'
    group by canonical_key
)
select
    r.canonical_key,
    r.canonical_key as name,
    case
        when coalesce(f.cost_ready_count, 0) > 0 then 'cost_ready'
        when coalesce(f.price_reference_count, 0) > 0 then 'price_reference'
        when coalesce(f.candidate_count, 0) > 0 then 'nutrition_only'
        else 'unmatched'
    end as status,
    coalesce(f.candidate_count, 0) as candidate_count,
    coalesce(f.price_reference_count, 0) as price_reference_count,
    coalesce(f.cost_ready_count, 0) as cost_ready_count,
    'recipe-food-v4' as normalization_version
from requirements r
left join fulfillment f using (canonical_key)
