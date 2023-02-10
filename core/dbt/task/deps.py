from typing import Any, Optional
import yaml

import dbt.utils
import dbt.deprecations
import dbt.exceptions

from dbt.config.renderer import DbtProjectYamlRenderer
from dbt.config.project import package_config_from_data, package_data_from_root
from dbt.deps.base import downloads_directory
from dbt.deps.resolver import resolve_lock_packages, resolve_packages
from dbt.deps.registry import RegistryPinnedPackage

from dbt.events.proto_types import ListOfStrings
from dbt.events.functions import fire_event
from dbt.events.types import (
    DepsAddPackage,
    DepsFoundDuplicatePackage,
    DepsInstallInfo,
    DepsListSubdirectory,
    DepsLockCreated,
    DepsLockUpdating,
    DepsNoPackagesFound,
    DepsNotifyUpdatesAvailable,
    DepsStartPackageInstall,
    DepsUpdateAvailable,
    DepsUpToDate,
    DepsVersionMissing,
    Formatting,
)
from dbt.clients import system

from dbt.task.base import BaseTask, move_to_nearest_project_dir

from dbt.config import Project


def _create_packages_yml_entry(package, version, source):
    """Create a formatted entry to add to `packages.yml` or `package-lock.yml` file

    Args:
        package (str): Name of package to download
        version (str): Version of package to download
        source (str): Source of where to download package from

    Returns:
        dict: Formatted dict to write to `packages.yml` or `package-lock.yml` file
    """
    package_key = source
    version_key = "version"

    if source == "hub":
        package_key = "package"

    if source == "git":
        version_key = "revision"

    packages_yml_entry = {package_key: package}

    if version:
        if "," in version:
            version = version.split(",")

        packages_yml_entry[version_key] = version

    return packages_yml_entry


class DepsTask(BaseTask):
    def __init__(self, args: Any, project: Project):
        move_to_nearest_project_dir(project.project_root)
        super().__init__(args=args, config=None, project=project)
        self.cli_vars = args.vars

        if not system.path_exists(f"{self.project.project_root}/package-lock.yml"):
            LockTask(args, project).run()

    def track_package_install(
        self, package_name: str, source_type: str, version: Optional[str]
    ) -> None:
        # Hub packages do not need to be hashed, as they are public
        if source_type == "local":
            package_name = dbt.utils.md5(package_name)
            version = "local"
        elif source_type == "tarball":
            package_name = dbt.utils.md5(package_name)
            version = "tarball"
        elif source_type != "hub":
            package_name = dbt.utils.md5(package_name)
            version = dbt.utils.md5(version)

        dbt.tracking.track_package_install(
            "deps",
            self.project.hashed_name(),
            {"name": package_name, "source": source_type, "version": version},
        )

    def run(self) -> None:
        if system.path_exists(self.project.packages_install_path):
            system.rmtree(self.project.packages_install_path)

        system.make_directory(self.project.packages_install_path)

        packages_lock_dict = package_data_from_root(self.project.project_root, "package-lock.yml")
        packages_lock_config = package_config_from_data(packages_lock_dict).packages

        if not packages_lock_config:
            fire_event(DepsNoPackagesFound())
            return

        with downloads_directory():
            lock_defined_deps = resolve_lock_packages(packages_lock_config)
            renderer = DbtProjectYamlRenderer(None, self.cli_vars)

            packages_to_upgrade = []

            for package in lock_defined_deps:
                package_name = package.name
                source_type = package.source_type()
                version = package.get_version()

                fire_event(DepsStartPackageInstall(package_name=package_name))
                package.install(self.project, renderer)

                fire_event(DepsInstallInfo(version_name=package.nice_version_name()))

                if isinstance(package, RegistryPinnedPackage):
                    version_latest = package.get_version_latest()

                    if version_latest != version:
                        packages_to_upgrade.append(package_name)
                        fire_event(DepsUpdateAvailable(version_latest=version_latest))
                    else:
                        fire_event(DepsUpToDate())

                if package.get_subdirectory():
                    fire_event(DepsListSubdirectory(subdirectory=package.get_subdirectory()))

                self.track_package_install(
                    package_name=package_name, source_type=source_type, version=version
                )

            if packages_to_upgrade:
                fire_event(Formatting(""))
                fire_event(DepsNotifyUpdatesAvailable(packages=ListOfStrings(packages_to_upgrade)))


class LockTask(BaseTask):
    def __init__(self, args: Any, project: Project):
        move_to_nearest_project_dir(project.project_root)
        super().__init__(args=args, config=None, project=project)
        self.cli_vars = args.vars

    def run(self):
        lock_filepath = f"{self.project.project_root}/package-lock.yml"

        packages = self.packages.packages.packages
        packages_installed = {"packages": []}

        if not packages:
            fire_event(DepsNoPackagesFound())
            return

        with downloads_directory():
            resolved_deps = resolve_packages(packages, self.project, self.cli_vars)

        # this loop is to create the package-lock.yml in the same format as original packages.yml
        # package-lock.yml includes both the stated packages in packages.yml along with dependent packages
        for package in resolved_deps:
            lock_entry = _create_packages_yml_entry(
                package.name, package.get_version(), package.source_type()
            )
            packages_installed["packages"].append(lock_entry)

        with open(lock_filepath, "w") as lock_obj:
            yaml.safe_dump(packages_installed, lock_obj)

        fire_event(DepsLockCreated(lock_filepath=lock_filepath))


class AddTask(BaseTask):
    def __init__(self, args: Any, project: Project):
        move_to_nearest_project_dir(project.project_root)
        super().__init__(args=args, config=None, project=project)
        self.cli_vars = args.vars

    def check_for_duplicate_packages(self, packages_yml):
        """Loop through contents of `packages.yml` to ensure no duplicate package names + versions.

        This duplicate check will take into consideration exact match of a package name, as well as
        a check to see if a package name exists within a name (i.e. a package name inside a git URL).

        Args:
            packages_yml (dict): In-memory read of `packages.yml` contents

        Returns:
            dict: Updated or untouched packages_yml contents
        """
        for i, pkg_entry in enumerate(packages_yml["packages"]):
            for val in pkg_entry.values():
                if self.args.package in val:
                    del packages_yml["packages"][i]

                    fire_event(DepsFoundDuplicatePackage(removed_package=pkg_entry))

        return packages_yml

    def run(self):
        packages_yml_filepath = f"{self.project.project_root}/packages.yml"

        if not system.path_exists(packages_yml_filepath):
            fire_event(DepsNoPackagesFound())
            return

        if not self.args.version and self.args.source != "local":
            fire_event(DepsVersionMissing(source=self.args.source))
            return

        new_package_entry = _create_packages_yml_entry(
            self.args.package, self.args.version, self.args.source
        )

        with open(packages_yml_filepath, "r") as user_yml_obj:
            packages_yml = yaml.safe_load(user_yml_obj)
            packages_yml = self.check_for_duplicate_packages(packages_yml)
            packages_yml["packages"].append(new_package_entry)

        if packages_yml:
            with open(packages_yml_filepath, "w") as pkg_obj:
                yaml.safe_dump(packages_yml, pkg_obj)

                fire_event(
                    DepsAddPackage(
                        package_name=self.args.package,
                        version=self.args.version,
                        packages_filepath=packages_yml_filepath,
                    )
                )

        if not self.args.dry_run:
            fire_event(
                DepsLockUpdating(lock_filepath=f"{self.project.project_root}/package-lock.yml")
            )
            LockTask(self.args, self.project).run()
