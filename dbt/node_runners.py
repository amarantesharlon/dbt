
from dbt.logger import GLOBAL_LOGGER as logger
from dbt.exceptions import NotImplementedException
from dbt.utils import RunHookType, NodeType, get_nodes_by_tags, get_materialization

import dbt.utils
import dbt.tracking
import dbt.ui.printer
import dbt.flags
import dbt.schema

import dbt.clients.jinja
import time


def track_model_run(index, num_nodes, run_model_result):
    invocation_id = dbt.tracking.active_user.invocation_id
    dbt.tracking.track_model_run({
        "invocation_id": invocation_id,
        "index": index,
        "total": num_nodes,
        "execution_time": run_model_result.execution_time,
        "run_status": run_model_result.status,
        "run_skipped": run_model_result.skip,
        "run_error": run_model_result.error,
        "model_materialization": dbt.utils.get_materialization(run_model_result.node),  # noqa
        "model_id": dbt.utils.get_hash(run_model_result.node),
        "hashed_contents": dbt.utils.get_hashed_contents(run_model_result.node),  # noqa
    })


class RunModelResult(object):
    def __init__(self, node, error=None, skip=False, status=None,
                 failed=None, execution_time=0):
        self.node = node
        self.error = error
        self.skip = skip
        self.fail = failed
        self.status = status
        self.execution_time = execution_time

    @property
    def errored(self):
        return self.error is not None

    @property
    def failed(self):
        return self.fail

    @property
    def skipped(self):
        return self.skip


class BaseRunner(object):
    print_header = True

    def __init__(self, project, adapter, node, node_index, num_nodes):
        self.project = project
        self.profile = project.run_environment()
        self.adapter = adapter
        self.node = node
        self.node_index = node_index
        self.num_nodes = num_nodes

        self.skip = False

    def error_handler(self, func):
        catchable_errors = (dbt.exceptions.CompilationException,
                            dbt.exceptions.RuntimeException)

        result = RunModelResult(self.node)

        try:
            status = func(*args, **kwargs)
            result.status = status

        except catchable_errors as e:
            result.error = str(e)
            result.status = 'ERROR'

        except dbt.exceptions.InternalException as e:
            build_path = node.get('build_path')
            prefix = 'Internal error executing {}'.format(build_path)

            error = "{prefix}\n{error}\n\n{note}".format(
                         prefix=dbt.ui.printer.red(prefix),
                         error=str(e).strip(),
                         note=INTERNAL_ERROR_STRING)
            logger.debug(error)

            result.error = str(e)
            result.status = 'ERROR'

        except Exception as e:
            prefix = "Unhandled error while executing {filepath}".format(
                        filepath=node.get('build_path'))

            error = "{prefix}\n{error}".format(
                         prefix=dbt.ui.printer.red(prefix),
                         error=str(e).strip())

            logger.debug(error)
            raise e

        finally:
            adapter.release_connection(self.profile, node.get('name'))

        return result

    @classmethod
    def get_schema(cls, adapter, profile):
        return adapter.get_default_schema(profile)

    def before_execute(self):
        raise NotImplementedException()

    def execute(self, flat_graph, existing):
        raise NotImplementedException()

    def run(self, flat_graph, existing):
        if self.skip:
            return self.on_skip()

        self.before_execute()
        started = time.time()
        result = self.execute(flat_graph, existing)
        result.execution_time = time.time() - started
        self.after_execute(result)

        return result

    def after_execute(self, result):
        raise NotImplementedException()

    def on_skip(self):
        schema_name = self.get_schema(self.adapter, self.profile)

        node_name = self.node.get('name')
        dbt.ui.printer.print_skip_line(self.node, schema_name, node_name,
                                       self.node_index, self.num_nodes)

        node_result = RunModelResult(self.node, skip=True)
        return node_result

    def skip(self):
        self.skip = True

    @classmethod
    def before_run(self, project, adapter, flat_graph):
        pass

    @classmethod
    def after_run(self, project, adapter, results, flat_graph, elapsed):
        pass


class CompileRunner(BaseRunner):
    print_header = False

    def before_execute(self):
        pass

    def after_execute(self, result):
        pass

    def execute(self, flat_graph, existing):
        compiled_node = self.compile(flat_graph)
        return RunModelResult(compiled_node)

    def compile(self, flat_graph):
        return self.compile_node(self.adapter, self.project, self.node, flat_graph)

    @classmethod
    def compile_node(cls, adapter, project, node, flat_graph):
        compiler = dbt.compilation.Compiler(project)
        node = compiler.compile_node(node, flat_graph)
        node = cls.inject_runtime_config(adapter, project, node)

        return node

    @classmethod
    def inject_runtime_config(cls, adapter, project, node):
        wrapped_sql = node.get('wrapped_sql')
        context = cls.node_context(adapter, project, node)
        sql = dbt.clients.jinja.get_rendered(wrapped_sql, context)
        node['wrapped_sql'] = sql
        return node

    @classmethod
    def node_context(cls, adapter, project, node):
        profile = project.run_environment()
        def call_get_columns_in_table(schema_name, table_name):
            return adapter.adapter.get_columns_in_table(
                profile, schema_name, table_name, node.get('name'))

        def call_get_missing_columns(from_schema, from_table,
                                     to_schema, to_table):
            return cls.adapter.get_missing_columns(
                profile, from_schema, from_table,
                to_schema, to_table, node.get('name'))

        def call_table_exists(schema, table):
            return cls.adapter.table_exists(
                profile, schema, table, node.get('name'))

        return {
            "run_started_at": dbt.tracking.active_user.run_started_at,
            "invocation_id": dbt.tracking.active_user.invocation_id,
            "get_columns_in_table": call_get_columns_in_table,
            "get_missing_columns": call_get_missing_columns,
            "already_exists": call_table_exists,
        }


class ModelRunner(CompileRunner):
    @classmethod
    def try_create_schema(cls, project, adapter):
        profile = project.run_environment()
        schema_name = cls.get_schema(adapter, profile)

        schema_exists = adapter.check_schema_exists(profile, schema_name)

        if schema_exists:
            logger.debug('schema {} already exists -- '
                         'not creating'.format(schema_name))
            return

        adapter.create_schema(profile, schema_name)

    @classmethod
    def run_hooks(cls, project, adapter, flat_graph, hook_type):
        profile = project.run_environment()

        nodes = flat_graph.get('nodes', {}).values()
        hooks = get_nodes_by_tags(nodes, {hook_type}, NodeType.Operation)

        for hook in hooks:
            compiled = cls.compile_node(adapter, project, hook, flat_graph)
            sql = compiled['wrapped_sql']
            adapter.execute_one(profile, sql, auto_begin=False)

    @classmethod
    def before_run(cls, project, adapter, flat_graph):
        cls.try_create_schema(project, adapter)
        cls.run_hooks(project, adapter, flat_graph, RunHookType.Start)

    @classmethod
    def print_results_line(cls, results, execution_time):
        nodes = [r.node for r in results]
        stat_line = dbt.ui.printer.get_counts(nodes)

        dbt.ui.printer.print_timestamped_line("")
        dbt.ui.printer.print_timestamped_line(
            "Finished running {stat_line} in {execution_time:0.2f}s."
            .format(stat_line=stat_line, execution_time=execution_time))

    @classmethod
    def after_run(cls, project, adapter, results, flat_graph, elapsed):
        cls.run_hooks(project, adapter, flat_graph, RunHookType.End)
        cls.print_results_line(results, elapsed)

    # TODO - terrible
    def do_execute_model(self, model, existing):
        schema = self.adapter.get_default_schema(self.profile)

        tmp_name = '{}__dbt_tmp'.format(model.get('name'))

        if dbt.flags.NON_DESTRUCTIVE or self.profile.get('type') == 'bigquery': # TODO
            # for non destructive mode, we only look at the already existing table.
            tmp_name = model.get('name')

        result = None

        # TRUNCATE / DROP
        if get_materialization(model) == 'table' and \
           dbt.flags.NON_DESTRUCTIVE and \
           existing.get(tmp_name) == 'table':
            # tables get truncated instead of dropped in non-destructive mode.
            self.adapter.truncate(
                profile=self.profile,
                table=tmp_name,
                model_name=model.get('name'))

        elif dbt.flags.NON_DESTRUCTIVE:
            # never drop existing relations in non destructive mode.
            pass

        elif (get_materialization(model) != 'incremental' and
              existing.get(tmp_name) is not None):
            # otherwise, for non-incremental things, drop them with IF EXISTS
            self.adapter.drop(
                profile=self.profile,
                relation=tmp_name,
                relation_type=existing.get(tmp_name),
                model_name=model.get('name'))

            # and update the list of what exists
            existing = self.adapter.query_for_existing(
                self.profile,
                schema,
                model_name=model.get('name'))

        # EXECUTE
        if get_materialization(model) == 'view' and dbt.flags.NON_DESTRUCTIVE and \
           model.get('name') in existing:
            # views don't need to be recreated in non destructive mode since they
            # will repopulate automatically. note that we won't run DDL for these
            # views either.
            pass
        elif dbt.utils.is_enabled(model) and get_materialization(model) != 'ephemeral':
            result = self.adapter.execute_model(self.profile, model)

        # DROP OLD RELATION AND RENAME
        if dbt.flags.NON_DESTRUCTIVE:
            # in non-destructive mode, we truncate and repopulate tables, and
            # don't modify views.
            pass
        elif get_materialization(model) in ['table', 'view']:
            # otherwise, drop tables and views, and rename tmp tables/views to
            # their new names
            if existing.get(model.get('name')) is not None:
                self.adapter.drop(
                    profile=self.profile,
                    relation=model.get('name'),
                    relation_type=existing.get(model.get('name')),
                    model_name=model.get('name'))

            self.adapter.rename(profile=self.profile,
                           from_name=tmp_name,
                           to_name=model.get('name'),
                           model_name=model.get('name'))


        self.adapter.commit_if_has_connection(self.profile, self.node.get('name'))
        return result

    def print_start_line(self):
        schema_name = self.get_schema(self.adapter, self.profile)
        dbt.ui.printer.print_model_start_line(self.node, schema_name,
                self.node_index, self.num_nodes)

    def print_result_line(self, result):
        schema_name = self.get_schema(self.adapter, self.profile)
        dbt.ui.printer.print_model_result_line(result, schema_name,
                self.node_index, self.num_nodes)

    def execute_model(self, flat_graph, existing):
        is_ephemeral = (dbt.utils.get_materialization(self.node) == 'ephemeral')
        compiled_node = self.compile(flat_graph)

        if not is_ephemeral:
            status = self.do_execute_model(compiled_node, existing)

        return RunModelResult(compiled_node, status=status)

    def before_execute(self):
        is_ephemeral = (dbt.utils.get_materialization(self.node) == 'ephemeral')
        if not is_ephemeral:
            self.print_start_line()

    def after_execute(self, result):
        track_model_run(self.node_index, self.num_nodes, result)

        is_ephemeral = (dbt.utils.get_materialization(self.node) == 'ephemeral')
        if not is_ephemeral:
            self.print_result_line(result)

    def execute(self, flat_graph, existing):
        run_model_result = self.execute_model(flat_graph, existing)
        return run_model_result

class TestRunner(CompileRunner):
    def print_start_line(self):
        schema_name = self.get_schema(self.adapter, self.profile)
        dbt.ui.printer.print_test_start_line(self.node, schema_name,
                self.node_index, self.num_nodes)

    def print_result_line(self, result):
        schema_name = self.get_schema(self.adapter, self.profile)
        dbt.ui.printer.print_test_result_line(result, schema_name,
                self.node_index, self.num_nodes)

    def execute_test(self, test):
        handle, cursor = self.adapter.execute_one(
            self.profile,
            test.get('wrapped_sql'),
            test.get('name'))

        # TODO 
        rows = cursor.fetchall()
        self.adapter.commit_if_has_connection(self.profile, self.node.get('name'))

        if len(rows) > 1:
            raise RuntimeError(
                "Bad test {name}: Returned {num_rows} rows instead of 1"
                .format(name=test.name, num_rows=len(rows)))

        row = rows[0]
        if len(row) > 1:
            raise RuntimeError(
                "Bad test {name}: Returned {num_cols} cols instead of 1"
                .format(name=test.name, num_cols=len(row)))

        return row[0]

    def before_execute(self):
        self.print_start_line()

    def execute(self, flat_graph, existing):
        test = self.compile(flat_graph)
        status = self.execute_test(test)
        return RunModelResult(test, status=status)

    def after_execute(self, result):
        self.print_result_line(result)


class ArchiveRunner(CompileRunner):
    def print_start_line(self):
        dbt.ui.printer.print_archive_start_line(self.node, self.node_index, self.num_nodes)

    def print_result_line(self, result):
        dbt.ui.printer.print_archive_result_line(result, self.node_index, self.num_nodes)

    def before_execute(self):
        self.print_start_line()

    def after_execute(self, result):
        self.print_result_line(result)

    def execute(self, flat_graph, existing):
        self.before_archive()
        started = time.time()
        status = self.execute_archive(self.project)
        execution_time = time.time() - started

        error = None # TODO
        result = RunModelResult(self.node, error=error, status=status,
                                execution_time=execution_time)
        self.after_archive(result)

        return result

    def execute_archive(self):
        node = self.node
        node_cfg = node.get('config', {})

        context = self.node_context(self.adapter, self.project, self.node)

        source_columns = self.adapter.get_columns_in_table(
            self.profile, node_cfg.get('source_schema'), node_cfg.get('source_table'))

        if len(source_columns) == 0:
            source_schema = node_cfg.get('source_schema')
            source_table = node_cfg.get('source_table')
            raise RuntimeError(
                'Source table "{}"."{}" does not '
                'exist'.format(source_schema, source_table))

        dest_columns = source_columns + [
            dbt.schema.Column("valid_from", "timestamp", None),
            dbt.schema.Column("valid_to", "timestamp", None),
            dbt.schema.Column("scd_id", "text", None),
            dbt.schema.Column("dbt_updated_at", "timestamp", None)
        ]

        self.adapter.create_table(
            self.profile,
            schema=node_cfg.get('target_schema'),
            table=node_cfg.get('target_table'),
            columns=dest_columns,
            sort='dbt_updated_at',
            dist='scd_id',
            model_name=node.get('name'))

        # TODO move this to inject_runtime_config, generate archive SQL
        # in wrap step. can't do this right now because we actually need
        # to inspect status of the schema at runtime and archive requires
        # a lot of information about the schema to generate queries.
        template_ctx = context.copy()
        template_ctx.update(node_cfg)

        select = dbt.clients.jinja.get_rendered(dbt.templates.SCDArchiveTemplate,
                                                template_ctx)

        insert_stmt = dbt.templates.ArchiveInsertTemplate().wrap(
            schema=node_cfg.get('target_schema'),
            table=node_cfg.get('target_table'),
            query=select,
            unique_key=node_cfg.get('unique_key'))

        node['wrapped_sql'] = dbt.clients.jinja.get_rendered(insert_stmt,
                                                             template_ctx)

        result = self.adapter.execute_model(
            profile=self.profile,
            model=node)

        return result
