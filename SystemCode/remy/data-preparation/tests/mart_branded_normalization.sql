select e.food_key, e.canonical_key
from {{ ref('edge_fulfills') }} e
where e.match_method = 'ingredient_text_only'
  and not exists (
      select 1
      from {{ ref('stg_branded_food') }} b,
           unnest(regexp_split_to_array(coalesce(b.ingredients, ''), '[,;]')) as ingredients(part)
      where try_cast(b.fdc_id as bigint) = try_cast(regexp_replace(e.food_key, '^fdc:', '') as bigint)
        and {{ recipe_normalize('part') }} = e.canonical_key
  )
