import os
import shutil
from unittest import mock
from unittest.mock import Mock, call
from pathlib import Path

import click

from test.integration.base import DBTIntegrationTest, use_profile


class TestInit(DBTIntegrationTest):
    def tearDown(self):
        project_name = self.get_project_name()

        if os.path.exists(project_name):
            shutil.rmtree(project_name)

        super().tearDown()

    def get_project_name(self):
        return 'my_project_{}'.format(self.unique_schema())

    @property
    def schema(self):
        return 'init_040'

    @property
    def models(self):
        return 'models'

    @use_profile('postgres')
    @mock.patch('click.confirm')
    @mock.patch('click.prompt')
    def test_postgres_init_task_in_project_with_existing_profiles_yml(self, mock_prompt, mock_confirm):
        manager = Mock()
        manager.attach_mock(mock_prompt, 'prompt')
        manager.attach_mock(mock_confirm, 'confirm')
        manager.confirm.side_effect = ["y"]
        manager.prompt.side_effect = [
            1,
            4,
            'localhost',
            5432,
            'test_user',
            'test_password',
            'test_db',
            'test_schema',
        ]

        self.run_dbt(['init'])

        manager.assert_has_calls([
            call.confirm(f'The profile test already exists in {self.test_root_dir}/profiles.yml. Continue and overwrite it?'),
            call.prompt("Which database would you like to use?\n[1] postgres\n\n(Don't see the one you want? https://docs.getdbt.com/docs/available-adapters)\n\nEnter a number", type=click.INT),
            call.prompt('threads (1 or more)', default=1, hide_input=False, type=click.INT),
            call.prompt('host (hostname for the instance)', default=None, hide_input=False, type=None),
            call.prompt('port', default=5432, hide_input=False, type=click.INT),
            call.prompt('user (dev username)', default=None, hide_input=False, type=None),
            call.prompt('pass (dev password)', default=None, hide_input=True, type=None),
            call.prompt('dbname (default database that dbt will build objects in)', default=None, hide_input=False, type=None),
            call.prompt('schema (default schema that dbt will build objects in)', default=None, hide_input=False, type=None)
        ])

        with open(os.path.join(self.test_root_dir, 'profiles.yml'), 'r') as f:
            assert f.read() == """config:
  send_anonymous_usage_stats: false
test:
  outputs:
    dev:
      dbname: test_db
      host: localhost
      pass: test_password
      port: 5432
      schema: test_schema
      threads: 4
      type: postgres
      user: test_user
  target: dev
"""

    @use_profile('postgres')
    @mock.patch('click.confirm')
    @mock.patch('click.prompt')
    @mock.patch.object(Path, 'exists', autospec=True)
    def test_postgres_init_task_in_project_without_existing_profiles_yml(self, exists, mock_prompt, mock_confirm):

        def exists_side_effect(path):
            # Override responses on specific files, default to 'real world' if not overriden
            return {
                'profiles.yml': False
            }.get(path.name, os.path.exists(path))

        exists.side_effect = exists_side_effect
        manager = Mock()
        manager.attach_mock(mock_prompt, 'prompt')
        manager.prompt.side_effect = [
            1,
            4,
            'localhost',
            5432,
            'test_user',
            'test_password',
            'test_db',
            'test_schema',
        ]

        self.run_dbt(['init'])

        manager.assert_has_calls([
            call.prompt("Which database would you like to use?\n[1] postgres\n\n(Don't see the one you want? https://docs.getdbt.com/docs/available-adapters)\n\nEnter a number", type=click.INT),
            call.prompt('threads (1 or more)', default=1, hide_input=False, type=click.INT),
            call.prompt('host (hostname for the instance)', default=None, hide_input=False, type=None),
            call.prompt('port', default=5432, hide_input=False, type=click.INT),
            call.prompt('user (dev username)', default=None, hide_input=False, type=None),
            call.prompt('pass (dev password)', default=None, hide_input=True, type=None),
            call.prompt('dbname (default database that dbt will build objects in)', default=None, hide_input=False, type=None),
            call.prompt('schema (default schema that dbt will build objects in)', default=None, hide_input=False, type=None)
        ])

        with open(os.path.join(self.test_root_dir, 'profiles.yml'), 'r') as f:
            assert f.read() == """test:
  outputs:
    dev:
      dbname: test_db
      host: localhost
      pass: test_password
      port: 5432
      schema: test_schema
      threads: 4
      type: postgres
      user: test_user
  target: dev
"""

    @use_profile('postgres')
    @mock.patch('click.confirm')
    @mock.patch('click.prompt')
    @mock.patch.object(Path, 'exists', autospec=True)
    def test_postgres_init_task_in_project_without_existing_profiles_yml_or_target_options(self, exists, mock_prompt, mock_confirm):

        def exists_side_effect(path):
            # Override responses on specific files, default to 'real world' if not overriden
            return {
                'profiles.yml': False,
                'target_options.yml': False,
            }.get(path.name, os.path.exists(path))

        exists.side_effect = exists_side_effect
        manager = Mock()
        manager.attach_mock(mock_prompt, 'prompt')
        manager.attach_mock(mock_confirm, 'confirm')
        manager.prompt.side_effect = [
            1,
        ]
        self.run_dbt(['init'])
        manager.assert_has_calls([
            call.prompt("Which database would you like to use?\n[1] postgres\n\n(Don't see the one you want? https://docs.getdbt.com/docs/available-adapters)\n\nEnter a number", type=click.INT),
        ])

        with open(os.path.join(self.test_root_dir, 'profiles.yml'), 'r') as f:
            assert f.read() == """test:
  outputs:

    dev:
      type: postgres
      threads: [1 or more]
      host: [host]
      port: [port]
      user: [dev_username]
      pass: [dev_password]
      dbname: [dbname]
      schema: [dev_schema]

    prod:
      type: postgres
      threads: [1 or more]
      host: [host]
      port: [port]
      user: [prod_username]
      pass: [prod_password]
      dbname: [dbname]
      schema: [prod_schema]

  target: dev
"""

    @use_profile('postgres')
    @mock.patch('click.confirm')
    @mock.patch('click.prompt')
    @mock.patch.object(Path, 'exists', autospec=True)
    def test_postgres_init_task_in_project_with_profile_template_without_existing_profiles_yml(self, exists, mock_prompt, mock_confirm):

        def exists_side_effect(path):
            # Override responses on specific files, default to 'real world' if not overriden
            return {
                'profiles.yml': False,
            }.get(path.name, os.path.exists(path))
        exists.side_effect = exists_side_effect

        with open("profile_template.yml", 'w') as f:
            f.write("""prompts:
  - pg_username
  - pg_password
profile:
  my_profile:
    outputs:
      dev:
        type: postgres
        threads: 4
        host: localhost
        port: 5432
        user: "{{ pg_username }}"
        pass: "{{ pg_password }}"
        dbname: my_db
        schema: my_schema
    target: dev""")

        manager = Mock()
        manager.attach_mock(mock_prompt, 'prompt')
        manager.attach_mock(mock_confirm, 'confirm')
        manager.prompt.side_effect = [
            'test_username',
            'test_password'
        ]
        self.run_dbt(['init'])
        manager.assert_has_calls([
            call.prompt('pg_username'),
            call.prompt('pg_password')
        ])

        with open(os.path.join(self.test_root_dir, 'profiles.yml'), 'r') as f:
            assert f.read() == """my_profile:
  outputs:
    dev:
      dbname: my_db
      host: localhost
      pass: test_password
      port: 5432
      schema: my_schema
      threads: 4
      type: postgres
      user: test_username
  target: dev
"""

    @use_profile('postgres')
    @mock.patch('click.confirm')
    @mock.patch('click.prompt')
    def test_postgres_init_task_in_project_with_invalid_profile_template(self, mock_prompt, mock_confirm):
        """Test that when an invalid profile_template.yml is provided,
        init command falls back to the target_options.yml"""

        with open("profile_template.yml", 'w') as f:
            f.write("""invalid template""")

        manager = Mock()
        manager.attach_mock(mock_prompt, 'prompt')
        manager.attach_mock(mock_confirm, 'confirm')
        manager.confirm.side_effect = ["y"]
        manager.prompt.side_effect = [
            1,
            4,
            'localhost',
            5432,
            'test_username',
            'test_password',
            'test_db',
            'test_schema',
        ]

        self.run_dbt(['init'])

        manager.assert_has_calls([
            call.confirm(f'The profile test already exists in {self.test_root_dir}/profiles.yml. Continue and overwrite it?'),
            call.prompt("Which database would you like to use?\n[1] postgres\n\n(Don't see the one you want? https://docs.getdbt.com/docs/available-adapters)\n\nEnter a number", type=click.INT),
            call.prompt('threads (1 or more)', default=1, hide_input=False, type=click.INT),
            call.prompt('host (hostname for the instance)', default=None, hide_input=False, type=None),
            call.prompt('port', default=5432, hide_input=False, type=click.INT),
            call.prompt('user (dev username)', default=None, hide_input=False, type=None),
            call.prompt('pass (dev password)', default=None, hide_input=True, type=None),
            call.prompt('dbname (default database that dbt will build objects in)', default=None, hide_input=False, type=None),
            call.prompt('schema (default schema that dbt will build objects in)', default=None, hide_input=False, type=None)
        ])

        with open(os.path.join(self.test_root_dir, 'profiles.yml'), 'r') as f:
            assert f.read() == """config:
  send_anonymous_usage_stats: false
test:
  outputs:
    dev:
      dbname: test_db
      host: localhost
      pass: test_password
      port: 5432
      schema: test_schema
      threads: 4
      type: postgres
      user: test_username
  target: dev
"""

    @use_profile('postgres')
    @mock.patch('click.confirm')
    @mock.patch('click.prompt')
    def test_postgres_init_task_outside_of_project(self, mock_prompt, mock_confirm):
        manager = Mock()
        manager.attach_mock(mock_prompt, 'prompt')
        manager.attach_mock(mock_confirm, 'confirm')

        # Start by removing the dbt_project.yml so that we're not in an existing project
        os.remove('dbt_project.yml')

        project_name = self.get_project_name()
        manager.prompt.side_effect = [
            project_name,
            1,
            4,
            'localhost',
            5432,
            'test_username',
            'test_password',
            'test_db',
            'test_schema',
        ]
        self.run_dbt(['init'])
        manager.assert_has_calls([
            call.prompt('What is the desired project name?'),
            call.prompt("Which database would you like to use?\n[1] postgres\n\n(Don't see the one you want? https://docs.getdbt.com/docs/available-adapters)\n\nEnter a number", type=click.INT),
            call.prompt('threads (1 or more)', default=1, hide_input=False, type=click.INT),
            call.prompt('host (hostname for the instance)', default=None, hide_input=False, type=None),
            call.prompt('port', default=5432, hide_input=False, type=click.INT),
            call.prompt('user (dev username)', default=None, hide_input=False, type=None),
            call.prompt('pass (dev password)', default=None, hide_input=True, type=None),
            call.prompt('dbname (default database that dbt will build objects in)', default=None, hide_input=False, type=None),
            call.prompt('schema (default schema that dbt will build objects in)', default=None, hide_input=False, type=None)
        ])

        with open(os.path.join(self.test_root_dir, 'profiles.yml'), 'r') as f:
            assert f.read() == f"""config:
  send_anonymous_usage_stats: false
{project_name}:
  outputs:
    dev:
      dbname: test_db
      host: localhost
      pass: test_password
      port: 5432
      schema: test_schema
      threads: 4
      type: postgres
      user: test_username
  target: dev
test:
  outputs:
    default2:
      dbname: dbt
      host: localhost
      pass: password
      port: 5432
      schema: {self.unique_schema()}
      threads: 4
      type: postgres
      user: root
    noaccess:
      dbname: dbt
      host: localhost
      pass: password
      port: 5432
      schema: {self.unique_schema()}
      threads: 4
      type: postgres
      user: noaccess
  target: default2
"""

        with open(os.path.join(self.test_root_dir, project_name, 'dbt_project.yml'), 'r') as f:
            assert f.read() == f"""
# Name your project! Project names should contain only lowercase characters
# and underscores. A good package name should reflect your organization's
# name or the intended use of these models
name: '{project_name}'
version: '1.0.0'
config-version: 2

# This setting configures which "profile" dbt uses for this project.
profile: '{project_name}'

# These configurations specify where dbt should look for different types of files.
# The `model-paths` config, for example, states that models in this project can be
# found in the "models/" directory. You probably won't need to change these!
model-paths: ["models"]
analysis-paths: ["analyses"]
test-paths: ["tests"]
seed-paths: ["seeds"]
macro-paths: ["macros"]
snapshot-paths: ["snapshots"]

target-path: "target"  # directory which will store compiled SQL files
clean-targets:         # directories to be removed by `dbt clean`
  - "target"
  - "dbt_packages"


# Configuring models
# Full documentation: https://docs.getdbt.com/docs/configuring-models

# In this example config, we tell dbt to build all models in the example/ directory
# as tables. These settings can be overridden in the individual model files
# using the `{{{{ config(...) }}}}` macro.
models:
  {project_name}:
    # Config indicated by + and applies to all files under models/example/
    example:
      +materialized: view
"""
