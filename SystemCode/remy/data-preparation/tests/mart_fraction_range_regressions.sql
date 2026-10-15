with samples(value, expected_quantity, expected_range) as (
    values
        ('1/2 cup beans', 0.5, false),
        ('1 1/2 cups rice', 1.5, false),
        ('1½ cups rice', 1.5, false),
        ('½ cup beans', 0.5, false),
        ('1-2 cups rice', null, true),
        ('1/2-3/4 cup rice', null, true),
        ('¼–½ cup rice', null, true),
        ('1 1/2 to 2 cups rice', null, true),
        ('3½–4-lb chicken', null, true)
), prepared as (
    select *, {{ recipe_ascii_fraction('value') }} as ascii_text,
        {{ recipe_is_quantity_range('value') }} as is_range
    from samples
), extracted as (
    select *,
        regexp_extract(ascii_text, '^\s*([0-9]+)\s+([0-9]+)\/([0-9]+)', 1) as mixed_whole,
        regexp_extract(ascii_text, '^\s*([0-9]+)\s+([0-9]+)\/([0-9]+)', 2) as mixed_num,
        regexp_extract(ascii_text, '^\s*([0-9]+)\s+([0-9]+)\/([0-9]+)', 3) as mixed_den,
        regexp_extract(ascii_text, '^\s*([0-9]+)\/([0-9]+)', 1) as fraction_num,
        regexp_extract(ascii_text, '^\s*([0-9]+)\/([0-9]+)', 2) as fraction_den
    from prepared
), actual as (
    select *, case
        when is_range then null
        when mixed_den <> '' then try_cast(mixed_whole as double) + try_cast(mixed_num as double) / nullif(try_cast(mixed_den as double), 0)
        when fraction_den <> '' then try_cast(fraction_num as double) / nullif(try_cast(fraction_den as double), 0)
        else try_cast(regexp_extract(ascii_text, '^\s*([0-9]+(?:\.[0-9]+)?)', 1) as double)
    end as actual_quantity
    from extracted
)
select value, expected_quantity, actual_quantity, expected_range, is_range
from actual
where is_range <> expected_range
   or (expected_quantity is null and actual_quantity is not null)
   or (expected_quantity is not null and abs(expected_quantity - actual_quantity) > 0.000001)
