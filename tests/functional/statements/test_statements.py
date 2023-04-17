import pathlib
import pytest

from dbt.tests.util import run_dbt, check_relations_equal, write_file
from tests.functional.statements.fixtures import (
    models__statement_actual,
    models__statement_duplicated_load,
    seeds__statement_actual,
    seeds__statement_expected,
)


class TestStatements:
    @pytest.fixture(scope="class", autouse=True)
    def setUp(self, project):
        # put seeds in 'seed' not 'seeds' directory
        (pathlib.Path(project.project_root) / "seed").mkdir(parents=True, exist_ok=True)
        write_file(seeds__statement_actual, project.project_root, "seed", "seed.csv")
        write_file(
            seeds__statement_expected, project.project_root, "seed", "statement_expected.csv"
        )

    @pytest.fixture(scope="class")
    def models(self):
        return {
            "statement_actual.sql": models__statement_actual,
            "statement_duplicated_load.sql": models__statement_duplicated_load,
        }

    @pytest.fixture(scope="class")
    def project_config_update(self):
        return {
            "seeds": {
                "quote_columns": False,
            },
            "seed-paths": ["seed"],
        }

    def test_postgres_statements(self, project):
        results = run_dbt(["seed"])
        assert len(results) == 2
        results = run_dbt(["run", "-m", "statement_actual"])
        assert len(results) == 1

        check_relations_equal(project.adapter, ["statement_actual", "statement_expected"])

    def test_duplicated_load_statements(self, project):
        run_dbt(["seed"])
        results = run_dbt(["run", "-m", "statement_duplicated_load"], False)
        assert len(results) == 1
        assert results.results[0].status == "error"
        assert (
            'The result "test_statement" has already been loaded into a variable'
            in results.results[0].message
        )
