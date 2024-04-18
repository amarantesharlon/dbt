{% macro postgres__drop_materialized_view(relation) -%}
    drop materialized view if exists {{ relation }} cascade
    {{ adapter.cache_dropped(relation) }}
{%- endmacro %}
