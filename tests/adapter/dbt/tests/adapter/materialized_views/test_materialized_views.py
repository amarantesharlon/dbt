from typing import List

import pytest

from dbt.tests.util import run_dbt, get_manifest
from dbt.contracts.relation import RelationType
from dbt.contracts.results import RunStatus


class MaterializedViewTestsBase:

    materialized_view = "mat_view"
    base_table = "base_table"
    base_table_columns = ["base_column"]
    starting_records = [(1,)]
    inserted_records = [(2,)]

    @pytest.fixture(scope="class")
    def models(self):
        base_table = "{{ config(materialized='table') }} select 1 as base_column where 0 = 1"
        mat_view = (
            "{{ config(materialized='materialized_view') }} select * from {{ ref('base_table') }}"
        )
        return {
            "base_table.sql": base_table,
            "mat_view.sql": mat_view,
        }

    @pytest.fixture(scope="function", autouse=True)
    def setup(self, project):
        run_dbt()
        for record in self.inserted_records:
            self.insert_record(project, self.base_table, self.base_table_columns, record)

    @staticmethod
    def get_records(project, relation_identifier: str) -> List[tuple]:
        sql = f"select * from {project.database}.{project.test_schema}.{relation_identifier};"
        return [tuple(row) for row in project.run_sql(sql, fetch="all")]

    @staticmethod
    def insert_record(project, relation_identifier: str, columns: List[str], record: tuple):
        sql = f"""
        insert into {project.database}.{project.test_schema}.{relation_identifier} ({', '.join(columns)})
        values ({','.join(str(value) for value in record)})
        ;"""
        project.run_sql(sql)

    def insert_test_records(self, project):
        for record in self.inserted_records:
            self.insert_record(project, self.base_table, self.base_table_columns, record)

    def assert_relation_is_materialized_view(self, project, relation_identifier):
        manifest = get_manifest(project.project_root)
        model = manifest.nodes[f"model.test.{relation_identifier}"]
        assert model.config.materialized == RelationType.MaterializedView
        assert len(self.get_records(project, relation_identifier)) > 0

    def test_relation_is_materialized_view_on_initial_creation(self, project):
        self.assert_relation_is_materialized_view(project, self.materialized_view)

    def test_relation_is_materialized_view_when_rerun(self, project, adapter):
        run_dbt(["run", "--models", self.materialized_view])
        self.assert_relation_is_materialized_view(project, self.materialized_view)

    def test_relation_is_materialized_view_on_full_refresh(self, project):
        run_dbt(["run", "--models", self.materialized_view, "--full-refresh"])
        self.assert_relation_is_materialized_view(project, self.materialized_view)

    def test_relation_is_materialized_view_on_update(self, project):
        run_dbt(
            ["run", "--models", self.materialized_view, "--vars", "quoting: {identifier: True}"]
        )
        self.assert_relation_is_materialized_view(project, self.materialized_view)

    def test_updated_base_table_data_only_shows_in_materialized_view_after_rerun(self, project):
        self.insert_test_records(project)
        assert self.get_records(project, self.materialized_view) == self.starting_records

        run_dbt(["run", "--models", self.materialized_view])
        assert (
            self.get_records(project, self.materialized_view)
            == self.starting_records + self.inserted_records
        )


class MaterializedViewTestsSkipConfigChangeBase(MaterializedViewTestsBase):
    @pytest.fixture(scope="class")
    def project_config_update(self):
        return {"models": {"on_configuration_change": "skip"}}

    def test_on_configuration_change_skips_with_update(self, project):
        results = run_dbt(
            ["run", "--models", self.materialized_view, "--vars", "quoting: {identifier: True}"]
        )
        assert results.results[0].adapter_response["rows_affected"] == 0
        results.results[0].node.config.on_configuration_change == "skip"
        assert results.results[0].status == RunStatus.Success


class TestMaterializedViewSkipTestsBase(MaterializedViewTestsSkipConfigChangeBase):
    @pytest.mark.skip("This currently fails since we're mocking with a traditional view")
    def test_updated_base_table_data_only_shows_in_materialized_view_after_rerun(self, project):
        pass

    def test_on_configuration_change_skips_with_update(self, project):
        super().test_on_configuration_change_skips_with_update(self)


class MaterializedViewTestsFailConfigChangeBase(MaterializedViewTestsBase):
    @pytest.fixture(scope="class")
    def project_config_update(self):
        return {"models": {"on_configuration_change": "fail"}}

    def test_on_configuration_change_fails_with_update(self, project):
        results = run_dbt(
            ["run", "--models", self.materialized_view, "--vars", "quoting: {identifier: True}"],
            expect_pass=False,
        )
        # breakpoint()
        results.results[0].node.config.on_configuration_change == "fail"
        assert results.results[0].status == RunStatus.Error


class TestMaterializedViewFailTestsBase(MaterializedViewTestsFailConfigChangeBase):
    @pytest.mark.skip("This currently fails since we're mocking with a traditional view")
    def test_updated_base_table_data_only_shows_in_materialized_view_after_rerun(self, project):
        pass

    def test_on_configuration_change_fails_with_update(self, project):
        super().test_on_configuration_change_fails_with_update(self)
