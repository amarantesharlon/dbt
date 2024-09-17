import pytest

from dbt.tests.util import run_dbt, assert_row_count

model_input_sql = """
select 1 as id
"""

ephemeral_model_input_sql = """
{{ config(materialized='ephemeral') }}
select 2 as id
"""

raw_source_csv = """id
3
"""


model_sql = """
select *
from {{ ref('model_input') }}
union all
select *
from {{ ref('ephemeral_model_input') }}
union all
select *
from {{ source('seed_sources', 'raw_source') }}
"""


schema_sources_yml = """
sources:
  - name: seed_sources
    schema: "{{ target.schema }}"
    tables:
      - name: raw_source
"""


class TestEmptyFlag:
    @pytest.fixture(scope="class")
    def seeds(self):
        return {
            "raw_source.csv": raw_source_csv,
        }

    @pytest.fixture(scope="class")
    def models(self):
        return {
            "model_input.sql": model_input_sql,
            "ephemeral_model_input.sql": ephemeral_model_input_sql,
            "model.sql": model_sql,
            "sources.yml": schema_sources_yml,
        }

    def test_run_with_empty(self, project):
        # create source from seed
        run_dbt(["seed"])

        # run without empty - 3 expected rows in output - 1 from each input
        run_dbt(["run"])
        assert_row_count(project, "model", 3)

        # run with empty - 0 expected rows in output
        run_dbt(["run", "--empty"])
        assert_row_count(project, "model", 0)

        # build without empty - 3 expected rows in output - 1 from each input
        run_dbt(["build"])
        assert_row_count(project, "model", 3)

        # build with empty - 0 expected rows in output
        run_dbt(["build", "--empty"])
        assert_row_count(project, "model", 0)

        # ensure dbt compile supports --empty flag
        run_dbt(["compile", "--empty"])
