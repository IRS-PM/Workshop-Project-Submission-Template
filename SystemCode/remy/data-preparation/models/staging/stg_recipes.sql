{{ config(
    materialized='external',
    format='parquet',
    location="target/{{ env_var('DBT_TARGET', 'nonprod') }}/staging/recipes.parquet"
) }}

select
    a as column0,
    Title,
    Ingredients,
    Instructions,
    Image_Name,
    Cleaned_Ingredients
from {{ ref('13k-recipes') }}
