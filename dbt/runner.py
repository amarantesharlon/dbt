from __future__ import print_function

import hashlib
import psycopg2
import os
import sys
import logging
import time
import itertools
import re
import yaml
from datetime import datetime

from dbt.adapters.factory import get_adapter
from dbt.logger import GLOBAL_LOGGER as logger

from dbt.source import Source
from dbt.utils import find_model_by_fqn, find_model_by_name, \
    dependency_projects, get_materialization
from dbt.model import NodeType

import dbt.clients.jinja
import dbt.compilation
import dbt.exceptions
import dbt.linker
import dbt.tracking
import dbt.schema
import dbt.graph.selector
import dbt.model

from multiprocessing.dummy import Pool as ThreadPool

ABORTED_TRANSACTION_STRING = ("current transaction is aborted, commands "
                              "ignored until end of transaction block")


def get_timestamp():
    return time.strftime("%H:%M:%S")


def get_hash(model):
    return hashlib.md5(model.get('unique_id').encode('utf-8')).hexdigest()


def get_hashed_contents(model):
    return hashlib.md5(model.get('raw_sql').encode('utf-8')).hexdigest()


def is_enabled(model):
    return model.get('config', {}).get('enabled') is True


def print_timestamped_line(msg):
    logger.info("{} | {}".format(get_timestamp(), msg))


def print_fancy_output_line(msg, status, index, total, execution_time=None):
    prefix = "{timestamp} | {index} of {total} {message}".format(
        timestamp=get_timestamp(),
        index=index,
        total=total,
        message=msg)
    justified = prefix.ljust(80, ".")

    if execution_time is None:
        status_time = ""
    else:
        status_time = " in {execution_time:0.2f}s".format(
            execution_time=execution_time)

    output = "{justified} [{status}{status_time}]".format(
        justified=justified, status=status, status_time=status_time)

    logger.info(output)


def print_skip_line(model, schema, relation, index, num_models):
    msg = 'SKIP relation {}.{}'.format(schema, relation)
    print_fancy_output_line(msg, 'SKIP', index, num_models)


def print_counts(flat_nodes):
    counts = {}
    for node in flat_nodes:
        t = node.get('resource_type')
        counts[t] = counts.get(t, 0) + 1

    for k, v in counts.items():
        logger.info("")
        print_timestamped_line("Running {} {}s".format(v, k))
        print_timestamped_line("")


def print_start_line(node, schema_name, index, total):
    if node.get('resource_type') == NodeType.Model:
        print_model_start_line(node, schema_name, index, total)
    if node.get('resource_type') == NodeType.Test:
        print_test_start_line(node, schema_name, index, total)


def print_test_start_line(model, schema_name, index, total):
    msg = "START test {name}".format(
        name=model.get('name'))

    print_fancy_output_line(msg, 'RUN', index, total)


def print_model_start_line(model, schema_name, index, total):
    msg = "START {model_type} model {schema}.{relation}".format(
        model_type=get_materialization(model),
        schema=schema_name,
        relation=model.get('name'))

    print_fancy_output_line(msg, 'RUN', index, total)


def print_result_line(result, schema_name, index, total):
    node = result.node

    if node.get('resource_type') == NodeType.Model:
        print_model_result_line(result, schema_name, index, total)
    elif node.get('resource_type') == NodeType.Test:
        print_test_result_line(result, schema_name, index, total)


def print_test_result_line(result, schema_name, index, total):
    model = result.node
    info = 'PASS'

    if result.errored:
        info = "ERROR"
    elif result.status > 0:
        info = 'FAIL {}'.format(result.status)
    elif result.status == 0:
        info = 'PASS'
    else:
        raise RuntimeError("unexpected status: {}".format(result.status))

    print_fancy_output_line(
        "{info} {name}".format(
            info=info,
            name=model.get('name')),
        info,
        index,
        total,
        result.execution_time)


def execute_test(profile, test):
    adapter = get_adapter(profile)
    _, cursor = adapter.execute_one(
        profile,
        test.get('wrapped_sql'),
        test.get('name'))

    rows = cursor.fetchall()

    adapter.commit(profile)

    cursor.close()

    if len(rows) > 1:
        raise RuntimeError(
            "Bad test {name}: Returned {num_rows} rows instead of 1"
            .format(name=model.name, num_rows=len(rows)))

    row = rows[0]
    if len(row) > 1:
        raise RuntimeError(
            "Bad test {name}: Returned {num_cols} cols instead of 1"
            .format(name=model.name, num_cols=len(row)))

    return row[0]


def print_model_result_line(result, schema_name, index, total):
    model = result.node
    info = 'OK created'

    if result.errored:
        info = 'ERROR creating'

    print_fancy_output_line(
        "{info} {model_type} model {schema}.{relation}".format(
            info=info,
            model_type=get_materialization(model),
            schema=schema_name,
            relation=model.get('name')),
        result.status,
        index,
        total,
        result.execution_time)


def print_results_line(results, execution_time):
    stats = {}

    for result in results:
        stats[result.node.get('resource_type')] = stats.get(
            result.node.get('resource_type'), 0) + 1

    stat_line = ", ".join(
        ["{} {}s".format(ct, t) for t, ct in stats.items()])

    print_timestamped_line("")
    print_timestamped_line(
        "Finished running {stat_line} in {execution_time:0.2f}s."
        .format(stat_line=stat_line, execution_time=execution_time))


def execute_model(profile, model, existing):
    adapter = get_adapter(profile)
    schema = adapter.get_default_schema(profile)

    tmp_name = '{}__dbt_tmp'.format(model.get('name'))

    if dbt.flags.NON_DESTRUCTIVE:
        # for non destructive mode, we only look at the already existing table.
        tmp_name = model.get('name')

    result = None

    # TRUNCATE / DROP
    if get_materialization(model) == 'table' and \
       dbt.flags.NON_DESTRUCTIVE and \
       existing.get(tmp_name) == 'table':
        # tables get truncated instead of dropped in non-destructive mode.
        adapter.truncate(
            profile=profile,
            table=tmp_name,
            model_name=model.get('name'))

    elif dbt.flags.NON_DESTRUCTIVE:
        # never drop existing relations in non destructive mode.
        pass

    elif (get_materialization(model) != 'incremental' and
          existing.get(tmp_name) is not None):
        # otherwise, for non-incremental things, drop them with IF EXISTS
        adapter.drop(
            profile=profile,
            relation=tmp_name,
            relation_type=existing.get(tmp_name),
            model_name=model.get('name'))

        # and update the list of what exists
        existing = adapter.query_for_existing(profile, schema)

    # EXECUTE
    if get_materialization(model) == 'view' and dbt.flags.NON_DESTRUCTIVE and \
       model.get('name') in existing:
        # views don't need to be recreated in non destructive mode since they
        # will repopulate automatically. note that we won't run DDL for these
        # views either.
        pass
    elif is_enabled(model) and get_materialization(model) != 'ephemeral':
        result = adapter.execute_model(profile, model)

    # DROP OLD RELATION AND RENAME
    if dbt.flags.NON_DESTRUCTIVE:
        # in non-destructive mode, we truncate and repopulate tables, and
        # don't modify views.
        pass
    elif get_materialization(model) in ['table', 'view']:
        # otherwise, drop tables and views, and rename tmp tables/views to
        # their new names
        if existing.get(model.get('name')) is not None:
            adapter.drop(
                profile=profile,
                relation=model.get('name'),
                relation_type=existing.get(model.get('name')),
                model_name=model.get('name'))

        adapter.rename(profile=profile,
                       from_name=tmp_name,
                       to_name=model.get('name'),
                       model_name=model.get('name'))

    return result


def execute_archive(profile, node, context):
    adapter = get_adapter(profile)

    node_cfg = node.get('config', {})

    source_columns = adapter.get_columns_in_table(
        profile, node_cfg.get('source_schema'), node_cfg.get('source_table'))

    if len(source_columns) == 0:
        raise RuntimeError(
            'Source table "{}"."{}" does not '
            'exist'.format(source_schema, source_table))

    dest_columns = source_columns + [
        dbt.schema.Column("valid_from", "timestamp", None),
        dbt.schema.Column("valid_to", "timestamp", None),
        dbt.schema.Column("scd_id", "text", None),
        dbt.schema.Column("dbt_updated_at", "timestamp", None)
    ]

    adapter.create_table(
        profile,
        schema=node_cfg.get('target_schema'),
        table=node_cfg.get('target_table'),
        columns=dest_columns,
        sort=node_cfg.get('updated_at'),
        dist=node_cfg.get('unique_key'))

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

    result = adapter.execute_model(
        profile=profile,
        model=node)

    return result


def run_hooks(profile, hooks, context, source):
    if type(hooks) not in (list, tuple):
        hooks = [hooks]

    ctx = {
        "target": profile,
        "state": "start",
        "invocation_id": context['invocation_id'],
        "run_started_at": context['run_started_at']
    }

    compiled_hooks = [
        dbt.clients.jinja.get_rendered(hook, ctx) for hook in hooks
    ]

    adapter = get_adapter(profile)

    adapter.execute_all(
        profile=profile,
        queries=compiled_hooks,
        model_name=source)

    adapter.commit(profile)


class RunModelResult(object):
    def __init__(self, node, error=None, skip=False, status=None,
                 execution_time=0):
        self.node = node
        self.error = error
        self.skip = skip
        self.status = status
        self.execution_time = execution_time

    @property
    def errored(self):
        return self.error is not None

    @property
    def skipped(self):
        return self.skip


class RunManager(object):
    def __init__(self, project, target_path, args):
        self.project = project
        self.target_path = target_path
        self.args = args

        profile = self.project.run_environment()

        # TODO validate the number of threads
        if self.args.threads is None:
            self.threads = profile.get('threads', 1)
        else:
            self.threads = self.args.threads

        adapter = get_adapter(profile)
        schema_name = adapter.get_default_schema(profile)

        def call_get_columns_in_table(schema_name, table_name):
            return adapter.get_columns_in_table(
                profile, schema_name, table_name)

        def call_get_missing_columns(from_schema, from_table,
                                     to_schema, to_table):
            return adapter.get_missing_columns(
                profile, from_schema, from_table,
                to_schema, to_table)

        def call_table_exists(schema, table):
            return adapter.table_exists(
                profile, schema, table)

        self.context = {
            "run_started_at": datetime.now(),
            "invocation_id": dbt.tracking.active_user.invocation_id,
            "get_columns_in_table": call_get_columns_in_table,
            "get_missing_columns": call_get_missing_columns,
            "already_exists": call_table_exists,
        }

    def inject_runtime_config(self, node):
        sql = dbt.clients.jinja.get_rendered(node.get('wrapped_sql'),
                                             self.context)

        node['wrapped_sql'] = sql

        return node

    def deserialize_graph(self):
        logger.info("Loading dependency graph file.")

        base_target_path = self.project['target-path']
        graph_file = os.path.join(
            base_target_path,
            dbt.compilation.graph_file_name
        )

        return dbt.linker.from_file(graph_file)

    def execute_node(self, node, existing):
        profile = self.project.run_environment()

        logger.debug("executing node %s", node.get('unique_id'))

        if node.get('skip') is True:
            return RunModelResult(node, skip=True)

        node = self.inject_runtime_config(node)

        if node.get('resource_type') == NodeType.Model:
            result = execute_model(profile, node, existing)
        elif node.get('resource_type') == NodeType.Test:
            result = execute_test(profile, node)
        elif node.get('resource_type') == NodeType.Archive:
            result = execute_archive(profile, node, self.context)

        return result

    def safe_execute_node(self, data):
        node, existing = data

        start_time = time.time()

        error = None

        try:
            status = self.execute_node(node, existing)
        except (RuntimeError,
                dbt.exceptions.ProgrammingException,
                psycopg2.ProgrammingError,
                psycopg2.InternalError) as e:
            error = "Error executing {filepath}\n{error}".format(
                filepath=node.get('build_path'), error=str(e).strip())
            status = "ERROR"
            logger.debug(error)
            if type(e) == psycopg2.InternalError and \
               ABORTED_TRANSACTION_STRING == e.diag.message_primary:
                return RunModelResult(
                    node,
                    error='{}\n'.format(ABORTED_TRANSACTION_STRING),
                    status="SKIP")
        except Exception as e:
            error = ("Unhandled error while executing {filepath}\n{error}"
                     .format(
                         filepath=node.get('build_path'),
                         error=str(e).strip()))
            logger.debug(error)
            raise e

        execution_time = time.time() - start_time

        return RunModelResult(node,
                              error=error,
                              status=status,
                              execution_time=execution_time)

    def as_concurrent_dep_list(self, linker, nodes_to_run):
        dependency_list = linker.as_dependency_list(nodes_to_run)

        concurrent_dependency_list = []
        for level in dependency_list:
            node_level = [linker.get_node(node) for node in level]
            concurrent_dependency_list.append(node_level)

        return concurrent_dependency_list

    def on_model_failure(self, linker, selected_nodes):
        def skip_dependent(node):
            dependent_nodes = linker.get_dependent_nodes(node.get('unique_id'))
            for node in dependent_nodes:
                if node in selected_nodes:
                    node_data = linker.get_node(node)
                    node_data['skip'] = True
                    linker.update_node_data(node, node_data)

        return skip_dependent

    def execute_nodes(self, node_dependency_list, on_failure,
                      should_run_hooks=False):
        profile = self.project.run_environment()
        adapter = get_adapter(profile)
        schema_name = adapter.get_default_schema(profile)

        flat_nodes = list(itertools.chain.from_iterable(
            node_dependency_list))

        num_nodes = len(flat_nodes)

        if num_nodes == 0:
            logger.info("WARNING: Nothing to do. Try checking your model "
                        "configs and running `dbt compile`".format(
                            self.target_path))
            return []

        num_threads = self.threads
        logger.info("Concurrency: {} threads (target='{}')".format(
            num_threads, self.project.get_target().get('name'))
        )

        existing = adapter.query_for_existing(profile, schema_name)

        pool = ThreadPool(num_threads)

        print_counts(flat_nodes)

        start_time = time.time()

        if should_run_hooks:
            run_hooks(self.project.get_target(),
                      self.project.cfg.get('on-run-start', []),
                      self.context,
                      'on-run-start hooks')

        node_id_to_index_map = {node.get('unique_id'): i + 1 for (i, node)
                                in enumerate(flat_nodes)}

        def get_idx(node):
            return node_id_to_index_map[node.get('unique_id')]

        node_results = []
        for node_list in node_dependency_list:
            for i, node in enumerate([node for node in node_list
                                      if node.get('skip')]):
                print_skip_line(node, schema_name, node.get('name'),
                                get_idx(node), num_nodes)

                node_result = RunModelResult(node, skip=True)
                node_results.append(node_result)

            nodes_to_execute = [node for node in node_list
                                if not node.get('skip')]

            threads = self.threads
            num_nodes_this_batch = len(nodes_to_execute)
            node_index = 0

            def on_complete(run_model_results):
                for run_model_result in run_model_results:
                    node_results.append(run_model_result)

                    index = get_idx(run_model_result.node)

                    print_result_line(run_model_result,
                                      schema_name,
                                      index,
                                      num_nodes)

                    invocation_id = dbt.tracking.active_user.invocation_id
                    dbt.tracking.track_model_run({
                        "invocation_id": invocation_id,
                        "index": index,
                        "total": num_nodes,
                        "execution_time": run_model_result.execution_time,
                        "run_status": run_model_result.status,
                        "run_skipped": run_model_result.skip,
                        "run_error": run_model_result.error,
                        "model_materialization": get_materialization(run_model_result.node),  # noqa
                        "model_id": get_hash(run_model_result.node),
                        "hashed_contents": get_hashed_contents(run_model_result.node),  # noqa
                    })

                    if run_model_result.errored:
                        on_failure(run_model_result.node)
                        logger.info(run_model_result.error)

            while node_index < num_nodes_this_batch:
                local_nodes = []
                for i in range(
                        node_index,
                        min(node_index + threads, num_nodes_this_batch)):
                    node = nodes_to_execute[i]
                    local_nodes.append(node)

                    print_start_line(node,
                                     schema_name,
                                     get_idx(node),
                                     num_nodes)

                map_result = pool.map_async(
                    self.safe_execute_node,
                    [(node, existing,) for node in local_nodes],
                    callback=on_complete
                )
                map_result.wait()
                run_model_results = map_result.get()

                node_index += threads

        pool.close()
        pool.join()

        if should_run_hooks:
            run_hooks(self.project.get_target(),
                      self.project.cfg.get('on-run-end', []),
                      self.context,
                      'on-run-end hooks')

        execution_time = time.time() - start_time

        print_results_line(node_results, execution_time)

        return node_results

    def get_nodes_to_run(self, graph, include_spec, exclude_spec,
                         resource_types, tags):

        if include_spec is None:
            include_spec = ['*']

        if exclude_spec is None:
            exclude_spec = []

        to_run = [
            n for n in graph.nodes()
            if (graph.node.get(n).get('empty') is False and
                is_enabled(graph.node.get(n)))
        ]

        filtered_graph = graph.subgraph(to_run)
        selected_nodes = dbt.graph.selector.select_nodes(self.project,
                                                         filtered_graph,
                                                         include_spec,
                                                         exclude_spec)

        post_filter = [
            n for n in selected_nodes
            if ((graph.node.get(n).get('resource_type') in resource_types) and
                get_materialization(graph.node.get(n)) != 'ephemeral' and
                (len(tags) == 0 or
                 # does the node share any tags with the run?
                 bool(set(graph.node.get(n).get('tags')) & set(tags))))
        ]

        return set(post_filter)

    def try_create_schema(self):
        profile = self.project.run_environment()
        adapter = get_adapter(profile)

        try:
            schema_name = adapter.get_default_schema(profile)

            adapter.create_schema(profile, schema_name)
        except (dbt.exceptions.FailedToConnectException,
                psycopg2.OperationalError) as e:
            logger.info("ERROR: Could not connect to the target database. Try "
                        "`dbt debug` for more information.")
            logger.info(str(e))
            raise

    def run_types_from_graph(self, include_spec, exclude_spec,
                             resource_types, tags, should_run_hooks=False):
        linker = self.deserialize_graph()

        selected_nodes = self.get_nodes_to_run(
            linker.graph,
            include_spec,
            exclude_spec,
            resource_types,
            tags)

        dependency_list = self.as_concurrent_dep_list(
            linker,
            selected_nodes)

        self.try_create_schema()

        on_failure = self.on_model_failure(linker, selected_nodes)

        results = self.execute_nodes(dependency_list, on_failure,
                                     should_run_hooks)

        return results

    # ------------------------------------

    def run_models(self, include_spec, exclude_spec):
        return self.run_types_from_graph(include_spec,
                                         exclude_spec,
                                         resource_types=[NodeType.Model],
                                         tags=[],
                                         should_run_hooks=True)

    def run_tests(self, include_spec, exclude_spec, tags):
        return self.run_types_from_graph(include_spec,
                                         exclude_spec,
                                         [NodeType.Test],
                                         tags)

    def run_archives(self, include_spec, exclude_spec):
        return self.run_types_from_graph(include_spec,
                                         exclude_spec,
                                         [NodeType.Archive],
                                         [])
