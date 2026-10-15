select candidate_key
from {{ ref('edge_fulfills') }}
group by candidate_key
having count(*) > 1
