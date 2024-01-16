import dataclasses

import agate
import decimal
from multiprocessing import get_context
import unittest
from unittest import mock

from dbt.adapters.base import BaseRelation
from dbt.adapters.contracts.relation import Path
from dbt.context.manifest import generate_query_header_context
from dbt.task.debug import DebugTask

from dbt.adapters.postgres import PostgresAdapter
from dbt.adapters.postgres import Plugin as PostgresPlugin
from dbt.contracts.files import FileHash
from dbt.contracts.graph.manifest import ManifestStateCheck
from dbt_common.clients import agate_helper
from dbt.exceptions import DbtConfigError
from dbt_common.exceptions import DbtValidationError
from dbt.context.providers import generate_runtime_macro_context
from psycopg2 import extensions as psycopg2_extensions
from psycopg2 import DatabaseError

from .utils import (
    config_from_parts_or_dicts,
    inject_adapter,
    mock_connection,
    TestAdapterConversions,
    load_internal_manifest_macros,
    clear_plugin,
)

from dbt.flags import set_from_args
from argparse import Namespace

set_from_args(Namespace(WARN_ERROR=False), None)


class TestPostgresAdapter(unittest.TestCase):
    def setUp(self):
        project_cfg = {
            "name": "X",
            "version": "0.1",
            "profile": "test",
            "project-root": "/tmp/dbt/does-not-exist",
            "config-version": 2,
        }
        profile_cfg = {
            "outputs": {
                "test": {
                    "type": "postgres",
                    "dbname": "postgres",
                    "user": "root",
                    "host": "thishostshouldnotexist",
                    "pass": "password",
                    "port": 5432,
                    "schema": "public",
                }
            },
            "target": "test",
        }

        self.config = config_from_parts_or_dicts(project_cfg, profile_cfg)
        self.mp_context = get_context("spawn")
        self._adapter = None

    @property
    def adapter(self):
        if self._adapter is None:
            self._adapter = PostgresAdapter(self.config, self.mp_context)
            inject_adapter(self._adapter, PostgresPlugin)
        return self._adapter

    @mock.patch("dbt.adapters.postgres.connections.psycopg2")
    def test_acquire_connection_validations(self, psycopg2):
        try:
            connection = self.adapter.acquire_connection("dummy")
        except DbtValidationError as e:
            self.fail("got DbtValidationError: {}".format(str(e)))
        except BaseException as e:
            self.fail("acquiring connection failed with unknown exception: {}".format(str(e)))
        self.assertEqual(connection.type, "postgres")

        psycopg2.connect.assert_not_called()
        connection.handle
        psycopg2.connect.assert_called_once()

    @mock.patch("dbt.adapters.postgres.connections.psycopg2")
    def test_acquire_connection(self, psycopg2):
        connection = self.adapter.acquire_connection("dummy")

        psycopg2.connect.assert_not_called()
        connection.handle
        self.assertEqual(connection.state, "open")
        self.assertNotEqual(connection.handle, None)
        psycopg2.connect.assert_called_once()

    def test_cancel_open_connections_empty(self):
        self.assertEqual(len(list(self.adapter.cancel_open_connections())), 0)

    def test_cancel_open_connections_master(self):
        key = self.adapter.connections.get_thread_identifier()
        self.adapter.connections.thread_connections[key] = mock_connection("master")
        self.assertEqual(len(list(self.adapter.cancel_open_connections())), 0)

    def test_cancel_open_connections_single(self):
        master = mock_connection("master")
        model = mock_connection("model")
        key = self.adapter.connections.get_thread_identifier()
        model.handle.get_backend_pid.return_value = 42
        self.adapter.connections.thread_connections.update(
            {
                key: master,
                1: model,
            }
        )
        with mock.patch.object(self.adapter.connections, "add_query") as add_query:
            query_result = mock.MagicMock()
            add_query.return_value = (None, query_result)

            self.assertEqual(len(list(self.adapter.cancel_open_connections())), 1)

            add_query.assert_called_once_with("select pg_terminate_backend(42)")

        master.handle.get_backend_pid.assert_not_called()

    @mock.patch("dbt.adapters.postgres.connections.psycopg2")
    def test_default_connect_timeout(self, psycopg2):
        connection = self.adapter.acquire_connection("dummy")

        psycopg2.connect.assert_not_called()
        connection.handle
        psycopg2.connect.assert_called_once_with(
            dbname="postgres",
            user="root",
            host="thishostshouldnotexist",
            password="password",
            port=5432,
            connect_timeout=10,
            application_name="dbt",
        )

    @mock.patch("dbt.adapters.postgres.connections.psycopg2")
    def test_changed_connect_timeout(self, psycopg2):
        self.config.credentials = self.config.credentials.replace(connect_timeout=30)
        connection = self.adapter.acquire_connection("dummy")

        psycopg2.connect.assert_not_called()
        connection.handle
        psycopg2.connect.assert_called_once_with(
            dbname="postgres",
            user="root",
            host="thishostshouldnotexist",
            password="password",
            port=5432,
            connect_timeout=30,
            application_name="dbt",
        )

    @mock.patch("dbt.adapters.postgres.connections.psycopg2")
    def test_default_keepalive(self, psycopg2):
        connection = self.adapter.acquire_connection("dummy")

        psycopg2.connect.assert_not_called()
        connection.handle
        psycopg2.connect.assert_called_once_with(
            dbname="postgres",
            user="root",
            host="thishostshouldnotexist",
            password="password",
            port=5432,
            connect_timeout=10,
            application_name="dbt",
        )

    @mock.patch("dbt.adapters.postgres.connections.psycopg2")
    def test_changed_keepalive(self, psycopg2):
        self.config.credentials = self.config.credentials.replace(keepalives_idle=256)
        connection = self.adapter.acquire_connection("dummy")

        psycopg2.connect.assert_not_called()
        connection.handle
        psycopg2.connect.assert_called_once_with(
            dbname="postgres",
            user="root",
            host="thishostshouldnotexist",
            password="password",
            port=5432,
            connect_timeout=10,
            keepalives_idle=256,
            application_name="dbt",
        )

    @mock.patch("dbt.adapters.postgres.connections.psycopg2")
    def test_default_application_name(self, psycopg2):
        connection = self.adapter.acquire_connection("dummy")

        psycopg2.connect.assert_not_called()
        connection.handle
        psycopg2.connect.assert_called_once_with(
            dbname="postgres",
            user="root",
            host="thishostshouldnotexist",
            password="password",
            port=5432,
            connect_timeout=10,
            application_name="dbt",
        )

    @mock.patch("dbt.adapters.postgres.connections.psycopg2")
    def test_changed_application_name(self, psycopg2):
        self.config.credentials = self.config.credentials.replace(application_name="myapp")
        connection = self.adapter.acquire_connection("dummy")

        psycopg2.connect.assert_not_called()
        connection.handle
        psycopg2.connect.assert_called_once_with(
            dbname="postgres",
            user="root",
            host="thishostshouldnotexist",
            password="password",
            port=5432,
            connect_timeout=10,
            application_name="myapp",
        )

    @mock.patch("dbt.adapters.postgres.connections.psycopg2")
    def test_role(self, psycopg2):
        self.config.credentials = self.config.credentials.replace(role="somerole")
        connection = self.adapter.acquire_connection("dummy")

        cursor = connection.handle.cursor()

        cursor.execute.assert_called_once_with("set role somerole")

    @mock.patch("dbt.adapters.postgres.connections.psycopg2")
    def test_search_path(self, psycopg2):
        self.config.credentials = self.config.credentials.replace(search_path="test")
        connection = self.adapter.acquire_connection("dummy")

        psycopg2.connect.assert_not_called()
        connection.handle
        psycopg2.connect.assert_called_once_with(
            dbname="postgres",
            user="root",
            host="thishostshouldnotexist",
            password="password",
            port=5432,
            connect_timeout=10,
            application_name="dbt",
            options="-c search_path=test",
        )

    @mock.patch("dbt.adapters.postgres.connections.psycopg2")
    def test_sslmode(self, psycopg2):
        self.config.credentials = self.config.credentials.replace(sslmode="require")
        connection = self.adapter.acquire_connection("dummy")

        psycopg2.connect.assert_not_called()
        connection.handle
        psycopg2.connect.assert_called_once_with(
            dbname="postgres",
            user="root",
            host="thishostshouldnotexist",
            password="password",
            port=5432,
            connect_timeout=10,
            sslmode="require",
            application_name="dbt",
        )

    @mock.patch("dbt.adapters.postgres.connections.psycopg2")
    def test_ssl_parameters(self, psycopg2):
        self.config.credentials = self.config.credentials.replace(sslmode="verify-ca")
        self.config.credentials = self.config.credentials.replace(sslcert="service.crt")
        self.config.credentials = self.config.credentials.replace(sslkey="service.key")
        self.config.credentials = self.config.credentials.replace(sslrootcert="ca.crt")
        connection = self.adapter.acquire_connection("dummy")

        psycopg2.connect.assert_not_called()
        connection.handle
        psycopg2.connect.assert_called_once_with(
            dbname="postgres",
            user="root",
            host="thishostshouldnotexist",
            password="password",
            port=5432,
            connect_timeout=10,
            sslmode="verify-ca",
            sslcert="service.crt",
            sslkey="service.key",
            sslrootcert="ca.crt",
            application_name="dbt",
        )

    @mock.patch("dbt.adapters.postgres.connections.psycopg2")
    def test_schema_with_space(self, psycopg2):
        self.config.credentials = self.config.credentials.replace(search_path="test test")
        connection = self.adapter.acquire_connection("dummy")

        psycopg2.connect.assert_not_called()
        connection.handle
        psycopg2.connect.assert_called_once_with(
            dbname="postgres",
            user="root",
            host="thishostshouldnotexist",
            password="password",
            port=5432,
            connect_timeout=10,
            application_name="dbt",
            options="-c search_path=test\ test",  # noqa: [W605]
        )

    @mock.patch("dbt.adapters.postgres.connections.psycopg2")
    def test_set_zero_keepalive(self, psycopg2):
        self.config.credentials = self.config.credentials.replace(keepalives_idle=0)
        connection = self.adapter.acquire_connection("dummy")

        psycopg2.connect.assert_not_called()
        connection.handle
        psycopg2.connect.assert_called_once_with(
            dbname="postgres",
            user="root",
            host="thishostshouldnotexist",
            password="password",
            port=5432,
            connect_timeout=10,
            application_name="dbt",
        )

    @mock.patch.object(PostgresAdapter, "execute_macro")
    @mock.patch.object(PostgresAdapter, "_get_catalog_relations")
    def test_get_catalog_various_schemas(self, mock_get_relations, mock_execute):
        self.catalog_test(mock_get_relations, mock_execute, False)

    @mock.patch.object(PostgresAdapter, "execute_macro")
    @mock.patch.object(PostgresAdapter, "_get_catalog_relations")
    def test_get_filtered_catalog(self, mock_get_relations, mock_execute):
        self.catalog_test(mock_get_relations, mock_execute, True)

    def catalog_test(self, mock_get_relations, mock_execute, filtered=False):
        column_names = ["table_database", "table_schema", "table_name"]
        relations = [
            BaseRelation(path=Path(database="dbt", schema="foo", identifier="bar")),
            BaseRelation(path=Path(database="dbt", schema="FOO", identifier="baz")),
            BaseRelation(path=Path(database="dbt", schema=None, identifier="bar")),
            BaseRelation(path=Path(database="dbt", schema="quux", identifier="bar")),
            BaseRelation(path=Path(database="dbt", schema="skip", identifier="bar")),
        ]
        rows = list(map(lambda x: dataclasses.astuple(x.path), relations))
        mock_execute.return_value = agate.Table(rows=rows, column_names=column_names)

        mock_get_relations.return_value = relations

        relation_configs = []
        used_schemas = {("dbt", "foo"), ("dbt", "quux")}

        if filtered:
            catalog, exceptions = self.adapter.get_filtered_catalog(
                relation_configs, used_schemas, set([relations[0], relations[3]])
            )
        else:
            catalog, exceptions = self.adapter.get_catalog(relation_configs, used_schemas)

        tupled_catalog = set(map(tuple, catalog))
        if filtered:
            self.assertEqual(tupled_catalog, {rows[0], rows[3]})
        else:
            self.assertEqual(tupled_catalog, {rows[0], rows[1], rows[3]})

        self.assertEqual(exceptions, [])


class TestConnectingPostgresAdapter(unittest.TestCase):
    def setUp(self):
        self.target_dict = {
            "type": "postgres",
            "dbname": "postgres",
            "user": "root",
            "host": "thishostshouldnotexist",
            "pass": "password",
            "port": 5432,
            "schema": "public",
        }

        profile_cfg = {
            "outputs": {
                "test": self.target_dict,
            },
            "target": "test",
        }
        project_cfg = {
            "name": "X",
            "version": "0.1",
            "profile": "test",
            "project-root": "/tmp/dbt/does-not-exist",
            "quoting": {
                "identifier": False,
                "schema": True,
            },
            "config-version": 2,
        }

        self.config = config_from_parts_or_dicts(project_cfg, profile_cfg)
        self.mp_context = get_context("spawn")

        self.handle = mock.MagicMock(spec=psycopg2_extensions.connection)
        self.cursor = self.handle.cursor.return_value
        self.mock_execute = self.cursor.execute
        self.patcher = mock.patch("dbt.adapters.postgres.connections.psycopg2")
        self.psycopg2 = self.patcher.start()

        # Create the Manifest.state_check patcher
        @mock.patch("dbt.parser.manifest.ManifestLoader.build_manifest_state_check")
        def _mock_state_check(self):
            all_projects = self.all_projects
            return ManifestStateCheck(
                vars_hash=FileHash.from_contents("vars"),
                project_hashes={name: FileHash.from_contents(name) for name in all_projects},
                profile_hash=FileHash.from_contents("profile"),
            )

        self.load_state_check = mock.patch(
            "dbt.parser.manifest.ManifestLoader.build_manifest_state_check"
        )
        self.mock_state_check = self.load_state_check.start()
        self.mock_state_check.side_effect = _mock_state_check

        self.psycopg2.connect.return_value = self.handle
        self.adapter = PostgresAdapter(self.config, self.mp_context)
        self.adapter.set_macro_resolver(load_internal_manifest_macros(self.config))
        self.adapter.set_macro_context_generator(generate_runtime_macro_context)
        self.adapter.connections.set_query_header(
            generate_query_header_context(self.config, self.adapter.get_macro_resolver())
        )
        self.qh_patch = mock.patch.object(self.adapter.connections.query_header, "add")
        self.mock_query_header_add = self.qh_patch.start()
        self.mock_query_header_add.side_effect = lambda q: "/* dbt */\n{}".format(q)
        self.adapter.acquire_connection()
        inject_adapter(self.adapter, PostgresPlugin)

    def tearDown(self):
        # we want a unique self.handle every time.
        self.adapter.cleanup_connections()
        self.qh_patch.stop()
        self.patcher.stop()
        self.load_state_check.stop()
        clear_plugin(PostgresPlugin)

    def test_quoting_on_drop_schema(self):
        relation = self.adapter.Relation.create(
            database="postgres",
            schema="test_schema",
            quote_policy=self.adapter.config.quoting,
        )
        self.adapter.drop_schema(relation)

        self.mock_execute.assert_has_calls(
            [mock.call('/* dbt */\ndrop schema if exists "test_schema" cascade', None)]
        )

    def test_quoting_on_drop(self):
        relation = self.adapter.Relation.create(
            database="postgres",
            schema="test_schema",
            identifier="test_table",
            type="table",
            quote_policy=self.adapter.config.quoting,
        )
        self.adapter.drop_relation(relation)
        self.mock_execute.assert_has_calls(
            [
                mock.call(
                    '/* dbt */\ndrop table if exists "postgres"."test_schema".test_table cascade',
                    None,
                )
            ]
        )

    def test_quoting_on_truncate(self):
        relation = self.adapter.Relation.create(
            database="postgres",
            schema="test_schema",
            identifier="test_table",
            type="table",
            quote_policy=self.adapter.config.quoting,
        )
        self.adapter.truncate_relation(relation)
        self.mock_execute.assert_has_calls(
            [mock.call('/* dbt */\ntruncate table "postgres"."test_schema".test_table', None)]
        )

    def test_quoting_on_rename(self):
        from_relation = self.adapter.Relation.create(
            database="postgres",
            schema="test_schema",
            identifier="table_a",
            type="table",
            quote_policy=self.adapter.config.quoting,
        )
        to_relation = self.adapter.Relation.create(
            database="postgres",
            schema="test_schema",
            identifier="table_b",
            type="table",
            quote_policy=self.adapter.config.quoting,
        )

        self.adapter.rename_relation(from_relation=from_relation, to_relation=to_relation)
        self.mock_execute.assert_has_calls(
            [
                mock.call(
                    '/* dbt */\nalter table "postgres"."test_schema".table_a rename to table_b',
                    None,
                )
            ]
        )

    def test_debug_connection_ok(self):
        DebugTask.validate_connection(self.target_dict)
        self.mock_execute.assert_has_calls([mock.call("/* dbt */\nselect 1 as id", None)])

    def test_debug_connection_fail_nopass(self):
        del self.target_dict["pass"]
        with self.assertRaises(DbtConfigError):
            DebugTask.validate_connection(self.target_dict)

    def test_connection_fail_select(self):
        self.mock_execute.side_effect = DatabaseError()
        with self.assertRaises(DbtConfigError):
            DebugTask.validate_connection(self.target_dict)
        self.mock_execute.assert_has_calls([mock.call("/* dbt */\nselect 1 as id", None)])

    def test_dbname_verification_is_case_insensitive(self):
        # Override adapter settings from setUp()
        self.target_dict["dbname"] = "Postgres"
        profile_cfg = {
            "outputs": {
                "test": self.target_dict,
            },
            "target": "test",
        }
        project_cfg = {
            "name": "X",
            "version": "0.1",
            "profile": "test",
            "project-root": "/tmp/dbt/does-not-exist",
            "quoting": {
                "identifier": False,
                "schema": True,
            },
            "config-version": 2,
        }
        self.config = config_from_parts_or_dicts(project_cfg, profile_cfg)
        self.mp_context = get_context("spawn")
        self.adapter.cleanup_connections()
        self._adapter = PostgresAdapter(self.config, self.mp_context)
        self.adapter.verify_database("postgres")


class TestPostgresFilterCatalog(unittest.TestCase):
    def test__catalog_filter_table(self):
        used_schemas = [["a", "B"], ["a", "1234"]]
        column_names = ["table_name", "table_database", "table_schema", "something"]
        rows = [
            ["foo", "a", "b", "1234"],  # include
            ["foo", "a", "1234", "1234"],  # include, w/ table schema as str
            ["foo", "c", "B", "1234"],  # skip
            ["1234", "A", "B", "1234"],  # include, w/ table name as str
        ]
        table = agate.Table(rows, column_names, agate_helper.DEFAULT_TYPE_TESTER)

        result = PostgresAdapter._catalog_filter_table(table, used_schemas)
        assert len(result) == 3
        for row in result.rows:
            assert isinstance(row["table_schema"], str)
            assert isinstance(row["table_database"], str)
            assert isinstance(row["table_name"], str)
            assert isinstance(row["something"], decimal.Decimal)


class TestPostgresAdapterConversions(TestAdapterConversions):
    def test_convert_text_type(self):
        rows = [
            ["", "a1", "stringval1"],
            ["", "a2", "stringvalasdfasdfasdfa"],
            ["", "a3", "stringval3"],
        ]
        agate_table = self._make_table_of(rows, agate.Text)
        expected = ["text", "text", "text"]
        for col_idx, expect in enumerate(expected):
            assert PostgresAdapter.convert_text_type(agate_table, col_idx) == expect

    def test_convert_number_type(self):
        rows = [
            ["", "23.98", "-1"],
            ["", "12.78", "-2"],
            ["", "79.41", "-3"],
        ]
        agate_table = self._make_table_of(rows, agate.Number)
        expected = ["integer", "float8", "integer"]
        for col_idx, expect in enumerate(expected):
            assert PostgresAdapter.convert_number_type(agate_table, col_idx) == expect

    def test_convert_boolean_type(self):
        rows = [
            ["", "false", "true"],
            ["", "false", "false"],
            ["", "false", "true"],
        ]
        agate_table = self._make_table_of(rows, agate.Boolean)
        expected = ["boolean", "boolean", "boolean"]
        for col_idx, expect in enumerate(expected):
            assert PostgresAdapter.convert_boolean_type(agate_table, col_idx) == expect

    def test_convert_datetime_type(self):
        rows = [
            ["", "20190101T01:01:01Z", "2019-01-01 01:01:01"],
            ["", "20190102T01:01:01Z", "2019-01-01 01:01:01"],
            ["", "20190103T01:01:01Z", "2019-01-01 01:01:01"],
        ]
        agate_table = self._make_table_of(
            rows, [agate.DateTime, agate_helper.ISODateTime, agate.DateTime]
        )
        expected = [
            "timestamp without time zone",
            "timestamp without time zone",
            "timestamp without time zone",
        ]
        for col_idx, expect in enumerate(expected):
            assert PostgresAdapter.convert_datetime_type(agate_table, col_idx) == expect

    def test_convert_date_type(self):
        rows = [
            ["", "2019-01-01", "2019-01-04"],
            ["", "2019-01-02", "2019-01-04"],
            ["", "2019-01-03", "2019-01-04"],
        ]
        agate_table = self._make_table_of(rows, agate.Date)
        expected = ["date", "date", "date"]
        for col_idx, expect in enumerate(expected):
            assert PostgresAdapter.convert_date_type(agate_table, col_idx) == expect

    def test_convert_time_type(self):
        # dbt's default type testers actually don't have a TimeDelta at all.
        agate.TimeDelta
        rows = [
            ["", "120s", "10s"],
            ["", "3m", "11s"],
            ["", "1h", "12s"],
        ]
        agate_table = self._make_table_of(rows, agate.TimeDelta)
        expected = ["time", "time", "time"]
        for col_idx, expect in enumerate(expected):
            assert PostgresAdapter.convert_time_type(agate_table, col_idx) == expect
