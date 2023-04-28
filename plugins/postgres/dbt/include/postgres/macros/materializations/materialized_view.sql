{% macro postgres__get_alter_materialized_view_as_sql(
    relation,
    configuration_changes,
    sql,
    existing_relation,
    backup_relation,
    intermediate_relation
) %}

    -- parse out all changes that can be applied via alter
    {%- set indexes = configuration_changes.pop("indexes", []) -%}

    -- if there are still changes left, a full refresh is needed
    {%- if configuration_changes != [] -%}
        {{- return(get_replace_materialized_view_as_sql(relation, sql, existing_relation, backup_relation, intermediate_relation)) -}}

    -- otherwise, build the sql statements to apply via alter
    {%- else -%}

        -- there is only one change that can be applied via alter, so just return it
        {{- return(postgres__update_indexes_on_materialized_view(relation, indexes)) -}}

    {%- endif -%}

{% endmacro %}


{% macro postgres__get_create_materialized_view_as_sql(relation, sql) %}
    {{- return(get_create_view_as_sql(relation, sql)) -}}
{% endmacro %}


{% macro postgres__get_replace_materialized_view_as_sql(relation, sql, existing_relation, backup_relation, intermediate_relation) %}
    {{- get_create_view_as_sql(intermediate_relation, sql) -}}

    {% if existing_relation is not none %}
        alter view {{ existing_relation }} rename to {{ backup_relation.include(database=False, schema=False) }};
    {% endif %}

    alter view {{ intermediate_relation }} rename to {{ relation.include(database=False, schema=False) }};

{% endmacro %}


{% macro postgres__get_materialized_view_configuration_changes(existing_relation, new_config) %}
    -- TODO: move this from jinja into python, it is not a template and does not need to be overwritten

    {%- set configuration_changes = {} -%}

    {%- set new_indexes = new_config.get("indexes", []) -%}
    {%- set old_indexes = [] -%}
    {%- if new_indexes != old_indexes -%}
        {% set _dummy = configuration_changes.update({"indexes": new_indexes}) %}
    {%- endif -%}

    {{- return(configuration_changes) -}}

{% endmacro %}


{% macro postgres__refresh_materialized_view(relation) %}
    {{- '' -}}
{% endmacro %}


{% macro postgres__update_indexes_on_materialized_view(relation, indexes) %}
    {{ log("Applying UPDATE INDEXES to: " ~ relation) }}
    {{- '' -}}
{% endmacro %}
