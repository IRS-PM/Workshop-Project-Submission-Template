with failures as (
    select 'concern_without_warning' as failure, candidate_key
    from {{ ref('edge_fulfills') }}
    where len(vegetarian_concerns) > 0 and not may_non_vegetarian
    union all
    select 'warning_without_concern', candidate_key
    from {{ ref('edge_fulfills') }}
    where may_non_vegetarian and len(vegetarian_concerns) = 0
    union all
    select 'unsafe_proxy_approval', candidate_key
    from {{ ref('edge_fulfills') }}
    where vegetarian_status = 'ingredient_screen_pass'
      and (may_non_vegetarian
        or canonical_key not in
           ('salt', 'water', 'rice', 'lentil', 'dry lentil', 'apple', 'banana', 'potato', 'carrot', 'onion')
        or (listing_key is not null and regexp_matches(lower(listing_name),
            '\b(currypuffs?|juice|sauces?|seasoned|flavou?r(?:ed|ing)?|diced|minced|frozen|canned|mix)\b')))
    union all
    select 'claim_without_listing', candidate_key
    from {{ ref('edge_fulfills') }}
    where vegetarian_status = 'retailer_claim' and listing_key is null
)
select * from failures
