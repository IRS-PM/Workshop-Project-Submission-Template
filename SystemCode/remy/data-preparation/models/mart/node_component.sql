select
    try_cast(id as bigint) as component_id,
    min(name) as name,
    'fooddata_central' as source
from {{ ref('stg_food_component') }}
where id is not null
group by try_cast(id as bigint)
