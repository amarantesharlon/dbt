{%- materialization view, default -%}

  {%- set identifier = model['name'] -%}
  {%- set tmp_identifier = identifier + '__dbt_tmp' -%}
  {%- set non_destructive_mode = (flags.NON_DESTRUCTIVE == True) -%}
  {%- set existing = adapter.query_for_existing(schema) -%}
  {%- set existing_type = existing.get(identifier) -%}

  {{ run_hooks(pre_transaction_hooks, auto_begin=False) }}
  {{ run_hooks(pre_hooks) }}

  -- build model
  {% if non_destructive_mode and existing_type == 'view' -%}
    -- noop
  {%- else -%}
    {% call statement('main') -%}
      {{ create_view_as(tmp_identifier, sql) }}
    {%- endcall %}
  {%- endif %}

  {{ run_hooks(post_hooks) }}

  -- cleanup
  {% if non_destructive_mode and existing_type == 'view' -%}
    -- noop
  {%- else -%}
    {% if existing_type is not none -%}
      {{ adapter.drop(identifier, existing_type) }}
    {%- endif %}

    {{ adapter.rename(tmp_identifier, identifier) }}
  {%- endif %}

  {{ adapter.commit() }}

  {{ run_hooks(post_transaction_hooks, auto_begin=False) }}

{%- endmaterialization -%}
