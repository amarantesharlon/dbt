from test.integration.base import DBTIntegrationTest, use_profile

import os

import pytest

import dbt.exceptions


class TestContextVars(DBTIntegrationTest):

    def setUp(self):
        DBTIntegrationTest.setUp(self)
        os.environ["DBT_TEST_013_ENV_VAR"] = "1"

        os.environ["DBT_TEST_013_USER"] = "root"
        os.environ["DBT_TEST_013_PASS"] = "password"

        self.fields = [
            'this',
            'this.name',
            'this.schema',
            'this.table',
            'target.dbname',
            'target.host',
            'target.name',
            'target.port',
            'target.schema',
            'target.threads',
            'target.type',
            'target.user',
            'target.pass',
            'run_started_at',
            'invocation_id',
            'env_var'
        ]

    @property
    def schema(self):
        return "context_vars_013"

    @property
    def models(self):
        return "models"

    @property
    def profile_config(self):
        return {
            'test': {
                'outputs': {
                    # don't use env_var's here so the integration tests can run
                    # seed sql statements and the like. default target is used
                    'dev': {
                        'type': 'postgres',
                        'threads': 1,
                        'host': self.database_host,
                        'port': 5432,
                        'user': "root",
                        'pass': "password",
                        'dbname': 'dbt',
                        'schema': self.unique_schema()
                    },
                    'prod': {
                        'type': 'postgres',
                        'threads': 1,
                        'host': self.database_host,
                        'port': 5432,
                        # root/password
                        'user': "{{ env_var('DBT_TEST_013_USER') }}",
                        'pass': "{{ env_var('DBT_TEST_013_PASS') }}",
                        'dbname': 'dbt',
                        'schema': self.unique_schema()
                    }
                },
                'target': 'dev'
            }
        }

    def get_ctx_vars(self):
        field_list = ", ".join(['"{}"'.format(f) for f in self.fields])
        query = 'select {field_list} from {schema}.context'.format(
            field_list=field_list,
            schema=self.unique_schema())

        vals = self.run_sql(query, fetch='all')
        ctx = dict([(k, v) for (k, v) in zip(self.fields, vals[0])])

        return ctx

    @use_profile('postgres')
    def test_postgres_env_vars_dev(self):
        results = self.run_dbt(['run'])
        self.assertEqual(len(results), 1)
        ctx = self.get_ctx_vars()

        this = '"{}"."{}"."context"'.format(self.default_database,
                                            self.unique_schema())
        self.assertEqual(ctx['this'], this)

        self.assertEqual(ctx['this.name'], 'context')
        self.assertEqual(ctx['this.schema'], self.unique_schema())
        self.assertEqual(ctx['this.table'], 'context')

        self.assertEqual(ctx['target.dbname'], 'dbt')
        self.assertEqual(ctx['target.host'], self.database_host)
        self.assertEqual(ctx['target.name'], 'dev')
        self.assertEqual(ctx['target.port'], 5432)
        self.assertEqual(ctx['target.schema'], self.unique_schema())
        self.assertEqual(ctx['target.threads'], 1)
        self.assertEqual(ctx['target.type'], 'postgres')
        self.assertEqual(ctx['target.user'], 'root')
        self.assertEqual(ctx['target.pass'], '')

        self.assertEqual(ctx['env_var'], '1')

    @use_profile('postgres')
    def test_postgres_env_vars_prod(self):
        results = self.run_dbt(['run', '--target', 'prod'])
        self.assertEqual(len(results), 1)
        ctx = self.get_ctx_vars()

        this = '"{}"."{}"."context"'.format(self.default_database,
                                            self.unique_schema())
        self.assertEqual(ctx['this'], this)

        self.assertEqual(ctx['this.name'], 'context')
        self.assertEqual(ctx['this.schema'], self.unique_schema())
        self.assertEqual(ctx['this.table'], 'context')

        self.assertEqual(ctx['target.dbname'], 'dbt')
        self.assertEqual(ctx['target.host'], self.database_host)
        self.assertEqual(ctx['target.name'], 'prod')
        self.assertEqual(ctx['target.port'], 5432)
        self.assertEqual(ctx['target.schema'], self.unique_schema())
        self.assertEqual(ctx['target.threads'], 1)
        self.assertEqual(ctx['target.type'], 'postgres')
        self.assertEqual(ctx['target.user'], 'root')
        self.assertEqual(ctx['target.pass'], '')
        self.assertEqual(ctx['env_var'], '1')


class TestEmitWarning(DBTIntegrationTest):
    @property
    def schema(self):
        return "context_vars_013"

    @property
    def models(self):
        return "emit-warning-models"

    @use_profile('postgres')
    def test_postgres_warn(self):
        with pytest.raises(dbt.exceptions.CompilationException):
            self.run_dbt(['run'], strict=True)
        self.run_dbt(['run'], strict=False, expect_pass=True)


class TestVarDependencyInheritance(DBTIntegrationTest):
    @property
    def schema(self):
        return "context_vars_013"

    @property
    def models(self):
        return 'dependency-models'

    @property
    def packages_config(self):
        return {
            "packages": [
                {'local': 'first_dependency'},
                {'local': 'second_dependency_v1'},
            ]
        }

    @property
    def project_config(self):
        return {
            'config-version': 2,
            'data-paths': ['dependency-data'],
            'vars': {
                'first_dep_override': 'dep_never_overridden',
                'test': {
                    'from_root_to_root': 'root_root_value',
                },
                'first_dep': {
                    'from_root_to_first': 'root_first_value',
                },
                'second_dep': {
                    'from_root_to_second': 'root_second_value',
                },
            },
        }

    @use_profile('postgres')
    def test_postgres_var_mutual_overrides_v1_conversion(self):
        self.run_dbt(['deps'], strict=False)
        assert len(self.run_dbt(['seed'], strict=False)) == 3
        assert len(self.run_dbt(['run'], strict=False)) == 3
        self.assertTablesEqual('root_model_expected', 'model')
        self.assertTablesEqual('first_dep_expected', 'first_dep_model')
        self.assertTablesEqual('second_dep_expected', 'second_dep_model')


class TestMissingVarGenerateNameMacro(DBTIntegrationTest):
    @property
    def schema(self):
        return "context_vars_013"

    @property
    def models(self):
        return 'trivial-models'

    @property
    def project_config(self):
        return {
            'macro-paths': ['bad-generate-macros'],
        }

    @use_profile('postgres')
    def test_postgres_generate_schema_name_var(self):
        with self.assertRaises(dbt.exceptions.CompilationException) as exc:
            self.run_dbt(['compile'])

        assert "Required var 'somevar' not found in config" in str(exc.exception)

        # globally scoped
        self.use_default_project({
            'vars': {
                'somevar': 1,
            },
            'macro-paths': ['bad-generate-macros'],
        })
        self.run_dbt(['compile'])
        # locally scoped
        self.use_default_project({
            'vars': {
                'test': {
                    'somevar': 1,
                },
            },
            'macro-paths': ['bad-generate-macros'],
        })
        self.run_dbt(['compile'])
