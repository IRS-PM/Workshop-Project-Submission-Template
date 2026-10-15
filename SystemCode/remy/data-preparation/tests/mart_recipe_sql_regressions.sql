with samples(value, expected_name) as (
    values
        ('rye-wheat flour', 'rye wheat flour'),
        ('2 large onions', 'onion'),
        ('1 (14-ounce) can tomatoes', 'tomatoe')
), normalized as (
    select value, expected_name, {{ recipe_normalize('value') }} as actual_name
    from samples
)
select *
from normalized
where actual_name <> expected_name
