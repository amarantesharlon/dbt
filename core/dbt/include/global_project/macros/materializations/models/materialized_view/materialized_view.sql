{% materialization materialized_view, default %}
    {% set full_refresh_mode = should_full_refresh() %}
    {% set existing_relation = load_cached_relation(this) %}
    {% set target_relation = this.incorporate(type='view') %}
    {% set intermediate_relation =  make_intermediate_relation(target_relation) %}

    -- the intermediate_relation should not already exist in the database; get_relation
    -- will return None in that case. Otherwise, we get a relation that we can drop
    -- later, before we try to use this name for the current operation
    {% set preexisting_intermediate_relation = load_cached_relation(intermediate_relation) %}
    /*
        This relation (probably) doesn't exist yet. If it does exist, it's a leftover from
        a previous run, and we're going to try to drop it immediately. At the end of this
        materialization, we're going to rename the "existing_relation" to this identifier,
        and then we're going to drop it. In order to make sure we run the correct one of:
          - drop view ...
          - drop table ...
        We need to set the type of this relation to be the type of the existing_relation, if it exists,
        or else "view" as a sane default if it does not. Note that if the existing_relation does not
        exist, then there is nothing to move out of the way and subsequently drop. In that case,
        this relation will be effectively unused.
    */
    {% set backup_relation_type = 'view' if existing_relation is none else existing_relation.type %}
    {% set backup_relation = make_backup_relation(target_relation, backup_relation_type) %}

    -- as above, the backup_relation should not already exist
    {% set preexisting_backup_relation = load_cached_relation(backup_relation) %}

    -- grab current tables grants config for comparison later on
    {% set grant_config = config.get('grants') %}

    -- get config options
    {% set on_configuration_change = config.get('on_configuration_change') %}
    {% if existing_relation %}
        {% set config_updates = get_materialized_view_configuration_changes(existing_relation, config) %}
    {% endif %}

    {{ run_hooks(pre_hooks, inside_transaction=False) }}

    -- drop the temp relations if they exist already in the database
    {{ drop_relation_if_exists(preexisting_intermediate_relation) }}
    {{ drop_relation_if_exists(preexisting_backup_relation) }}

    -- `BEGIN` happens here:
    {{ run_hooks(pre_hooks, inside_transaction=True) }}

    -- cleanup
    -- move the existing view out of the way
    {% if existing_relation is none %}
        {% set build_sql = get_create_materialized_view_as_sql(target_relation, sql) %}
    {% elif full_refresh_mode or existing_relation.type != relation.View %}
        {% set build_sql = get_replace_materialized_view_as_sql(target_relation, sql, existing_relation, backup_relation, intermediate_relation) %}
    {% elif config_updates and on_configuration_change == 'apply' %}
        {% set build_sql = get_alter_materialized_view_as_sql(target_relation, config_updates, sql, existing_relation, backup_relation, intermediate_relation) %}
    {% elif config_updates and on_configuration_change == 'skip' %}
        {% set build_sql = "select 1" %}{# no-op #}
        {{ exceptions.warn("Updates were identified and `on_configuration_change` was set to `skip` for `" ~ target_relation ~ "`") }}
    {% elif config_updates and on_configuration_change == 'fail' %}
        {{ exceptions.raise_compiler_error("Updates were identified and `on_configuration_change` was set to `fail`") }}
    {% else %}
        {% set build_sql = refresh_materialized_view(target_relation) %}
    {% endif %}

    -- build model
    {% call statement("main") %}
        {{ build_sql }}
    {% endcall %}

    {% set should_revoke = should_revoke(existing_relation, full_refresh_mode=True) %}
    {% do apply_grants(target_relation, grant_config, should_revoke=should_revoke) %}

    {% do persist_docs(target_relation, model) %}

    {{ run_hooks(post_hooks, inside_transaction=True) }}

    {{ adapter.commit() }}

    {{ drop_relation_if_exists(backup_relation) }}
    {{ drop_relation_if_exists(intermediate_relation) }}

    {{ run_hooks(post_hooks, inside_transaction=False) }}

    {{ return({'relations': [target_relation]}) }}

{% endmaterialization %}
