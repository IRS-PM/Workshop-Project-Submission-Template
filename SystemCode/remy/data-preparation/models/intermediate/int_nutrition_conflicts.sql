with comparisons as (
    select c.fdc_id, v.field, v.crawler_value, v.canonical_value
    from {{ ref('stg_price_mapped_nutrients') }} c
    join {{ ref('int_fdc_canonical_nutrition') }} f using (fdc_id)
    cross join lateral (values
        ('energy_kcal', c.energy_kcal, f.energy_kcal),
        ('protein_g', c.protein_g, f.protein_g),
        ('fat_g', c.fat_g, f.fat_g),
        ('saturated_fat_g', c.saturated_fat_g, f.saturated_fat_g),
        ('carbohydrate_g', c.carbohydrate_g, f.carbohydrate_g),
        ('fiber_g', c.fiber_g, f.fiber_g),
        ('sugars_g', c.sugars_g, f.sugars_g),
        ('sodium_mg', c.sodium_mg, f.sodium_mg),
        ('cholesterol_mg', c.cholesterol_mg, f.cholesterol_mg)
    ) v(field, crawler_value, canonical_value)
)
select
    fdc_id, field, crawler_value, canonical_value,
    abs(crawler_value - canonical_value) as absolute_difference,
    'review_required' as resolution_status
from comparisons
where crawler_value is not null and canonical_value is not null
  and abs(crawler_value - canonical_value) > greatest(0.01, abs(canonical_value) * 0.01)
