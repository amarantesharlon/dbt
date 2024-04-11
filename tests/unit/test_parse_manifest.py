import unittest
from unittest import mock
from unittest.mock import patch, MagicMock
from argparse import Namespace

from .utils import config_from_parts_or_dicts, normalize

from dbt.contracts.files import SourceFile, FileHash, FilePath
from dbt.contracts.graph.manifest import Manifest, ManifestStateCheck
from dbt.parser import manifest
from dbt.parser.manifest import ManifestLoader
from dbt.config import RuntimeConfig
from dbt.flags import set_from_args


class MatchingHash(FileHash):
    def __init__(self):
        return super().__init__("", "")

    def __eq__(self, other):
        return True


class MismatchedHash(FileHash):
    def __init__(self):
        return super().__init__("", "")

    def __eq__(self, other):
        return False


class TestLoader(unittest.TestCase):
    def setUp(self):
        profile_data = {
            "target": "test",
            "quoting": {},
            "outputs": {
                "test": {
                    "type": "postgres",
                    "host": "localhost",
                    "schema": "analytics",
                    "user": "test",
                    "pass": "test",
                    "dbname": "test",
                    "port": 1,
                }
            },
        }

        root_project = {
            "name": "root",
            "version": "0.1",
            "profile": "test",
            "project-root": normalize("/usr/src/app"),
            "config-version": 2,
        }

        self.root_project_config = config_from_parts_or_dicts(
            project=root_project, profile=profile_data, cli_vars='{"test_schema_name": "foo"}'
        )
        self.parser = mock.MagicMock()

        # Create the Manifest.state_check patcher
        @patch("dbt.parser.manifest.ManifestLoader.build_manifest_state_check")
        def _mock_state_check(self):
            all_projects = self.all_projects
            return ManifestStateCheck(
                vars_hash=FileHash.from_contents("vars"),
                project_hashes={name: FileHash.from_contents(name) for name in all_projects},
                profile_hash=FileHash.from_contents("profile"),
            )

        self.load_state_check = patch(
            "dbt.parser.manifest.ManifestLoader.build_manifest_state_check"
        )
        self.mock_state_check = self.load_state_check.start()
        self.mock_state_check.side_effect = _mock_state_check

        self.loader = manifest.ManifestLoader(
            self.root_project_config, {"root": self.root_project_config}
        )

    def _new_manifest(self):
        state_check = ManifestStateCheck(MatchingHash(), MatchingHash, [])
        manifest = Manifest({}, {}, {}, {}, {}, {}, [], {})
        manifest.state_check = state_check
        return manifest

    def _mismatched_file(self, searched, name):
        return self._new_file(searched, name, False)

    def _matching_file(self, searched, name):
        return self._new_file(searched, name, True)

    def _new_file(self, searched, name, match):
        if match:
            checksum = MatchingHash()
        else:
            checksum = MismatchedHash()
        path = FilePath(
            searched_path=normalize(searched),
            relative_path=normalize(name),
            project_root=normalize(self.root_project_config.project_root),
        )
        return SourceFile(path=path, checksum=checksum)


class TestPartialParse(unittest.TestCase):
    def setUp(self) -> None:
        mock_project = MagicMock(RuntimeConfig)
        mock_project.cli_vars = ""
        mock_project.args = MagicMock()
        mock_project.args.profile = "test"
        mock_project.args.target = "test"
        mock_project.project_env_vars = {}
        mock_project.profile_env_vars = {}
        mock_project.project_target_path = "mock_target_path"
        mock_project.credentials = MagicMock()
        self.mock_project = mock_project

    @patch("dbt.parser.manifest.ManifestLoader.build_manifest_state_check")
    @patch("dbt.parser.manifest.os.path.exists")
    @patch("dbt.parser.manifest.open")
    def test_partial_parse_file_path(self, patched_open, patched_os_exist, patched_state_check):
        mock_project = MagicMock(RuntimeConfig)
        mock_project.project_target_path = "mock_target_path"
        patched_os_exist.return_value = True
        set_from_args(Namespace(), {})
        ManifestLoader(mock_project, {})
        # by default we use the project_target_path
        patched_open.assert_called_with("mock_target_path/partial_parse.msgpack", "rb")
        set_from_args(Namespace(partial_parse_file_path="specified_partial_parse_path"), {})
        ManifestLoader(mock_project, {})
        # if specified in flags, we use the specified path
        patched_open.assert_called_with("specified_partial_parse_path", "rb")

    def test_profile_hash_change(self):
        # This test validate that the profile_hash is updated when the connection keys change
        profile_hash = "750bc99c1d64ca518536ead26b28465a224be5ffc918bf2a490102faa5a1bcf5"
        self.mock_project.credentials.connection_info.return_value = "test"
        set_from_args(Namespace(), {})
        manifest = ManifestLoader(self.mock_project, {})
        assert manifest.manifest.state_check.profile_hash.checksum == profile_hash
        self.mock_project.credentials.connection_info.return_value = "test1"
        manifest = ManifestLoader(self.mock_project, {})
        assert manifest.manifest.state_check.profile_hash.checksum != profile_hash


class TestFailedPartialParse(unittest.TestCase):
    @patch("dbt.tracking.track_partial_parser")
    @patch("dbt.tracking.active_user")
    @patch("dbt.parser.manifest.PartialParsing")
    @patch("dbt.parser.manifest.ManifestLoader.read_manifest_for_partial_parse")
    @patch("dbt.parser.manifest.ManifestLoader.build_manifest_state_check")
    def test_partial_parse_safe_update_project_parser_files_partially(
        self,
        patched_state_check,
        patched_read_manifest_for_partial_parse,
        patched_partial_parsing,
        patched_active_user,
        patched_track_partial_parser,
    ):
        mock_instance = MagicMock()
        mock_instance.skip_parsing.return_value = False
        mock_instance.get_parsing_files.side_effect = KeyError("Whoopsie!")
        patched_partial_parsing.return_value = mock_instance

        mock_project = MagicMock(RuntimeConfig)
        mock_project.project_target_path = "mock_target_path"

        mock_saved_manifest = MagicMock(Manifest)
        mock_saved_manifest.files = {}
        patched_read_manifest_for_partial_parse.return_value = mock_saved_manifest

        set_from_args(Namespace(), {})
        loader = ManifestLoader(mock_project, {})
        loader.safe_update_project_parser_files_partially({})

        patched_track_partial_parser.assert_called_once()
        exc_info = patched_track_partial_parser.call_args[0][0]
        self.assertIn("traceback", exc_info)
        self.assertIn("exception", exc_info)
        self.assertIn("code", exc_info)
        self.assertIn("location", exc_info)
        self.assertIn("full_reparse_reason", exc_info)
        self.assertEqual("KeyError: 'Whoopsie!'", exc_info["exception"])
        self.assertTrue(
            isinstance(exc_info["code"], str) or isinstance(exc_info["code"], type(None))
        )
