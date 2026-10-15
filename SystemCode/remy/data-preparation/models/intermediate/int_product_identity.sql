with normalized as (
    select
        *,
        lower(trim(regexp_replace(coalesce(name, ''), '[^a-zA-Z0-9]+', ' ', 'g'))) as normalized_name,
        lower(trim(coalesce(quantity_raw, ''))) as pack
    from {{ ref('stg_retail_listing') }}
    where name is not null
), parsed as (
    select
        *,
        try_cast(regexp_extract(pack, '^\s*([0-9]+)\s*[x×]\s*[0-9]+(?:\.[0-9]+)?\s*(?:kg|g|l|ml)\s*$', 1) as bigint) as multiplier,
        try_cast(regexp_extract(pack, '(?:^|[x×]\s*)([0-9]+(?:\.[0-9]+)?)\s*(kg|g)\s*$', 1) as double) as mass_value,
        regexp_extract(pack, '(?:^|[x×]\s*)([0-9]+(?:\.[0-9]+)?)\s*(kg|g)\s*$', 2) as mass_unit,
        try_cast(regexp_extract(pack, '(?:^|[x×]\s*)([0-9]+(?:\.[0-9]+)?)\s*(l|ml)\s*$', 1) as double) as volume_value,
        regexp_extract(pack, '(?:^|[x×]\s*)([0-9]+(?:\.[0-9]+)?)\s*(l|ml)\s*$', 2) as volume_unit,
        try_cast(regexp_extract(pack, '^\s*([0-9]+)\s*(?:pcs?|pieces?|packs?)\s*$', 1) as bigint) as explicit_count
    from normalized
), keyed as (
    select
        *,
        case
            when retailer_product_id is not null then concat(retailer, ':', retailer_product_id, ':', coalesce(nullif(pack, ''), 'unknown-pack'))
            else concat(retailer, ':provisional:', md5(concat_ws('|', retailer, normalized_name, pack)))
        end as product_key
    from parsed
), assessed as (
    select
        *,
        count(distinct normalized_name) over (partition by product_key) as identity_name_count,
        row_number() over (partition by product_key order by source_kind = 'search' desc, source_row_id) as identity_rank
    from keyed
)
select
    product_key,
    retailer_product_id,
    retailer,
    name,
    brand,
    quantity_raw,
    mass_value * case when mass_unit = 'kg' then 1000 else 1 end * coalesce(multiplier, 1) as package_mass_g,
    volume_value * case when volume_unit = 'l' then 1000 else 1 end * coalesce(multiplier, 1) as package_volume_ml,
    coalesce(explicit_count, multiplier) as package_count,
    case
        when quantity_raw is null then 'missing'
        when mass_value is not null then 'mass'
        when volume_value is not null then 'volume'
        when explicit_count is not null then 'count'
        else 'unresolved'
    end as package_dimension,
    cast(null as double) as edible_fraction,
    regexp_extract(lower(name), '\b(raw|cooked|dry|hydrated|frozen|whole|ground|salted|unsalted)\b', 1) as food_state,
    case
        when identity_name_count > 1 then 'conflict'
        when retailer_product_id is not null then 'verified_id'
        else 'provisional'
    end as identity_status,
    case
        when lower(coalesce(category, '')) similar to '%(household|electronics)%'
          or regexp_matches(lower(name), '\b(lotion|shampoo|detergent|cleaner|toothpaste)\b')
          then 'rejected_non_food'
        else 'review_required'
    end as food_classification_status,
    source_snapshot_id,
    source_row_id
from assessed
where identity_rank = 1
qualify row_number() over (order by identity_status = 'verified_id' desc, product_key) <= 6000
