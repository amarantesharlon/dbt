import unittest
from datetime import datetime, timedelta
import json
import os

import multiprocessing
from base64 import standard_b64encode as b64
import requests
import socket
import time


from dbt.exceptions import CompilationException
from test.integration.base import DBTIntegrationTest, use_profile, AnyFloat, \
    AnyStringWith
from dbt.main import handle_and_check


class BaseSourcesTest(DBTIntegrationTest):
    @property
    def schema(self):
        return "sources_042"

    @property
    def models(self):
        return "test/integration/042_sources_test/models"

    @property
    def project_config(self):
        return {
            'data-paths': ['test/integration/042_sources_test/data'],
            'quoting': {'database': True, 'schema': True, 'identifier': True},
        }

    def setUp(self):
        super(BaseSourcesTest, self).setUp()
        os.environ['DBT_TEST_SCHEMA_NAME_VARIABLE'] = 'test_run_schema'
        self.run_dbt_with_vars(['seed'], strict=False)

    def tearDown(self):
        del os.environ['DBT_TEST_SCHEMA_NAME_VARIABLE']
        super(BaseSourcesTest, self).tearDown()

    def run_dbt_with_vars(self, cmd, *args, **kwargs):
        cmd.extend(['--vars',
                    '{{test_run_schema: {}}}'.format(self.unique_schema())])
        return self.run_dbt(cmd, *args, **kwargs)


class TestSources(BaseSourcesTest):
    @use_profile('postgres')
    def test_postgres_basic_source_def(self):
        results = self.run_dbt_with_vars(['run'])
        self.assertEqual(len(results), 3)
        self.assertManyTablesEqual(
            ['source', 'descendant_model', 'nonsource_descendant'],
            ['expected_multi_source', 'multi_source_model'])
        results = self.run_dbt_with_vars(['test'])
        self.assertEqual(len(results), 4)

    @use_profile('postgres')
    def test_postgres_source_selector(self):
        # only one of our models explicitly depends upon a source
        results = self.run_dbt_with_vars([
            'run',
            '--models',
            'source:test_source.test_table+'
        ])
        self.assertEqual(len(results), 1)
        self.assertTablesEqual('source', 'descendant_model')
        self.assertTableDoesNotExist('nonsource_descendant')
        self.assertTableDoesNotExist('multi_source_model')
        results = self.run_dbt_with_vars([
            'test',
            '--models',
            'source:test_source.test_table+'
        ])
        self.assertEqual(len(results), 4)

    @use_profile('postgres')
    def test_postgres_empty_source_def(self):
        # sources themselves can never be selected, so nothing should be run
        results = self.run_dbt_with_vars([
            'run',
            '--models',
            'source:test_source.test_table'
        ])
        self.assertTableDoesNotExist('nonsource_descendant')
        self.assertTableDoesNotExist('multi_source_model')
        self.assertTableDoesNotExist('descendant_model')
        self.assertEqual(len(results), 0)

    @use_profile('postgres')
    def test_postgres_source_only_def(self):
        results = self.run_dbt_with_vars([
            'run', '--models', 'source:other_source+'
        ])
        self.assertEqual(len(results), 1)
        self.assertTablesEqual('expected_multi_source', 'multi_source_model')
        self.assertTableDoesNotExist('nonsource_descendant')
        self.assertTableDoesNotExist('descendant_model')

        results = self.run_dbt_with_vars([
            'run', '--models', 'source:test_source+'
        ])
        self.assertEqual(len(results), 2)
        self.assertManyTablesEqual(
            ['source', 'descendant_model'],
            ['expected_multi_source', 'multi_source_model'])
        self.assertTableDoesNotExist('nonsource_descendant')

    @use_profile('postgres')
    def test_source_childrens_parents(self):
        results = self.run_dbt_with_vars([
            'run', '--models', '@source:test_source'
        ])
        self.assertEqual(len(results), 2)
        self.assertManyTablesEqual(
            ['source', 'descendant_model'],
            ['expected_multi_source', 'multi_source_model'],
        )
        self.assertTableDoesNotExist('nonsource_descendant')


class TestSourceFreshness(BaseSourcesTest):
    def setUp(self):
        super(TestSourceFreshness, self).setUp()
        self.maxDiff = None
        self._id = 100
        # this is the db initial value
        self.last_inserted_time = "2016-09-19T14:45:51+00:00"

    # test_source.test_table should have a loaded_at field of `updated_at`
    # and a freshness of warn_after: 10 hours, error_after: 18 hours
    # by default, our data set is way out of date!
    def _set_updated_at_to(self, delta):
        insert_time = datetime.utcnow() + delta
        timestr = insert_time.strftime("%Y-%m-%d %H:%M:%S")
        #favorite_color,id,first_name,email,ip_address,updated_at
        insert_id = self._id
        self._id += 1
        raw_sql = """INSERT INTO {schema}.{source}
            (favorite_color,id,first_name,email,ip_address,updated_at)
        VALUES (
            'blue',{id},'Jake','abc@example.com','192.168.1.1','{time}'
        )"""
        self.run_sql(
            raw_sql,
            kwargs={
                'schema': self.unique_schema(),
                'time': timestr,
                'id': insert_id,
                'source': self.adapter.quote('source'),
            }
        )
        self.last_inserted_time = insert_time.strftime("%Y-%m-%dT%H:%M:%S+00:00")

    def _assert_freshness_results(self, path, state):
        self.assertTrue(os.path.exists(path))
        with open(path) as fp:
            data = json.load(fp)

        self.assertEqual(set(data), {'meta', 'sources'})
        self.assertIn('generated_at', data['meta'])
        self.assertIn('elapsed_time', data['meta'])
        self.assertTrue(isinstance(data['meta']['elapsed_time'], float))
        self.assertBetween(data['meta']['generated_at'],
                           self.freshness_start_time)

        last_inserted_time = self.last_inserted_time
        if last_inserted_time is None:
            last_inserted_time = "2016-09-19T14:45:51+00:00"

        self.assertEqual(data['sources'], {
            'source.test.test_source.test_table': {
                'max_loaded_at': last_inserted_time,
                'snapshotted_at': AnyStringWith(),
                'max_loaded_at_time_ago_in_s': AnyFloat(),
                'state': state,
                'criteria': {
                    'warn_after': {'count': 10, 'period': 'hour'},
                    'error_after': {'count': 1, 'period': 'day'},
                },
            }
        })

    def _run_source_freshness(self):
        self.freshness_start_time = datetime.utcnow()
        results = self.run_dbt_with_vars(
            ['source', 'snapshot-freshness', '-o', 'target/error_source.json'],
            expect_pass=False
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, 'error')
        self.assertTrue(results[0].failed)
        self.assertIsNone(results[0].error)
        self._assert_freshness_results('target/error_source.json', 'error')

        self._set_updated_at_to(timedelta(hours=-12))
        self.freshness_start_time = datetime.utcnow()
        results = self.run_dbt_with_vars(
            ['source', 'snapshot-freshness', '-o', 'target/warn_source.json'],
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, 'warn')
        self.assertFalse(results[0].failed)
        self.assertIsNone(results[0].error)
        self._assert_freshness_results('target/warn_source.json', 'warn')

        self._set_updated_at_to(timedelta(hours=-2))
        self.freshness_start_time = datetime.utcnow()
        results = self.run_dbt_with_vars(
            ['source', 'snapshot-freshness', '-o', 'target/pass_source.json'],
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, 'pass')
        self.assertFalse(results[0].failed)
        self.assertIsNone(results[0].error)
        self._assert_freshness_results('target/pass_source.json', 'pass')

    @use_profile('postgres')
    def test_postgres_source_freshness(self):
        self._run_source_freshness()

    @use_profile('snowflake')
    def test_snowflake_source_freshness(self):
        self._run_source_freshness()

    @use_profile('redshift')
    def test_redshift_source_freshness(self):
        self._run_source_freshness()

    @use_profile('bigquery')
    def test_bigquery_source_freshness(self):
        self._run_source_freshness()


class TestSourceFreshnessErrors(BaseSourcesTest):
    @property
    def models(self):
        return "test/integration/042_sources_test/error_models"

    @use_profile('postgres')
    def test_postgres_error(self):
        results = self.run_dbt_with_vars(
            ['source', 'snapshot-freshness'],
            expect_pass=False
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, 'error')
        self.assertFalse(results[0].failed)
        self.assertIsNotNone(results[0].error)


class TestMalformedSources(BaseSourcesTest):
    @property
    def models(self):
        return "test/integration/042_sources_test/malformed_models"

    @use_profile('postgres')
    def test_postgres_malformed_schema_nonstrict_will_not_break_run(self):
        self.run_dbt_with_vars(['run'], strict=False)

    @use_profile('postgres')
    def test_postgres_malformed_schema_strict_will_break_run(self):
        with self.assertRaises(CompilationException):
            self.run_dbt_with_vars(['run'], strict=True)


class ServerProcess(multiprocessing.Process):
    def __init__(self, cli_vars=None):
        self.port = 22991
        handle_and_check_args = [
            '--strict', 'rpc', '--log-cache-events',
            '--port', str(self.port),
        ]
        if cli_vars:
            handle_and_check_args.extend(['--vars', cli_vars])
        super(ServerProcess, self).__init__(
            target=handle_and_check,
            args=(handle_and_check_args,))

    def is_up(self):
        sock = socket.socket()
        try:
            sock.connect(('localhost', self.port))
        except socket.error:
            return False
        sock.close()
        return True

    def start(self):
        super(ServerProcess, self).start()
        for _ in range(10):
            if self.is_up():
                break
            time.sleep(0.5)
        if not self.is_up():
            self.terminate()
            raise Exception('server never appeared!')


_select_from_ephemeral = '''with __dbt__CTE__ephemeral_model as (


select 1 as id
)select * from __dbt__CTE__ephemeral_model'''


@unittest.skipIf(os.name == 'nt', 'Windows not supported for now')
class TestRPCServer(BaseSourcesTest):
    def setUp(self):
        super(TestRPCServer, self).setUp()
        self._server = ServerProcess(
            cli_vars='{{test_run_schema: {}}}'.format(self.unique_schema())
        )
        self._server.start()

    def tearDown(self):
        self._server.terminate()
        super(TestRPCServer, self).tearDown()

    @property
    def project_config(self):
        return {
            'data-paths': ['test/integration/042_sources_test/data'],
            'quoting': {'database': True, 'schema': True, 'identifier': True},
            'macro-paths': ['test/integration/042_sources_test/macros'],
        }

    def build_query(self, method, kwargs, sql=None, test_request_id=1, macros=None):
        body_data = ''
        if sql is not None:
            body_data += sql

        if macros is not None:
            body_data += macros

        if sql is not None or macros is not None:
            kwargs['sql'] = b64(body_data.encode('utf-8')).decode('utf-8')

        return {
            'jsonrpc': '2.0',
            'method': method,
            'params': kwargs,
            'id': test_request_id
        }

    def perform_query(self, query):
        url = 'http://localhost:{}/jsonrpc'.format(self._server.port)
        headers = {'content-type': 'application/json'}
        response = requests.post(url, headers=headers, data=json.dumps(query))
        return response

    def query(self, _method, _sql=None, _test_request_id=1, macros=None, **kwargs):
        built = self.build_query(_method, kwargs, _sql, _test_request_id, macros)
        return self.perform_query(built)

    def assertResultHasTimings(self, result, *names):
        self.assertIn('timing', result)
        timings = result['timing']
        self.assertEqual(len(timings), len(names))
        for expected_name, timing in zip(names, timings):
            self.assertIn('name', timing)
            self.assertEqual(timing['name'], expected_name)
            self.assertIn('started_at', timing)
            self.assertIn('completed_at', timing)
            datetime.strptime(timing['started_at'], '%Y-%m-%dT%H:%M:%S.%fZ')
            datetime.strptime(timing['completed_at'], '%Y-%m-%dT%H:%M:%S.%fZ')

    def assertIsResult(self, data):
        self.assertEqual(data['id'], 1)
        self.assertEqual(data['jsonrpc'], '2.0')
        self.assertIn('result', data)
        self.assertNotIn('error', data)
        return data['result']

    def assertIsError(self, data):
        self.assertEqual(data['id'], 1)
        self.assertEqual(data['jsonrpc'], '2.0')
        self.assertIn('error', data)
        self.assertNotIn('result', data)
        return data['error']

    def assertIsErrorWithCode(self, data, code):
        error = self.assertIsError(data)
        self.assertIn('code', error)
        self.assertIn('message', error)
        self.assertEqual(error['code'], code)
        return error

    def assertResultHasSql(self, data, raw_sql, compiled_sql=None):
        if compiled_sql is None:
            compiled_sql = raw_sql
        result = self.assertIsResult(data)
        self.assertIn('logs', result)
        self.assertTrue(len(result['logs']) > 0)
        self.assertIn('raw_sql', result)
        self.assertIn('compiled_sql', result)
        self.assertEqual(result['raw_sql'], raw_sql)
        self.assertEqual(result['compiled_sql'], compiled_sql)
        return result

    def assertSuccessfulCompilationResult(self, data, raw_sql, compiled_sql=None):
        result = self.assertResultHasSql(data, raw_sql, compiled_sql)
        self.assertNotIn('table', result)
        # compile results still have an 'execute' timing, it just represents
        # the time to construct a result object.
        self.assertResultHasTimings(result, 'compile', 'execute')

    def assertSuccessfulRunResult(self, data, raw_sql, compiled_sql=None, table=None):
        result = self.assertResultHasSql(data, raw_sql, compiled_sql)
        self.assertIn('table', result)
        if table is not None:
            self.assertEqual(result['table'], table)
        self.assertResultHasTimings(result, 'compile', 'execute')

    @use_profile('postgres')
    def test_compile(self):
        trivial = self.query(
            'compile',
            'select 1 as id',
            name='foo'
        ).json()
        self.assertSuccessfulCompilationResult(
            trivial, 'select 1 as id'
        )

        ref = self.query(
            'compile',
            'select * from {{ ref("descendant_model") }}',
            name='foo'
        ).json()
        self.assertSuccessfulCompilationResult(
            ref,
            'select * from {{ ref("descendant_model") }}',
            compiled_sql='select * from "{}"."{}"."descendant_model"'.format(
                self.default_database,
                self.unique_schema())
        )

        source = self.query(
            'compile',
            'select * from {{ source("test_source", "test_table") }}',
            name='foo'
        ).json()
        self.assertSuccessfulCompilationResult(
            source,
            'select * from {{ source("test_source", "test_table") }}',
            compiled_sql='select * from "{}"."{}"."source"'.format(
                self.default_database,
                self.unique_schema())
            )

        macro = self.query(
            'compile',
            'select {{ my_macro() }}',
            name='foo',
            macros='{% macro my_macro() %}1 as id{% endmacro %}'
        ).json()
        self.assertSuccessfulCompilationResult(
            macro,
            'select {{ my_macro() }}',
            compiled_sql='select 1 as id'
        )

        macro_override = self.query(
            'compile',
            'select {{ happy_little_macro() }}',
            name='foo',
            macros='{% macro override_me() %}2 as id{% endmacro %}'
        ).json()
        self.assertSuccessfulCompilationResult(
            macro_override,
            'select {{ happy_little_macro() }}',
            compiled_sql='select 2 as id'
        )

        macro_override_with_if_statement = self.query(
            'compile',
            '{% if True %}select {{ happy_little_macro() }}{% endif %}',
            name='foo',
            macros='{% macro override_me() %}2 as id{% endmacro %}'
        ).json()
        self.assertSuccessfulCompilationResult(
            macro_override_with_if_statement,
            '{% if True %}select {{ happy_little_macro() }}{% endif %}',
            compiled_sql='select 2 as id'
        )

        ephemeral = self.query(
            'compile',
            'select * from {{ ref("ephemeral_model") }}',
            name='foo'
        ).json()
        self.assertSuccessfulCompilationResult(
            ephemeral,
            'select * from {{ ref("ephemeral_model") }}',
            compiled_sql=_select_from_ephemeral
        )

    @use_profile('postgres')
    def test_run(self):
        # seed + run dbt to make models before using them!
        self.run_dbt_with_vars(['seed'])
        self.run_dbt_with_vars(['run'])
        data = self.query(
            'run',
            'select 1 as id',
            name='foo'
        ).json()
        self.assertSuccessfulRunResult(
            data, 'select 1 as id', table={'column_names': ['id'], 'rows': [[1.0]]}
        )

        ref = self.query(
            'run',
            'select * from {{ ref("descendant_model") }} order by updated_at limit 1',
            name='foo'
        ).json()
        self.assertSuccessfulRunResult(
            ref,
            'select * from {{ ref("descendant_model") }} order by updated_at limit 1',
            compiled_sql='select * from "{}"."{}"."descendant_model" order by updated_at limit 1'.format(
                self.default_database,
                self.unique_schema()),
            table={
                'column_names': ['favorite_color', 'id', 'first_name', 'email', 'ip_address', 'updated_at'],
                'rows': [['blue', 38.0, 'Gary',  'gray11@statcounter.com', "'40.193.124.56'", '1970-01-27T10:04:51']],
            }
        )

        source = self.query(
            'run',
            'select * from {{ source("test_source", "test_table") }} order by updated_at limit 1',
            name='foo'
        ).json()
        self.assertSuccessfulRunResult(
            source,
            'select * from {{ source("test_source", "test_table") }} order by updated_at limit 1',
            compiled_sql='select * from "{}"."{}"."source" order by updated_at limit 1'.format(
                self.default_database,
                self.unique_schema()),
            table={
                'column_names': ['favorite_color', 'id', 'first_name', 'email', 'ip_address', 'updated_at'],
                'rows': [['blue', 38.0, 'Gary',  'gray11@statcounter.com', "'40.193.124.56'", '1970-01-27T10:04:51']],
            }
        )

        macro = self.query(
            'run',
            'select {{ my_macro() }}',
            name='foo',
            macros='{% macro my_macro() %}1 as id{% endmacro %}'
        ).json()
        self.assertSuccessfulRunResult(
            macro,
            raw_sql='select {{ my_macro() }}',
            compiled_sql='select 1 as id',
            table={'column_names': ['id'], 'rows': [[1.0]]}
        )

        macro_override = self.query(
            'run',
            'select {{ happy_little_macro() }}',
            name='foo',
            macros='{% macro override_me() %}2 as id{% endmacro %}'
        ).json()
        self.assertSuccessfulRunResult(
            macro_override,
            raw_sql='select {{ happy_little_macro() }}',
            compiled_sql='select 2 as id',
            table={'column_names': ['id'], 'rows': [[2.0]]}
        )

        macro_override_with_if_statement = self.query(
            'run',
            '{% if True %}select {{ happy_little_macro() }}{% endif %}',
            name='foo',
            macros='{% macro override_me() %}2 as id{% endmacro %}'
        ).json()
        self.assertSuccessfulRunResult(
            macro_override_with_if_statement,
            '{% if True %}select {{ happy_little_macro() }}{% endif %}',
            compiled_sql='select 2 as id',
            table={'column_names': ['id'], 'rows': [[2.0]]}
        )

        macro_with_raw_statement = self.query(
            'run',
            '{% raw %}select 1 as{% endraw %}{{ test_macros() }}{% macro test_macros() %} id{% endmacro %}',
            name='foo'
        ).json()
        self.assertSuccessfulRunResult(
            macro_with_raw_statement,
            '{% raw %}select 1 as{% endraw %}{{ test_macros() }}',
            compiled_sql='select 1 as id',
            table={'column_names': ['id'], 'rows': [[1.0]]}
        )

        macro_with_comment = self.query(
            'run',
            '{% raw %}select 1 {% endraw %}{{ test_macros() }} {# my comment #}{% macro test_macros() -%} as{% endmacro %} id{# another comment #}',
            name='foo'
        ).json()
        self.assertSuccessfulRunResult(
            macro_with_comment,
            '{% raw %}select 1 {% endraw %}{{ test_macros() }} {# my comment #} id{# another comment #}',
            compiled_sql='select 1 as  id',
            table={'column_names': ['id'], 'rows': [[1.0]]}
        )

        ephemeral = self.query(
            'run',
            'select * from {{ ref("ephemeral_model") }}',
            name='foo'
        ).json()
        self.assertSuccessfulRunResult(
            ephemeral,
            raw_sql='select * from {{ ref("ephemeral_model") }}',
            compiled_sql=_select_from_ephemeral,
            table={'column_names': ['id'], 'rows': [[1.0]]}
        )

    @use_profile('postgres')
    def test_invalid_requests(self):
        data = self.query(
            'xxxxxnotamethodxxxxx',
            'hi this is not sql'
        ).json()
        error = self.assertIsErrorWithCode(data, -32601)
        self.assertEqual(error['message'],  'Method not found')

        data = self.query(
            'compile',
            'select * from {{ reff("nonsource_descendant") }}',
            name='mymodel'
        ).json()
        error = self.assertIsErrorWithCode(data, 10004)
        self.assertEqual(error['message'], 'Compilation Error')
        self.assertIn('data', error)
        error_data = error['data']
        self.assertEqual(error_data['type'], 'CompilationException')
        self.assertEqual(
            error_data['message'],
            "Compilation Error in rpc mymodel (from remote system)\n  'reff' is undefined"
        )
        self.assertIn('logs', error_data)
        self.assertTrue(len(error_data['logs']) > 0)

        data = self.query(
            'run',
            'hi this is not sql',
            name='foo'
        ).json()
        error = self.assertIsErrorWithCode(data, 10003)
        self.assertEqual(error['message'], 'Database Error')
        self.assertIn('data', error)
        error_data = error['data']
        self.assertEqual(error_data['type'], 'DatabaseException')
        self.assertEqual(
            error_data['message'],
            'Database Error\n  syntax error at or near "hi"\n  LINE 1: hi this is not sql\n          ^'
        )
        self.assertIn('logs', error_data)
        self.assertTrue(len(error_data['logs']) > 0)

        macro_no_override = self.query(
            'run',
            'select {{ happy_little_macro() }}',
            name='foo',
        ).json()
        self.assertIsErrorWithCode(macro_no_override, 10003)
        self.assertEqual(error['message'], 'Database Error')
        self.assertIn('data', error)
        error_data = error['data']
        self.assertEqual(error_data['type'], 'DatabaseException')

    @use_profile('postgres')
    def test_timeout(self):
        data = self.query(
            'run',
            'select from pg_sleep(5)',
            name='foo',
            timeout=1
        ).json()
        error = self.assertIsErrorWithCode(data, 10008)
        self.assertEqual(error['message'], 'RPC timeout error')
        self.assertIn('data', error)
        error_data = error['data']
        self.assertIn('timeout', error_data)
        self.assertEqual(error_data['timeout'], 1)
        self.assertIn('message', error_data)
        self.assertEqual(error_data['message'], 'RPC timed out after 1s')
        self.assertIn('logs', error_data)
        self.assertTrue(len(error_data['logs']) > 0)
