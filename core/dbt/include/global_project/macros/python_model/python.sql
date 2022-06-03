-- copying a bunch of code from snowflake

{% macro build_ref_function(model) %}

    {% set ref_dict = {} %}
    {#-- i mean obviously don't do this... --#}
    {% for _ref in model.refs %}
        {% set resolved = ref(*_ref) %}
        {% do ref_dict.update({_ref | join("."): resolved | string}) %}
    {% endfor %}

def ref(*args):
  refs = {{ ref_dict | tojson }}
  key = ".".join(args)
  {{load_df_def()}}
  return load_df_function(refs[key])

{% endmacro %}

{% macro build_source_function(model) %}

    {% set source_dict = {} %}
    {#-- i mean obviously don't do this... --#}
    {% for _source in model.sources %}
        {% set resolved = source(*_source) %}
        {% do source_dict.update({_source | join("."): resolved | string}) %}
    {% endfor %}

def source(*args):
  sources = {{ source_dict | tojson }}
  key = ".".join(args)
  {{load_df_def()}}
  return load_df_function(sources[key])

{% endmacro %}



{% macro py_script_prefix( model) %}
# this part is dbt logic for get ref work, do not modify
{{ build_ref_function(model ) }}
{{ build_source_function(model ) }}

def config(*args, **kwargs):
  pass

class dbt:
  config = config
  ref = ref
  source = source


# COMMAND ----------
# This part is user provided model code

{% endmacro %}

{% macro load_df_def() %}
  {{ exceptions.raise_not_implemented(
    'load_df_def macro not implemented for adapter '+adapter.type()) }}
{% endmacro %}
