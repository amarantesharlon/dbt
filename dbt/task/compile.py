from __future__ import print_function

from dbt.logger import GLOBAL_LOGGER as logger
from dbt.runner import RunManager
from dbt.node_runners import CompileRunner
from dbt.utils import NodeType


class CompileTask:
    def __init__(self, args, project):
        self.args = args
        self.project = project

    def run(self):
        runner = RunManager(
            self.project, self.project['target-path'], self.args
        )

        query = {
            "include": self.args.models,
            "exclude": self.args.exclude,
            "resource_types": NodeType.all,
            "tags": set()
        }

        runner.run(query, CompileRunner)

        logger.info('Done.')
