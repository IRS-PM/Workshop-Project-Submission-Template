with parsed as (
    select * from {{ ref('edge_requires') }}
), failures as (
    select 'nonpositive_known_quantity' as failure, occurrence_id
    from parsed where quantity_status = 'known' and (quantity is null or quantity <= 0)
    union all
    select 'unknown_has_quantity', occurrence_id
    from parsed where quantity_status = 'unknown' and quantity is not null
    union all
    select 'invalid_quantity_status', occurrence_id
    from parsed where quantity_status not in ('known', 'estimated', 'unknown')
    union all
    select 'lost_required_state', occurrence_id
    from parsed
    where regexp_matches(lower(coalesce(raw_text, cleaned_text)), '\b(raw|cooked|dry|hydrated|frozen|whole|ground|salted|unsalted|sweetened|unsweetened)\b')
      and required_state is null
    union all
    select 'implicit_optional', occurrence_id
    from parsed
    where optional and not regexp_matches(lower(cleaned_text), '\boptional\b')
)
select * from failures
