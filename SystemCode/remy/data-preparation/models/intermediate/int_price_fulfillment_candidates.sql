with concepts as (
    select normalized_name as canonical_key, count(*) as occurrence_count
    from {{ ref('edge_requires') }}
    group by normalized_name
), compatible_food as (
    select
        try_cast(f.fdc_id as bigint) as fdc_id,
        concat('fdc:', cast(try_cast(f.fdc_id as bigint) as varchar)) as food_key,
        c.canonical_key,
        c.occurrence_count,
        row_number() over (
            partition by c.canonical_key
            order by (p.carbohydrate_g is not null and p.carbohydrate_g >= 0) desc,
                     (p.nutrition_status = 'validated') desc nulls last,
                     try_cast(f.fdc_id as bigint)
        ) as nutrition_rank
    from {{ ref('stg_food') }} f
    join concepts c on c.canonical_key = {{ recipe_normalize('f.description') }}
    left join {{ ref('int_fdc_nutrition_profiles') }} p on p.fdc_id = try_cast(f.fdc_id as bigint)
    where try_cast(f.fdc_id as bigint) is not null
    qualify row_number() over (partition by try_cast(f.fdc_id as bigint), c.canonical_key order by f.description) = 1
), best_food as (
    select * from compatible_food where nutrition_rank = 1
), span_references as (
    select
        f.food_key,
        f.fdc_id,
        f.canonical_key,
        f.occurrence_count,
        r.price_ref,
        'span_reference' as price_basis,
        r.reference_price_minor,
        'SGD' as currency,
        'fairprice_singapore_config:v1' as currency_source,
        cast(null as double) as package_mass_g,
        cast(null as double) as package_volume_ml,
        cast(null as bigint) as package_count,
        false as cost_basis_compatible,
        'fairprice' as retailer,
        r.priced_name as listing_name,
        cast(null as varchar) as listing_key,
        r.source_snapshot_id,
        'estimated' as price_status,
        'estimated' as price_match_status,
        'unknown' as freshness_status,
        'unknown' as halal_status,
        cast(null as varchar) as halal_evidence_kind,
        cast(null as varchar) as halal_evidence_ref
    from {{ ref('int_price_references') }} r
    join concepts c on c.canonical_key = {{ recipe_normalize('r.priced_name') }}
    join best_food f using (canonical_key)
    where r.parse_status = 'accepted'
), plain_allowlist(canonical_key) as (
    values ('salt'), ('water'), ('rice'), ('lentil'), ('dry lentil'), ('apple'), ('banana'), ('potato'), ('carrot'), ('onion')
), listing_references as (
    select
        f.food_key,
        f.fdc_id,
        f.canonical_key,
        f.occurrence_count,
        concat('listing:', i.product_key) as price_ref,
        case when i.package_mass_g is not null then 'package_mass'
             when i.package_volume_ml is not null then 'package_volume'
             when i.package_count is not null then 'package_count'
             else 'package_unresolved' end as price_basis,
        cast(round(l.raw_price * 100) as bigint) as reference_price_minor,
        'SGD' as currency,
        'fairprice_singapore_config:v1' as currency_source,
        i.package_mass_g,
        i.package_volume_ml,
        i.package_count,
        i.package_mass_g is not null and nullif(i.food_state, '') is null as cost_basis_compatible,
        l.retailer,
        l.name as listing_name,
        i.product_key as listing_key,
        l.source_snapshot_id,
        'estimated' as price_status,
        'accepted' as price_match_status,
        'unknown' as freshness_status,
        case
            when regexp_matches(lower(coalesce(l.dietary_raw, '')), '(^|[^a-z])halal([^a-z]|$)') then 'retailer_claim'
            when a.canonical_key is not null then 'ingredient_screen_pass'
            else 'unknown'
        end as halal_status,
        case
            when regexp_matches(lower(coalesce(l.dietary_raw, '')), '(^|[^a-z])halal([^a-z]|$)') then 'retailer_badge'
            when a.canonical_key is not null then 'reviewed_plain_ingredient_allowlist'
        end as halal_evidence_kind,
        case
            when regexp_matches(lower(coalesce(l.dietary_raw, '')), '(^|[^a-z])halal([^a-z]|$)') then l.source_row_id
            when a.canonical_key is not null then 'plain_allowlist:v1'
        end as halal_evidence_ref
    from {{ ref('stg_retail_listing') }} l
    join {{ ref('int_product_identity') }} i using (source_row_id)
    join concepts c on c.canonical_key = {{ recipe_normalize("coalesce(l.product_name, l.search_term)") }}
    join best_food f using (canonical_key)
    left join plain_allowlist a
      on a.canonical_key = f.canonical_key
     and not regexp_matches(lower(l.name), '\b(currypuffs?|sparkling|juice|sauces?|seasoned|flavou?r(?:ed|ing)?|diced|minced|frozen|canned|mix)\b')
    where l.raw_price > 0
      and i.identity_status <> 'conflict'
      and i.food_classification_status <> 'rejected_non_food'
), combined as (
    select * from span_references
    union all
    select * from listing_references
)
select
    concat('candidate:', sha256(concat_ws('|', food_key, canonical_key, 'direct', price_ref))) as candidate_key,
    *,
    'direct' as kind,
    1.0::double as confidence,
    'exact_normalized_description' as match_method,
    'accepted' as approval_status,
    'halal_screen_v1' as halal_policy_version,
    cast(null as timestamp) as observed_at,
    cast(null as timestamp) as halal_valid_until,
    'unknown' as halal_freshness_status
from combined
qualify row_number() over (
    partition by food_key, canonical_key, price_ref
    order by listing_key is not null desc, reference_price_minor, listing_key
) = 1
