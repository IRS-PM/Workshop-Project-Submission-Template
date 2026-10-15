select *
from {{ ref('edge_fulfills') }}
where confidence < 0 or confidence > 1
