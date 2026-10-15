with source_rows as (
    select
        try_cast(column0 as bigint) as recipe_id,
        title,
        instructions,
        image_name,
        row_number() over (
            partition by try_cast(column0 as bigint)
            order by title, instructions, image_name
        ) as row_num
    from {{ ref('stg_recipes') }}
)
select
    recipe_id,
    title,
    instructions,
    image_name,
    'josephrmartinez/recipe-dataset' as source,
    'CC BY-SA 3.0' as source_license
from source_rows
where recipe_id is not null
  and row_num = 1
