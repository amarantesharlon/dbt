import pytest

from .util import (
    get_querier,
    ProjectDefinition,
)


def deps_with_packages(packages, bad_packages, project_dir, profiles_dir, schema):
    project = ProjectDefinition(
        models={
            'my_model.sql': 'select 1 as id',
        },
        packages={'packages': packages},
    )
    querier_ctx = get_querier(
        project_def=project,
        project_dir=project_dir,
        profiles_dir=profiles_dir,
        schema=schema,
        test_kwargs={},
    )

    with querier_ctx as querier:
        # we should be able to run sql queries at startup
        querier.async_wait_for_result(querier.run_sql('select 1 as id'))

        # the status should be something positive
        querier.is_result(querier.status())

        # deps should pass
        querier.async_wait_for_result(querier.deps())

        # queries should work after deps
        tok1 = querier.is_async_result(querier.run())
        tok2 = querier.is_async_result(querier.run_sql('select 1 as id'))

        querier.is_result(querier.async_wait(tok2))
        querier.is_result(querier.async_wait(tok1))

        # now break the project
        project.packages['packages'] = bad_packages
        project.write_packages(project_dir, remove=True)

        # queries should still work because we haven't reloaded
        tok1 = querier.is_async_result(querier.run())
        tok2 = querier.is_async_result(querier.run_sql('select 1 as id'))

        querier.is_result(querier.async_wait(tok2))
        querier.is_result(querier.async_wait(tok1))

        # now run deps again, it should be sad
        querier.async_wait_for_error(querier.deps())
        # it should also not be running.
        result = querier.is_result(querier.ps(active=True, completed=False))
        assert result['rows'] == []

        # fix packages again
        project.packages['packages'] = packages
        project.write_packages(project_dir, remove=True)
        # keep queries broken, we haven't run deps yet
        querier.is_error(querier.run())

        # deps should pass now
        querier.async_wait_for_result(querier.deps())
        querier.is_result(querier.status())

        tok1 = querier.is_async_result(querier.run())
        tok2 = querier.is_async_result(querier.run_sql('select 1 as id'))

        querier.is_result(querier.async_wait(tok2))
        querier.is_result(querier.async_wait(tok1))


@pytest.mark.supported('postgres')
def test_rpc_deps_packages(project_root, profiles_root, dbt_profile, unique_schema):
    packages = [{
        'package': 'fishtown-analytics/dbt_utils',
        'version': '0.5.0',
    }]
    bad_packages = [{
        'package': 'fishtown-analytics/dbt_util',
        'version': '0.5.0',
    }]
    deps_with_packages(packages, bad_packages, project_root, profiles_root, unique_schema)


@pytest.mark.supported('postgres')
def test_rpc_deps_git(project_root, profiles_root, dbt_profile, unique_schema):
    packages = [
        {
            'git': 'https://github.com/fishtown-analytics/dbt-utils.git',
            'revision': '0.5.0'
        },
        # TODO: Change me to something that fishtown-analytics manages!
        # here I just moved the dbt_utils code into a subdirectory
        {
            'git': 'https://github.com/dmateusp/dbt-utils.git',
            'revision': 'dmateusp/move_dbt_utils_to_subdir',
            'subdirectory': 'dbt_projects/dbt_utils'
        },
    ]
    # if you use a bad URL, git thinks it's a private repo and prompts for auth
    bad_packages = [{
        'git': 'https://github.com/fishtown-analytics/dbt-utils.git',
        'revision': 'not-a-real-revision'
    }]
    deps_with_packages(packages, bad_packages, project_root, profiles_root, unique_schema)


@pytest.mark.supported('postgres')
def test_rpc_deps_git_commit(project_root, profiles_root, dbt_profile, unique_schema):
    packages = [{
        'git': 'https://github.com/fishtown-analytics/dbt-utils.git',
        'revision': 'b736cf6acdbf80d2de69b511a51c8d7fe214ee79'
    }]
    # don't use short commits
    bad_packages = [{
        'git': 'https://github.com/fishtown-analytics/dbt-utils.git',
        'revision': 'b736cf6'
    }]
    deps_with_packages(packages, bad_packages, project_root, profiles_root, unique_schema)
