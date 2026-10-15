with candidate_concepts as (
    select distinct normalized_name as canonical_key
    from {{ ref('edge_requires') }}
    union all values
        ('vegetable broth'), ('olive oil'), ('soy milk'), ('flax egg')
), food_source as (
    select
        try_cast(f.fdc_id as bigint) as fdc_id,
        concat('fdc:', cast(try_cast(f.fdc_id as bigint) as varchar)) as food_key,
        lower(coalesce(f.description, '')) as description
    from {{ ref('stg_food') }} f
    join candidate_concepts c on c.canonical_key = {{ recipe_normalize('f.description') }}
    where try_cast(f.fdc_id as bigint) is not null
    qualify row_number() over (partition by try_cast(f.fdc_id as bigint) order by description) = 1
), relevant_fdc as (
    select distinct fdc_id from food_source
), branded as (
    select
        try_cast(b.fdc_id as bigint) as fdc_id,
        lower(coalesce(b.ingredients, '')) as ingredients
    from {{ ref('stg_branded_food') }} b
    join relevant_fdc r on r.fdc_id = try_cast(b.fdc_id as bigint)
    qualify row_number() over (partition by try_cast(b.fdc_id as bigint) order by modified_date desc nulls last) = 1
), food as (
    select
        f.food_key,
        lower(concat_ws(' ', f.description, coalesce(b.ingredients, ''))) as evidence_text
    from food_source f
    left join branded b using (fdc_id)
), concern_patterns(concern, pattern) as (
    values
        ('meat', '\b(pork|beef|chicken|turkey|lamb|mutton|veal|venison|bacon|ham|prosciutto|pepperoni|sausage|lard|tallow)\b'),
        ('fish', '\b(fish|salmon|tuna|cod|anchov(?:y|ies)|sardines?|mackerel|tilapia|trout)\b'),
        ('shellfish', '\b(shrimp|prawns?|crabs?|lobsters?|crayfish|mussels?|oysters?|clams?|scallops?|squid|octopus)\b'),
        ('gelatin', '\bgelatine?\b'),
        ('animal_rennet', '\b(animal rennet|animal enzymes?)\b'),
        ('meat_stock', '\b(meat|beef|chicken|pork|fish)\s+(broth|stock)\b')
)
select
    f.food_key,
    p.concern,
    'fdc_food_text_proxy' as evidence_kind,
    f.food_key as evidence_ref,
    'vegetarian_screen:v1' as policy_version
from food f
cross join concern_patterns p
where regexp_matches(f.evidence_text, p.pattern)
