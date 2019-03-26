
{#
    Renders a alias name given a custom alias name. If the custom
    alias name is none, then the resulting alias is just the filename of the
    model. If a alias override is specified, then that is used.

    This macro can be overriden in projects to define different semantics
    for rendering a alias name.

    Arguments:
    custom_alias_name: The custom alias name specified for a model, or none

#}
{% macro generate_alias_name(node, custom_alias_name=none) -%}

    {%- if custom_alias_name is none -%}

        {{ node.name }}

    {%- else -%}

        {{ custom_alias_name | trim }}

    {%- endif -%}

{%- endmacro %}
