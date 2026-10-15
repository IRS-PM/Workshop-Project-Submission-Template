with candidate_concepts as (
    select distinct normalized_name as canonical_key
    from {{ ref('edge_requires') }}
    union all values
        ('vegetable broth'), ('olive oil'), ('soy milk'), ('flax egg')
), food_source as (
    select
        try_cast(fdc_id as bigint) as fdc_id,
        concat('fdc:', cast(try_cast(fdc_id as bigint) as varchar)) as food_key,
        lower(coalesce(description, '')) as description
    from {{ ref('stg_food') }} f
    join candidate_concepts c on c.canonical_key = {{ recipe_normalize('f.description') }}
    where try_cast(fdc_id as bigint) is not null
    qualify row_number() over (partition by try_cast(fdc_id as bigint) order by description) = 1
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
    select f.*, coalesce(b.ingredients, '') as ingredients
    from food_source f
    left join branded b using (fdc_id)
), allergen_patterns(allergen_key, pattern) as (
    values
        ('peanut', '\bpeanuts?\b'),
        ('tree_nut', '\b(almonds?|walnuts?|cashews?|pistachios?|pecans?|hazelnuts?|macadamias?|brazil nuts?|pine nuts?)\b'),
        ('milk', '\b(milk|whey|casein|caseinate|lactose|buttermilk|cream|cheese)\b'),
        ('egg', '\b(eggs?|albumen|ovalbumin)\b'),
        ('wheat_gluten', '\b(wheat|gluten|barley|rye|spelt)\b'),
        ('soy', '\b(soy|soya|soybeans?)\b'),
        ('fish', '\b(fish|salmon|tuna|cod|anchov(?:y|ies)|sardines?|mackerel|tilapia|trout)\b'),
        ('shellfish', '\b(shellfish|shrimp|prawns?|crabs?|lobsters?|crayfish|mussels?|oysters?|clams?|scallops?|squid|octopus)\b'),
        ('sesame', '\b(sesame|tahini)\b'),
        ('mustard', '\bmustard\b'),
        ('celery', '\bcelery\b'),
        ('lupin', '\blupin\b'),
        ('sulphites', '\b(sulphites?|sulfites?|sulphur dioxide|sulfur dioxide)\b')
)
select
    f.food_key,
    p.allergen_key,
    case when regexp_matches(f.ingredients, p.pattern)
         then 'fdc_ingredient_text_proxy'
         else 'fdc_description_heuristic' end as evidence_kind,
    f.food_key as evidence_ref,
    'potential_contains' as screening_status,
    'allergen_keyword_screen:v1' as policy_version
from food f
cross join allergen_patterns p
where regexp_matches(f.ingredients, p.pattern)
   or regexp_matches(f.description, p.pattern)
