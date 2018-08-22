import json
import os
import shutil

from dbt.adapters.factory import get_adapter
from dbt.clients.system import write_json
from dbt.compat import bigint
from dbt.include import DOCS_INDEX_FILE_PATH
import dbt.ui.printer
import dbt.utils
import dbt.compilation
import dbt.exceptions

from dbt.task.base_task import BaseTask


CATALOG_FILENAME = 'catalog.json'


def get_stripped_prefix(source, prefix):
    """Go through source, extracting every key/value pair where the key starts
    with the given prefix.
    """
    cut = len(prefix)
    return {
        k[cut:]: v for k, v in source.items()
        if k.startswith(prefix)
    }

def format_stats(stats):
    """Given a dictionary following this layout:

        {
            'encoded:label': 'Encoded',
            'encoded:value': 'Yes',
            'encoded:description': 'Indicates if the column is encoded',
            'encoded:include': True,

            'size:label': 'Size',
            'size:value': 128,
            'size:description': 'Size of the table in MB',
            'size:include': True,
        }

    format_stats will convert the dict into this structure:

        [
            {
                'id': 'encoded',
                'label': 'Encoded',
                'value': 'Yes',
                'description': 'Indicates if the column is encoded',
                'include': True
            },
            {
                'id': 'size',
                'label': 'Size',
                'value': 128,
                'description': 'Size of the table in MB',
                'include': True
            }
        ]
    """
    stats_collector = {}
    for stat_key, stat_value in stats.items():
        stat_id, stat_field = stat_key.split(":")

        stats_collector.setdefault(stat_id, {"id": stat_id})
        stats_collector[stat_id][stat_field] = stat_value

    return list(stats_tmp.values())

def unflatten(columns):
    """Given a list of column dictionaries following this layout:

        [{
            'column_comment': None,
            'column_index': Decimal('1'),
            'column_name': 'id',
            'column_type': 'integer',
            'table_comment': None,
            'table_name': 'test_table',
            'table_schema': 'test_schema',
            'table_type': 'BASE TABLE'
        }]

    unflatten will convert them into a dict with this nested structure:

        {
            'test_schema': {
                'test_table': {
                    'metadata': {
                        'comment': None,
                        'name': 'test_table',
                        'type': 'BASE TABLE',
                        'schema': 'test_schema',
                    },
                    'columns': {
                        "id": {
                            'type': 'integer',
                            'comment': None,
                            'index': bigint(1),
                            'name': 'id'
                        }
                    }
                }
            }
        }

    Required keys in each column: table_schema, table_name, column_index

    Keys prefixed with 'column_' end up in per-column data and keys prefixed
    with 'table_' end up in table metadata. Keys without either prefix are
    ignored.
    """
    structured = {}
    for entry in columns:
        schema_name = entry['table_schema']
        table_name = entry['table_name']

        if schema_name not in structured:
            structured[schema_name] = {}
        schema = structured[schema_name]

        if table_name not in schema:
            metadata = get_stripped_prefix(entry, 'table_')
            stats = get_stripped_prefix(entry, 'stats:')

            if stats.get('has_stats:value', False):
                stats_list = format_stats(stats)
            else:
                stats_list = []

            schema[table_name] = {'metadata': metadata, 'stats': stats_list, 'columns': {}}

        table = schema[table_name]

        column = get_stripped_prefix(entry, 'column_')

        # the index should really never be that big so it's ok to end up
        # serializing this to JSON (2^53 is the max safe value there)
        column['index'] = bigint(column['index'])
        table['columns'][column['name']] = column
    return structured


def incorporate_catalog_unique_ids(catalog, manifest):
    nodes = {}

    for schema, tables in catalog.items():
        for table_name, table_def in tables.items():
            unique_id = manifest.get_unique_id_for_schema_and_table(
                schema, table_name)

            if not unique_id:
                continue

            elif unique_id in nodes:
                dbt.exceptions.raise_ambiguous_catalog_match(
                    unique_id, nodes[unique_id], table_def)

            else:
                table_def['unique_id'] = unique_id
                nodes[unique_id] = table_def

    return nodes


class GenerateTask(BaseTask):
    def _get_manifest(self):
        compiler = dbt.compilation.Compiler(self.project)
        compiler.initialize()

        all_projects = compiler.get_all_projects()

        manifest = dbt.loader.GraphLoader.load_all(self.project, all_projects)
        return manifest

    def run(self):
        shutil.copyfile(
            DOCS_INDEX_FILE_PATH,
            os.path.join(self.project['target-path'], 'index.html'))

        manifest = self._get_manifest()
        profile = self.project.run_environment()
        adapter = get_adapter(profile)

        dbt.ui.printer.print_timestamped_line("Building catalog")
        results = adapter.get_catalog(profile, self.project.cfg, manifest)

        results = [
            dict(zip(results.column_names, row))
            for row in results
        ]

        nested_results = unflatten(results)
        results = {
            'nodes': incorporate_catalog_unique_ids(nested_results, manifest),
            'generated_at': dbt.utils.timestring(),
        }

        path = os.path.join(self.project['target-path'], CATALOG_FILENAME)
        write_json(path, results)

        dbt.ui.printer.print_timestamped_line(
            'Catalog written to {}'.format(os.path.abspath(path))
        )

        return results
