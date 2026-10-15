with facts as (
    select
        c.canonical_key,
        c.status,
        count(f.candidate_key) as candidate_count,
        count(*) filter (where f.price_basis <> 'nutrition_only') as price_count,
        count(*) filter (where f.price_basis = 'package_mass' and f.cost_basis_compatible) as cost_count
    from {{ ref('node_food_concept') }} c
    left join {{ ref('edge_fulfills') }} f using (canonical_key)
    group by c.canonical_key, c.status
)
select canonical_key
from facts
where (status = 'cost_ready' and cost_count = 0)
   or (status = 'price_reference' and (price_count = 0 or cost_count > 0))
   or (status = 'nutrition_only' and (candidate_count = 0 or price_count > 0))
   or (status = 'unmatched' and candidate_count > 0)
