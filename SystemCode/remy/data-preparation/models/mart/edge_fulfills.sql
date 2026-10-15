with concept_usage as (
    select normalized_name as canonical_key, count(*) as occurrence_count
    from {{ ref('edge_requires') }}
    group by normalized_name
), food_source as (
    select try_cast(fdc_id as bigint) as fdc_id, description
    from {{ ref('stg_food') }}
    where try_cast(fdc_id as bigint) is not null and description is not null
    qualify row_number() over (partition by try_cast(fdc_id as bigint) order by description) = 1
), normalized_food as (
    select *, {{ recipe_normalize('description', false) }} as base_name, {{ recipe_normalize('description') }} as normalized_name
    from food_source
), direct_candidates as (
    select
        f.fdc_id, concat('fdc:', cast(f.fdc_id as varchar)) as food_key, c.canonical_key,
        'direct' as kind,
        case when f.base_name <> f.normalized_name then 0.95 else 1.0 end as confidence,
        case when f.base_name <> f.normalized_name then 'approved_alias' else 'exact_normalized_description' end as match_method,
        cast(null as varchar) as context, 1.0::double as replacement_factor, 'same_amount' as factor_basis,
        cast(null as varchar) as required_state, cast(null as varchar) as rule_id,
        'accepted' as approval_status, 'recipe_food_to_dbt:v4' as mapping_version, c.occurrence_count
    from normalized_food f
    join concept_usage c on c.canonical_key = f.normalized_name
    where f.normalized_name <> ''
), substitution_rules(target_key, replacement_key, context, replacement_factor, factor_basis, rule_id) as (
    values
        ('chicken broth', 'vegetable broth', 'vegetarian', 1.0, 'volume', 'sub:chicken-broth:vegetable-broth:v1'),
        ('beef broth', 'vegetable broth', 'vegetarian', 1.0, 'volume', 'sub:beef-broth:vegetable-broth:v1'),
        ('butter', 'olive oil', 'dairy_free', 0.75, 'volume', 'sub:butter:olive-oil:v1'),
        ('milk', 'soy milk', 'dairy_free', 1.0, 'volume', 'sub:milk:soy-milk:v1'),
        ('egg', 'flax egg', 'vegan_baking', 1.0, 'count', 'sub:egg:flax-egg:v1')
), substitution_candidates as (
    select
        f.fdc_id, concat('fdc:', cast(f.fdc_id as varchar)) as food_key, r.target_key as canonical_key,
        'substitute' as kind, 0.95 as confidence, 'rule_based_substitution' as match_method,
        r.context, r.replacement_factor, r.factor_basis, cast(null as varchar) as required_state,
        r.rule_id, 'accepted' as approval_status, 'recipe_food_to_dbt:v4' as mapping_version, c.occurrence_count
    from normalized_food f
    join substitution_rules r on r.replacement_key = f.normalized_name
    join concept_usage c on c.canonical_key = r.target_key
), deduplicated as (
    select * from (select * from direct_candidates union all select * from substitution_candidates)
    qualify row_number() over (partition by food_key, canonical_key, kind order by confidence desc, fdc_id) = 1
), nutrition_ranked as (
    select d.*, row_number() over (
        partition by d.canonical_key, d.kind
        order by (p.carbohydrate_g is not null and p.carbohydrate_g >= 0) desc,
                 (p.nutrition_status = 'validated') desc nulls last,
                 d.confidence desc, d.fdc_id
    ) as kind_rank
    from deduplicated d
    left join {{ ref('int_fdc_nutrition_profiles') }} p using (fdc_id)
), nutrition_candidates as (
    select
        concat('candidate:', sha256(concat_ws('|', food_key, canonical_key, kind, 'nutrition_only'))) as candidate_key,
        food_key, fdc_id, canonical_key, kind, confidence, match_method, context,
        replacement_factor, factor_basis, required_state, rule_id, approval_status,
        mapping_version, occurrence_count,
        cast(null as varchar) as price_ref, 'nutrition_only' as price_basis,
        cast(null as bigint) as reference_price_minor, cast(null as varchar) as currency,
        cast(null as varchar) as currency_source, cast(null as double) as package_mass_g,
        cast(null as double) as package_volume_ml, cast(null as bigint) as package_count,
        false as cost_basis_compatible, cast(null as varchar) as retailer,
        cast(null as varchar) as listing_name, cast(null as varchar) as listing_key,
        cast(null as varchar) as source_snapshot_id, 'unavailable' as price_status,
        'unmatched' as price_match_status, cast(null as timestamp) as observed_at,
        'unknown' as freshness_status, 'unknown' as halal_status,
        cast(null as varchar) as halal_evidence_kind, cast(null as varchar) as halal_evidence_ref,
        'halal_screen_v1' as halal_policy_version, cast(null as timestamp) as halal_valid_until,
        'unknown' as halal_freshness_status,
        kind_rank
    from nutrition_ranked
    where (kind = 'direct' and kind_rank <= 4) or (kind = 'substitute' and kind_rank <= 1)
), price_candidates as (
    select
        p.candidate_key, p.food_key, p.fdc_id, p.canonical_key, p.kind, p.confidence,
        p.match_method, cast(null as varchar) as context, 1.0::double as replacement_factor,
        'same_amount' as factor_basis, cast(null as varchar) as required_state,
        cast(null as varchar) as rule_id, p.approval_status, 'price_mapping:v1' as mapping_version,
        p.occurrence_count, p.price_ref, p.price_basis, p.reference_price_minor, p.currency,
        p.currency_source, p.package_mass_g, p.package_volume_ml, p.package_count,
        p.cost_basis_compatible, p.retailer, p.listing_name, p.listing_key, p.source_snapshot_id,
        p.price_status, p.price_match_status, p.observed_at, p.freshness_status, p.halal_status,
        p.halal_evidence_kind, p.halal_evidence_ref, p.halal_policy_version,
        p.halal_valid_until, p.halal_freshness_status, 0::bigint as kind_rank
    from {{ ref('int_price_fulfillment_candidates') }} p
), candidates as (
    select *,
        case
            when price_basis = 'nutrition_only' and kind = 'direct' and kind_rank = 1 then 0
            when price_basis <> 'nutrition_only' then 1
            when kind = 'direct' then 2
            else 3
        end as slot_priority
    from (select * from nutrition_candidates union all select * from price_candidates)
), per_concept as (
    select *
    from candidates
    qualify row_number() over (
        partition by canonical_key
        order by slot_priority, price_basis = 'package_mass' desc, reference_price_minor nulls last,
                 confidence desc, fdc_id, candidate_key
    ) <= 5
), globally_capped as (
    select * from per_concept
    qualify row_number() over (
        order by occurrence_count desc, canonical_key, slot_priority, confidence desc, fdc_id, candidate_key
    ) <= 50000
), allergen_flags as (
    select
        food_key as allergen_food_key,
        list(allergen_key order by allergen_key) as potential_allergens,
        list(evidence_kind order by allergen_key) as allergen_evidence_kinds
    from {{ ref('int_food_allergen_flags') }}
    group by food_key
), vegetarian_flags as (
    select
        food_key as vegetarian_food_key,
        list(concern order by concern) as vegetarian_concerns
    from {{ ref('int_food_vegetarian_flags') }}
    group by food_key
), vegetarian_claims as (
    select i.product_key as vegetarian_listing_key
    from {{ ref('int_product_identity') }} i
    join {{ ref('stg_retail_listing') }} l using (source_row_id)
    where regexp_matches(lower(coalesce(l.dietary_raw, '')), '(^|[^a-z])(vegetarian|vegan)([^a-z]|$)')
), plain_vegetarian_concepts(vegetarian_canonical_key) as (
    values ('salt'), ('water'), ('rice'), ('lentil'), ('dry lentil'), ('apple'),
           ('banana'), ('potato'), ('carrot'), ('onion')
)
select
    candidate_key, food_key, canonical_key, kind, confidence, match_method, context,
    replacement_factor, factor_basis, required_state, rule_id, approval_status,
    case when price_basis = 'nutrition_only' then 'fooddata_central' else 'fairprice' end as source,
    mapping_version, price_ref, price_match_status, price_basis, reference_price_minor,
    currency, currency_source, package_mass_g, package_volume_ml, package_count,
    cost_basis_compatible, retailer, listing_name, listing_key, source_snapshot_id,
    price_status, observed_at, freshness_status, halal_status, halal_evidence_kind,
    halal_evidence_ref, halal_policy_version, halal_valid_until, halal_freshness_status,
    slot_priority as selection_priority, kind_rank as nutrition_rank,
    a.potential_allergens is not null as may_allergic,
    coalesce(a.potential_allergens, []::varchar[]) as potential_allergens,
    coalesce(a.allergen_evidence_kinds, []::varchar[]) as allergen_evidence_kinds,
    case when a.potential_allergens is not null then 'potential_contains' else 'unknown' end as allergen_screening_status,
    'allergen_keyword_screen:v1' as allergen_policy_version,
    v.vegetarian_concerns is not null as may_non_vegetarian,
    coalesce(v.vegetarian_concerns, []::varchar[]) as vegetarian_concerns,
    case
        when vc.vegetarian_listing_key is not null then 'retailer_claim'
        when v.vegetarian_concerns is not null then 'potential_not_vegetarian'
        when pv.vegetarian_canonical_key is not null
          and (g.listing_key is null or not regexp_matches(lower(g.listing_name),
               '\b(currypuffs?|juice|sauces?|seasoned|flavou?r(?:ed|ing)?|diced|minced|frozen|canned|mix)\b'))
          then 'ingredient_screen_pass'
        else 'unknown'
    end as vegetarian_status,
    case when vc.vegetarian_listing_key is not null then 'retailer_badge'
         when v.vegetarian_concerns is not null then 'fdc_food_text_proxy'
         when pv.vegetarian_canonical_key is not null
          and (g.listing_key is null or not regexp_matches(lower(g.listing_name),
               '\b(currypuffs?|juice|sauces?|seasoned|flavou?r(?:ed|ing)?|diced|minced|frozen|canned|mix)\b'))
          then 'reviewed_plain_ingredient_allowlist' end as vegetarian_evidence_kind,
    'vegetarian_screen:v1' as vegetarian_policy_version
from globally_capped g
left join allergen_flags a on a.allergen_food_key = g.food_key
left join vegetarian_flags v on v.vegetarian_food_key = g.food_key
left join vegetarian_claims vc on vc.vegetarian_listing_key = g.listing_key
left join plain_vegetarian_concepts pv on pv.vegetarian_canonical_key = g.canonical_key
