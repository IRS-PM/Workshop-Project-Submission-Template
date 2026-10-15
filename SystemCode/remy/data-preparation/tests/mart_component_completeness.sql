select s.id, s.fdc_id
from {{ ref('stg_food_component') }} s
left join {{ ref('edge_has_component') }} e
  on try_cast(s.id as bigint) = e.id
where s.id is not null
  and s.fdc_id is not null
  and e.id is null
