with per_concept as (
    select canonical_key,
        count(*) as total_count,
        count(*) filter (where kind = 'substitute') as substitute_count
    from {{ ref('edge_fulfills') }}
    group by canonical_key
), failures as (
    select canonical_key from per_concept where total_count > 5 or substitute_count > 1
    union all
    select 'GLOBAL_CAP' from {{ ref('edge_fulfills') }} having count(*) > 50000
)
select * from failures
