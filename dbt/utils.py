import os
import json

import dbt.project

from dbt.compat import basestring
from dbt.logger import GLOBAL_LOGGER as logger

DBTConfigKeys = [
    'enabled',
    'materialized',
    'dist',
    'sort',
    'sql_where',
    'unique_key',
    'sort_type',
    'pre-hook',
    'post-hook',
    'vars'
]


class This(object):
    def __init__(self, schema, table, name):
        self.schema = schema
        self.table = table
        self.name = table if name is None else name

    def schema_table(self, schema, table):
        return '"{}"."{}"'.format(schema, table)

    def __repr__(self):
        return self.schema_table(self.schema, self.table)


def compiler_error(model, msg):
    if model is None:
        name = '<None>'
    elif isinstance(model, str):
        name = model
    elif isinstance(model, dict):
        name = model.get('name')
    else:
        name = model.nice_name

    raise RuntimeError(
        "! Compilation error while compiling model {}:\n! {}\n"
        .format(name, msg)
    )


def compiler_warning(model, msg):
    logger.info(
        "* Compilation warning while compiling model {}:\n* {}\n"
        .format(model.nice_name, msg)
    )


class Var(object):
    UndefinedVarError = "Required var '{}' not found in config:\nVars "\
                        "supplied to {} = {}"
    NoneVarError = "Supplied var '{}' is undefined in config:\nVars supplied"\
                   "to {} = {}"

    def __init__(self, model, context):
        self.model = model
        self.context = context

        if isinstance(model, dict) and model.get('unique_id'):
            self.local_vars = model.get('config', {}).get('vars')
            self.model_name = model.get('name')
        else:
            # still used for wrapping
            self.model_name = model.nice_name
            self.local_vars = model.config.get('vars', {})

    def pretty_dict(self, data):
        return json.dumps(data, sort_keys=True, indent=4)

    def __call__(self, var_name, default=None):
        pretty_vars = self.pretty_dict(self.local_vars)
        if var_name not in self.local_vars and default is None:
            compiler_error(
                self.model,
                self.UndefinedVarError.format(
                    var_name, self.model_name, pretty_vars
                )
            )
        elif var_name in self.local_vars:
            raw = self.local_vars[var_name]
            if raw is None:
                compiler_error(
                    self.model,
                    self.NoneVarError.format(
                        var_name, self.model.nice_name, pretty_vars
                    )
                )

            # if bool/int/float/etc are passed in, don't compile anything
            if not isinstance(raw, basestring):
                return raw

            return dbt.clients.jinja.get_rendered(raw, self.context)
        else:
            return default


def model_cte_name(model):
    return '__dbt__CTE__{}'.format(model.get('name'))


def find_model_by_name(all_models, target_model_name,
                       target_model_package):

    for name, model in all_models.items():
        resource_type, package_name, model_name = name.split('.')

        if (resource_type == 'model' and
            ((target_model_name == model_name) and
             (target_model_package is None or
              target_model_package == package_name))):
            return model

    return None


def find_model_by_fqn(models, fqn):
    for model in models:
        if tuple(model.fqn) == tuple(fqn):
            return model

    raise RuntimeError(
        "Couldn't find a compiled model with fqn: '{}'".format(fqn)
    )


def dependency_projects(project):
    for obj in os.listdir(project['modules-path']):
        full_obj = os.path.join(project['modules-path'], obj)
        if os.path.isdir(full_obj):
            try:
                yield dbt.project.read_project(
                    os.path.join(full_obj, 'dbt_project.yml'),
                    project.profiles_dir,
                    profile_to_load=project.profile_to_load,
                    args=project.args)
            except dbt.project.DbtProjectError as e:
                logger.info(
                    "Error reading dependency project at {}".format(full_obj)
                )
                logger.info(str(e))


def split_path(path):
    norm = os.path.normpath(path)
    return path.split(os.sep)


# http://stackoverflow.com/questions/20656135/python-deep-merge-dictionary-data
def deep_merge(destination, source):
    if isinstance(source, dict):
        for key, value in source.items():
            if isinstance(value, dict):
                node = destination.setdefault(key, {})
                deep_merge(node, value)
            elif isinstance(value, tuple) or isinstance(value, list):
                if key in destination:
                    destination[key] = list(value) + list(destination[key])
                else:
                    destination[key] = value
            else:
                destination[key] = value
        return destination


def to_unicode(s, encoding):
    try:
        unicode
        return unicode(s, encoding)
    except NameError:
        return s


def to_string(s):
    try:
        unicode
        return s.encode('utf-8')
    except NameError:
        return s


def get_materialization(node):
    return node.get('config', {}).get('materialized')


def is_enabled(node):
    return node.get('config', {}).get('enabled') is True
