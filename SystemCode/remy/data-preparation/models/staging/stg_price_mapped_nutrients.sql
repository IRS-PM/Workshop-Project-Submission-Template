with source_rows as (
    select * from {{ ref('price_mapped_nutrients') }}
), snapshot as (
    select concat(
        'fairprice_price_mapped_nutrients:sha256:',
        sha256(string_agg(md5(concat_ws('|',
            cast(fdc_id as varchar), coalesce(description, ''), coalesce(product, ''),
            coalesce(item_prices, ''), coalesce(unpriced_items, ''), cast(priced_items as varchar),
            cast(total_items as varchar), cast(priced_share as varchar), cast(total_price as varchar),
            cast(protein_g as varchar), cast(fat_g as varchar), cast(carb_g as varchar),
            cast(energy_kcal as varchar), cast(fiber_g as varchar), cast(sodium_mg as varchar),
            cast(cholesterol_mg as varchar), cast(satfat_g as varchar), cast(sugars_g as varchar)
        )), '' order by try_cast(fdc_id as bigint)))
    ) as source_snapshot_id
    from source_rows
)
select
    try_cast(fdc_id as bigint) as fdc_id,
    nullif(trim(description), '') as description,
    try_cast(protein_g as double) as protein_g,
    try_cast(fat_g as double) as fat_g,
    try_cast(carb_g as double) as carbohydrate_g,
    try_cast(energy_kcal as double) as energy_kcal,
    try_cast(fiber_g as double) as fiber_g,
    try_cast(sodium_mg as double) as sodium_mg,
    try_cast(cholesterol_mg as double) as cholesterol_mg,
    try_cast(satfat_g as double) as saturated_fat_g,
    try_cast(sugars_g as double) as sugars_g,
    try_cast(priced_items as bigint) as priced_items,
    try_cast(total_items as bigint) as total_items,
    try_cast(priced_share as double) as priced_share,
    try_cast(total_price as decimal(18, 2)) as aggregate_total_price,
    product as product_spans,
    item_prices,
    unpriced_items,
    snapshot.source_snapshot_id
from source_rows
cross join snapshot
where try_cast(fdc_id as bigint) is not null
