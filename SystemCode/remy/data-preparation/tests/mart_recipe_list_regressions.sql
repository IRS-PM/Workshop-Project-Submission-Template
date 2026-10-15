with source(value) as (
    values ($$['', 'onion']$$)
), actual as (
    select
        {{ recipe_unquote('item') }} as item,
        position
    from source,
         unnest({{ recipe_list_items('value') }}) with ordinality as items(item, position)
), expected(position, item) as (
    values (1, ''), (2, 'onion')
)
select e.position, e.item
from expected e
left join actual a using (position)
where a.position is null or a.item <> e.item
union all
select a.position, a.item
from actual a
where not exists (select 1 from expected e where e.position = a.position)
