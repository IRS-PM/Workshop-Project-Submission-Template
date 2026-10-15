{% macro recipe_normalize(value, apply_aliases=true) %}
    {% set text = "lower(" ~ value ~ ")" %}
    {% set text = "replace(replace(replace(" ~ text ~ ", '–', '-'), '—', '-'), '-', ' ')" %}
    {% set text = "regexp_replace(" ~ text ~ ", '\\([^)]*\\)', ' ', 'g')" %}
    {% set text = "regexp_replace(" ~ text ~ ", '[0-9]+(?:[./][0-9]+)?[[:space:]]*(kg|mg|g|lb|lbs|oz|ounce[s]?|pound[s]?|ml|l|cup[s]?|tbsp?\\.?|tsp?\\.?|qt|quart[s]?|inch(es)?|cm|mm)?\\b', ' ', 'g')" %}
    {% set text = "regexp_replace(" ~ text ~ ", '[^a-z0-9[:space:]]', ' ', 'g')" %}
    {% set text = "regexp_replace(" ~ text ~ ", '\\b(tsp|tsps|teaspoon|teaspoons|tbsp|tbsps|tablespoon|tablespoons|cup|cups|pound|pounds|lb|lbs|ounce|ounces|oz|gram|grams|g|kg|ml|l|clove|cloves|can|cans|package|packages|loaf|loaves|pinch|piece|pieces|qt|quarts|quart|fl|fluid|cl|liter|liters|litre|litres|inch|inches|cm|mm|stick|sticks|slice|slices)\\b', ' ', 'g')" %}
    {% set text = "trim(regexp_replace(regexp_replace(" ~ text ~ ", '\\b(about|added|as|coarse|coarsely|divided|diced|finely|fresh|freshly|for|good|large|medium|melted|more|new|plus|quality|room|small|such|temperature|thinly|torn|chopped|sliced|packed|or|of|at|least|kosher|sturdy|natural|crushed|optional|storebought|homemade|needed|serving|serve|serves|garnish|to|taste|only|lightly|roughly|removed|drained|rinsed|halved|lengthwise|crosswise|beaten|grated|minced|peeled|seeded|cored|cut|cubes|pieces|finishing|separated|tender|parts|white|pale|according|directions)\\b', ' ', 'g'), '[[:space:]]+', ' ', 'g'))" %}
    {% set text = "regexp_replace(regexp_replace(" ~ text ~ ", '\\b([a-z]{4,})ies\\b', '\\1y', 'g'), '\\b([a-z]{5,})s\\b', '\\1', 'g')" %}
    {% if apply_aliases %}
        case {{ text }}
            when 'egg whites' then 'egg white'
            when 'egg white' then 'egg white'
            when 'eggplants' then 'eggplant'
            when 'scallion' then 'green onion'
            when 'spring onion' then 'green onion'
            when 'green onion' then 'green onion'
            when 'bell pepper' then 'bell pepper'
            when 'red pepper' then 'red pepper'
            when 'black pepper' then 'pepper'
            when 'extra virgin olive oil' then 'olive oil'
            else {{ text }}
        end
    {% else %}
        {{ text }}
    {% endif %}
{% endmacro %}

{% macro recipe_list_items(value) %}
    regexp_extract_all(
        coalesce({{ value }}, ''),
        $$'(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*"$$
    )
{% endmacro %}

{% macro recipe_nonempty_list_items(value) %}
    list_filter(
        {{ recipe_list_items(value) }},
        item -> {{ recipe_unquote('item') }} <> ''
    )
{% endmacro %}

{% macro recipe_unquote(value) %}
    replace(
        replace(
            replace(substr({{ value }}, 2, length({{ value }}) - 2), chr(92) || chr(92), chr(92)),
            chr(92) || chr(39), chr(39)
        ),
        chr(92) || chr(34), chr(34)
    )
{% endmacro %}

{% macro recipe_ascii_fraction(value) %}
replace(replace(replace(replace(replace(replace(replace(replace(replace(
    regexp_replace({{ value }}, '([0-9])([¼½¾⅓⅔⅛⅜⅝⅞])', '\1 \2', 'g'),
    '¼', '1/4'), '½', '1/2'), '¾', '3/4'), '⅓', '1/3'), '⅔', '2/3'),
    '⅛', '1/8'), '⅜', '3/8'), '⅝', '5/8'), '⅞', '7/8')
{% endmacro %}

{% macro recipe_is_quantity_range(value) %}
regexp_matches(
    {{ recipe_ascii_fraction(value) }},
    '^\s*(?:[0-9]+(?:\.[0-9]+)?(?:\s+[0-9]+/[0-9]+)?|[0-9]+/[0-9]+)\s*(?:[-–—]|\bto\b)\s*(?:[0-9]+(?:\.[0-9]+)?(?:\s+[0-9]+/[0-9]+)?|[0-9]+/[0-9]+)'
)
{% endmacro %}
