with listings as (
    select
        'aisle' as source_kind,
        concat('aisle:', cast(try_cast(a as bigint) as varchar)) as source_row_id,
        'fairprice' as retailer,
        cast(null as varchar) as retailer_product_id,
        nullif(trim(category), '') as category,
        nullif(trim(name), '') as name,
        nullif(trim(quantity), '') as quantity_raw,
        try_cast(price_value as decimal(18, 2)) as raw_price,
        nullif(trim(dietary), '') as dietary_raw,
        nullif(trim(origin), '') as origin,
        nullif(trim(brand), '') as brand,
        nullif(trim(variant), '') as variant,
        nullif(trim(product), '') as product_name,
        cast(null as varchar) as search_term
    from {{ ref('retail_aisle_listing') }}
    union all
    select
        'search',
        concat('search:', cast(try_cast(rank as bigint) as varchar), ':', coalesce(term, ''), ':', coalesce(product_id, '')),
        'fairprice',
        nullif(trim(cast(product_id as varchar)), ''),
        nullif(trim(category), ''),
        nullif(trim(name), ''),
        nullif(trim(quantity), ''),
        try_cast(price_value as decimal(18, 2)),
        nullif(trim(dietary), ''),
        cast(null as varchar), cast(null as varchar), cast(null as varchar), cast(null as varchar),
        nullif(trim(term), '')
    from {{ ref('retail_search_listing') }}
), snapshots as (
    select
        source_kind,
        concat('fairprice_', source_kind, ':sha256:', sha256(string_agg(
            md5(concat_ws('|', source_row_id, retailer, coalesce(retailer_product_id, ''),
                coalesce(category, ''), coalesce(name, ''), coalesce(quantity_raw, ''),
                cast(raw_price as varchar), coalesce(dietary_raw, ''), coalesce(origin, ''),
                coalesce(brand, ''), coalesce(variant, ''), coalesce(product_name, ''), coalesce(search_term, ''))),
            '' order by source_row_id
        ))) as source_snapshot_id
    from listings
    group by source_kind
)
select l.source_kind, s.source_snapshot_id, l.source_row_id, l.retailer,
    l.retailer_product_id, l.category, l.name, l.quantity_raw, l.raw_price,
    l.dietary_raw, l.origin, l.brand, l.variant, l.product_name, l.search_term
from listings l
join snapshots s using (source_kind)
