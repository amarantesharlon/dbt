{% macro get_create_materialized_view_as_sql(relation, sql) -%}
    {% if relation is not none %}
        {{ adapter.cache_added(relation) }}
    {% endif %}
    {{- adapter.dispatch('get_create_materialized_view_as_sql', 'dbt')(relation, sql) -}}
{%- endmacro %}


{% macro default__get_create_materialized_view_as_sql(relation, sql) -%}
    {{ exceptions.raise_compiler_error(
        "`get_create_materialized_view_as_sql` has not been implemented for this adapter."
    ) }}
{% endmacro %}
