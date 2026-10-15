with counts as (
    select 'node' as entity_type, 'Recipe' as entity, count(*)::bigint as row_count, 14000::bigint as allocation from {{ ref('node_recipe') }}
    union all select 'node', 'FoodConcept', count(*), 35000 from {{ ref('node_food_concept') }}
    union all select 'node', 'Food', count(*), 32000 from {{ ref('node_food') }}
    union all select 'node', 'Component', count(*), 3200 from {{ ref('node_component') }}
    union all select 'relationship', 'REQUIRES', count(*), 155000 from {{ ref('edge_requires') }}
    union all select 'relationship', 'FULFILLS', count(*), 50000 from {{ ref('edge_fulfills') }}
    union all select 'relationship', 'HAS_COMPONENT', count(*), 3200 from {{ ref('edge_has_component') }}
), totals as (
    select entity_type, sum(row_count)::bigint as row_count,
        case when entity_type = 'node' then 84200 else 208200 end::bigint as allocation
    from counts group by entity_type
), capabilities as (
    select
        count(*) filter (where price_basis = 'span_reference') as span_references,
        count(*) filter (where listing_key is not null) as listing_associations,
        count(*) filter (where price_basis = 'package_mass' and cost_basis_compatible) as cost_ready,
        count(*) filter (where halal_status in ('certified', 'retailer_claim', 'ingredient_screen_pass')) as halal_screen_ready,
        count(*) filter (where may_allergic) as allergen_warning_candidates,
        count(*) filter (where vegetarian_status in ('retailer_claim', 'ingredient_screen_pass')) as vegetarian_screen_ready
    from {{ ref('edge_fulfills') }}
)
select entity_type, entity, row_count, allocation, row_count <= allocation as within_allocation,
    false as strict_planning_ready,
    concat('span_references=', c.span_references, ';listing_associations=', c.listing_associations,
           ';cost_ready=', c.cost_ready, ';halal_screen_ready=', c.halal_screen_ready,
           ';allergen_warning_candidates=', c.allergen_warning_candidates,
           ';vegetarian_screen_ready=', c.vegetarian_screen_ready) as capability_reason
from counts cross join capabilities c
union all
select entity_type, concat('TOTAL_', upper(entity_type)), row_count, allocation, row_count <= allocation,
    false, 'estimated projection; certification and complete-recipe coverage require query-time selection'
from totals
