with nutrient_rows as (
    select
        try_cast(fdc_id as bigint) as fdc_id,
        try_cast(nutrient_id as bigint) as nutrient_id,
        try_cast(amount as double) as amount,
        row_number() over (
            partition by try_cast(fdc_id as bigint), try_cast(nutrient_id as bigint)
            order by amount is null, try_cast(id as bigint) desc nulls last
        ) as row_num
    from {{ ref('stg_food_nutrient') }}
    where try_cast(nutrient_id as bigint) in (1003, 1004, 1005, 1008, 1079, 1093, 1258, 1063, 2000, 1253)
)
select
    fdc_id,
    max(amount) filter (where nutrient_id = 1008) as energy_kcal,
    max(amount) filter (where nutrient_id = 1003) as protein_g,
    max(amount) filter (where nutrient_id = 1004) as fat_g,
    max(amount) filter (where nutrient_id = 1258) as saturated_fat_g,
    max(amount) filter (where nutrient_id = 1005) as carbohydrate_g,
    max(amount) filter (where nutrient_id = 1079) as fiber_g,
    coalesce(max(amount) filter (where nutrient_id = 2000), max(amount) filter (where nutrient_id = 1063)) as sugars_g,
    max(amount) filter (where nutrient_id = 1093) as sodium_mg,
    max(amount) filter (where nutrient_id = 1253) as cholesterol_mg
from nutrient_rows
where row_num = 1
group by fdc_id
