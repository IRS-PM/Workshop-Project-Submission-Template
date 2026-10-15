select *
from {{ ref('node_food') }}
where food_key <> concat('fdc:', cast(fdc_id as varchar))
