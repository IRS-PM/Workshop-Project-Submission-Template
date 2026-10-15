select e.food_key, e.canonical_key
from {{ ref('edge_fulfills') }} e
join {{ ref('node_food') }} f using (food_key)
where e.match_method = 'strong_fuzzy_name'
  and split_part({{ recipe_normalize('f.description') }}, ' ', 1) <> split_part(e.canonical_key, ' ', 1)
   or e.match_method = 'strong_fuzzy_name'
  and abs(length({{ recipe_normalize('f.description') }}) - length(e.canonical_key)) > 4
   or e.match_method = 'strong_fuzzy_name'
  and 1.0 - levenshtein({{ recipe_normalize('f.description') }}, e.canonical_key)::double
      / greatest(length({{ recipe_normalize('f.description') }}), length(e.canonical_key), 1) < 0.85
