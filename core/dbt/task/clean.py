import os.path
import os
import shutil
from typing import Any, Dict, List

from dbt import deprecations
from dbt.config import Project
from dbt.events.functions import fire_event
from dbt.events.types import (
    CheckCleanPath,
    ConfirmCleanPath,
    ProtectedCleanPath,
    FinishedCleanPaths,
)
from dbt.task.base import BaseTask, move_to_nearest_project_dir


class CleanTask(BaseTask):
    # Note: CleanTask is the last task that uses UnsetProfileConfig,
    # and can be deleted once CleanTask no longer requires it.

    def run(self):
        """
        This function takes all the paths in the target file
        and cleans the project paths that are not protected.
        """
        move_to_nearest_project_dir(self.args.project_dir)
        if (
            "dbt_modules" in self.project.clean_targets
            and self.config.packages_install_path not in self.config.clean_targets
        ):
            deprecations.warn("install-packages-path")
        for path in self.project.clean_targets:
            fire_event(CheckCleanPath(path=path))
            if not is_protected_path(path, self.config.model_paths, self.config.test_paths):
                shutil.rmtree(path, True)
                fire_event(ConfirmCleanPath(path=path))
            else:
                fire_event(ProtectedCleanPath(path=path))

        fire_event(FinishedCleanPaths())

    @classmethod
    def from_project(cls, project: Project, cli_vars: Dict[str, Any]) -> "CleanTask":
        return cls(cli_vars, project)


def is_protected_path(path, model_paths: List[str], test_paths: List[str]) -> bool:
    """This function identifies protected paths."""
    abs_path = os.path.abspath(path)
    protected_paths = model_paths + test_paths + ["."]
    protected_abs_paths = [os.path.abspath(p) for p in protected_paths]
    return abs_path in set(protected_abs_paths) or is_project_path(abs_path)


def is_project_path(path) -> bool:
    """This function identifies project paths."""
    proj_path = os.path.abspath(".")
    return not os.path.commonprefix([proj_path, os.path.abspath(path)]) == proj_path
