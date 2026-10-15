select *
from {{ source('fooddata_central_files', 'food_nutrient') }}
