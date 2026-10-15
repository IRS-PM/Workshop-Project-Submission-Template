{% macro duckdb__load_csv_rows(model, agate_table) %}
    {% set seed_file_path = adapter.get_seed_file_path(model) %}
    {% set delimiter = config.get('delimiter', ',') %}
    {% set sql %}
      COPY {{ this.render() }} FROM '{{ seed_file_path }}'
      (FORMAT CSV, HEADER TRUE, DELIMITER '{{ delimiter }}', QUOTE '"', ESCAPE '"', STRICT_MODE FALSE, PARALLEL FALSE)
    {% endset %}
    {% do adapter.add_query(sql, abridge_sql_log=True) %}
    {{ return(sql) }}
{% endmacro %}
