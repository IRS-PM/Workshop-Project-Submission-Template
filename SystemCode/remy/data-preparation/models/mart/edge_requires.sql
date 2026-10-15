with source_rows as (
    select
        try_cast(column0 as bigint) as recipe_id,
        {{ recipe_list_items('Cleaned_Ingredients') }} as cleaned_items,
        {{ recipe_list_items('Ingredients') }} as raw_items
    from {{ ref('stg_recipes') }}
    where try_cast(column0 as bigint) is not null
), raw_rows as (
    select recipe_id, {{ recipe_unquote('item') }} as raw_text, position
    from source_rows, unnest(raw_items) with ordinality as items(item, position)
), cleaned_rows as (
    select recipe_id, {{ recipe_unquote('item') }} as cleaned_text, position
    from source_rows, unnest(cleaned_items) with ordinality as items(item, position)
), occurrences as (
    select
        coalesce(r.recipe_id, c.recipe_id) as recipe_id,
        coalesce(r.position, c.position) as position,
        r.raw_text,
        coalesce(nullif(c.cleaned_text, ''), r.raw_text) as cleaned_text
    from raw_rows r
    full outer join cleaned_rows c using (recipe_id, position)
), effective as (
    select *, coalesce(nullif(cleaned_text, ''), raw_text) as effective_text
    from occurrences
    where coalesce(nullif(cleaned_text, ''), raw_text) is not null
), prepared as (
    select
        *,
        {{ recipe_ascii_fraction('effective_text') }} as ascii_text,
        {{ recipe_normalize('effective_text') }} as normalized_name
    from effective
), extracted as (
    select
        *,
        regexp_extract(ascii_text, '^\s*([0-9]+)\s+([0-9]+)\/([0-9]+)', 1) as mixed_whole,
        regexp_extract(ascii_text, '^\s*([0-9]+)\s+([0-9]+)\/([0-9]+)', 2) as mixed_num,
        regexp_extract(ascii_text, '^\s*([0-9]+)\s+([0-9]+)\/([0-9]+)', 3) as mixed_den,
        regexp_extract(ascii_text, '^\s*([0-9]+)\/([0-9]+)', 1) as fraction_num,
        regexp_extract(ascii_text, '^\s*([0-9]+)\/([0-9]+)', 2) as fraction_den,
        {{ recipe_is_quantity_range('ascii_text') }} as is_range,
        lower(regexp_extract(ascii_text, '^\s*(?:[0-9]+\s+[0-9]+/[0-9]+|[0-9]+/[0-9]+|[0-9]+(?:\.[0-9]+)?)\s*([A-Za-z]+)', 1)) as extracted_unit
    from prepared
), parsed as (
    select
        *,
        case
            when is_range then null
            when mixed_den <> '' then try_cast(mixed_whole as double) + try_cast(mixed_num as double) / nullif(try_cast(mixed_den as double), 0)
            when fraction_den <> '' then try_cast(fraction_num as double) / nullif(try_cast(fraction_den as double), 0)
            else try_cast(regexp_extract(ascii_text, '^\s*([0-9]+(?:\.[0-9]+)?)', 1) as double)
        end as quantity,
        case extracted_unit
            when 'tsp' then 'teaspoon' when 'tsps' then 'teaspoon' when 'teaspoon' then 'teaspoon' when 'teaspoons' then 'teaspoon'
            when 'tbsp' then 'tablespoon' when 'tbsps' then 'tablespoon' when 'tablespoon' then 'tablespoon' when 'tablespoons' then 'tablespoon'
            when 'cup' then 'cup' when 'cups' then 'cup'
            when 'lb' then 'pound' when 'lbs' then 'pound' when 'pound' then 'pound' when 'pounds' then 'pound'
            when 'oz' then 'ounce' when 'ounce' then 'ounce' when 'ounces' then 'ounce'
            when 'g' then 'gram' when 'gram' then 'gram' when 'grams' then 'gram'
            when 'kg' then 'kilogram' when 'ml' then 'milliliter' when 'l' then 'liter'
            when 'clove' then 'clove' when 'cloves' then 'clove'
            when 'can' then 'can' when 'cans' then 'can'
            when 'package' then 'package' when 'packages' then 'package'
            when 'pinch' then 'pinch' when 'piece' then 'piece' when 'pieces' then 'piece'
            when 'quart' then 'quart' when 'quarts' then 'quart'
            else null
        end as unit
    from extracted
)
select
    recipe_id,
    concat(cast(recipe_id as varchar), ':', cast(position - 1 as varchar)) as occurrence_id,
    cast(position - 1 as integer) as position,
    coalesce(raw_text, cleaned_text) as raw_text,
    cleaned_text,
    normalized_name,
    case when quantity > 0 then quantity else null end as quantity,
    unit,
    case when quantity > 0 then 'known' else 'unknown' end as quantity_status,
    nullif(regexp_extract(lower(coalesce(raw_text, effective_text)), '\b(raw|cooked|dry|hydrated|frozen|whole|ground|salted|unsalted|sweetened|unsweetened)\b', 1), '') as required_state,
    case when regexp_matches(lower(effective_text), '\bor\b') then concat(cast(recipe_id as varchar), ':choice:', cast(position - 1 as varchar)) else null end as choice_group,
    regexp_matches(lower(effective_text), '\boptional\b') as optional,
    nullif(regexp_extract(effective_text, '(?i)\b(chopped|diced|sliced|minced|peeled|seeded|grated|crushed|drained|rinsed|halved|beaten|melted|torn)\b', 1), '') as preparation,
    'josephrmartinez/recipe-dataset' as source
from parsed
where normalized_name is not null and normalized_name <> ''
  and normalized_name not in ('a', 'an', 'the', 'and', 'or', 'of', 'to', 'for', 'as', 'in')
