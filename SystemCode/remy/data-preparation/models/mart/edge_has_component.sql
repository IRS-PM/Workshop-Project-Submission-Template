select
    try_cast(id as bigint) as id,
    concat('fdc:', cast(try_cast(fdc_id as bigint) as varchar)) as food_key,
    try_cast(id as bigint) as component_id,
    try_cast(pct_weight as double) as pct_weight,
    is_refuse,
    try_cast(gram_weight as double) as gram_weight,
    try_cast(data_points as bigint) as data_points,
    try_cast(min_year_acquired as bigint) as min_year_acquired,
    'fooddata_central' as source
from {{ ref('stg_food_component') }}
where id is not null
  and fdc_id is not null
