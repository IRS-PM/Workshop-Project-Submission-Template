with failures as (
    select 'invalid_accepted_price_reference' as failure, price_ref as detail
    from {{ ref('int_price_references') }}
    where parse_status = 'accepted'
      and (priced_name is null or reference_price_minor <= 0 or price_ref is null)
    union all
    select 'listing_evidence_scope_mismatch', candidate_key
    from {{ ref('edge_fulfills') }}
    where halal_status = 'retailer_claim'
      and (listing_key is null or halal_evidence_kind <> 'retailer_badge' or halal_evidence_ref is null)
    union all
    select 'substitute_has_original_item_price', candidate_key
    from {{ ref('edge_fulfills') }}
    where kind = 'substitute' and price_basis <> 'nutrition_only'
    union all
    select 'unknown_became_approval', candidate_key
    from {{ ref('edge_fulfills') }}
    where halal_status = 'unknown' and halal_evidence_ref is not null
)
select * from failures
