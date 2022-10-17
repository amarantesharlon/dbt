from dataclasses import dataclass
from dbt import ui
from dbt.events.base_types import (
    NoFile,
    DebugLevel,
    InfoLevel,
    WarnLevel,
    ErrorLevel,
    Cache,
    AdapterEventStringFunctor,
    EventStringFunctor,
)
from dbt.events.format import format_fancy_output_line, pluralize

# The generated classes quote the included message classes, requiring the following line
from dbt.events.proto_types import EventInfo, RunResultMsg, ListOfStrings  # noqa
from dbt.events.proto_types import NodeInfo, ReferenceKeyMsg
from dbt.events import proto_types as pt

from dbt.node_types import NodeType


# The classes in this file represent the data necessary to describe a
# particular event to both human readable logs, and machine reliable
# event streams. classes extend superclasses that indicate what
# destinations they are intended for, which mypy uses to enforce
# that the necessary methods are defined.


# Event codes have prefixes which follow this table
#
# | Code |     Description     |
# |:----:|:-------------------:|
# | A    | Pre-project loading |
# | E    | DB adapter          |
# | I    | Project parsing     |
# | M    | Deps generation     |
# | Q    | Node execution     |
# | W    | Node testing        |
# | Z    | Misc                |
# | T    | Test only           |
#
# The basic idea is that event codes roughly translate to the natural order of running a dbt task


def format_adapter_message(name, base_msg, args) -> str:
    # only apply formatting if there are arguments to format.
    # avoids issues like "dict: {k: v}".format() which results in `KeyError 'k'`
    msg = base_msg if len(args) == 0 else base_msg.format(*args)
    return f"{name} adapter: {msg}"


# =======================================================
# A - Pre-project loading
# =======================================================


@dataclass
class MainReportVersion(InfoLevel, pt.MainReportVersion):  # noqa
    def code(self):
        return "A001"

    def message(self):
        return f"Running with dbt{self.version}"


@dataclass
class MainReportArgs(DebugLevel, pt.MainReportArgs):  # noqa
    def code(self):
        return "A002"

    def message(self):
        return f"running dbt with arguments {str(self.args)}"


@dataclass
class MainTrackingUserState(DebugLevel, pt.MainTrackingUserState):
    def code(self):
        return "A003"

    def message(self):
        return f"Tracking: {self.user_state}"


@dataclass
class MergedFromState(DebugLevel, pt.MergedFromState):
    def code(self):
        return "A004"

    def message(self) -> str:
        return f"Merged {self.num_merged} items from state (sample: {self.sample})"


@dataclass
class MissingProfileTarget(InfoLevel, pt.MissingProfileTarget):
    def code(self):
        return "A005"

    def message(self) -> str:
        return f"target not specified in profile '{self.profile_name}', using '{self.target_name}'"


# Skipped A006, A007


@dataclass
class InvalidVarsYAML(ErrorLevel, pt.InvalidVarsYAML):
    def code(self):
        return "A008"

    def message(self) -> str:
        return "The YAML provided in the --vars argument is not valid."


@dataclass
class DbtProjectError(ErrorLevel, pt.DbtProjectError):
    def code(self):
        return "A009"

    def message(self) -> str:
        return "Encountered an error while reading the project:"


@dataclass
class DbtProjectErrorException(ErrorLevel, pt.DbtProjectErrorException):
    def code(self):
        return "A010"

    def message(self) -> str:
        return f"  ERROR: {str(self.exc)}"


@dataclass
class DbtProfileError(ErrorLevel, pt.DbtProfileError):
    def code(self):
        return "A011"

    def message(self) -> str:
        return "Encountered an error while reading profiles:"


@dataclass
class DbtProfileErrorException(ErrorLevel, pt.DbtProfileErrorException):
    def code(self):
        return "A012"

    def message(self) -> str:
        return f"  ERROR: {str(self.exc)}"


@dataclass
class ProfileListTitle(InfoLevel, pt.ProfileListTitle):
    def code(self):
        return "A013"

    def message(self) -> str:
        return "Defined profiles:"


@dataclass
class ListSingleProfile(InfoLevel, pt.ListSingleProfile):
    def code(self):
        return "A014"

    def message(self) -> str:
        return f" - {self.profile}"


@dataclass
class NoDefinedProfiles(InfoLevel, pt.NoDefinedProfiles):
    def code(self):
        return "A015"

    def message(self) -> str:
        return "There are no profiles defined in your profiles.yml file"


@dataclass
class ProfileHelpMessage(InfoLevel, pt.ProfileHelpMessage):
    def code(self):
        return "A016"

    def message(self) -> str:
        return """
For more information on configuring profiles, please consult the dbt docs:

https://docs.getdbt.com/docs/configure-your-profile
"""


@dataclass
class StarterProjectPath(DebugLevel, pt.StarterProjectPath):
    def code(self):
        return "A017"

    def message(self) -> str:
        return f"Starter project path: {self.dir}"


@dataclass
class ConfigFolderDirectory(InfoLevel, pt.ConfigFolderDirectory):
    def code(self):
        return "A018"

    def message(self) -> str:
        return f"Creating dbt configuration folder at {self.dir}"


@dataclass
class NoSampleProfileFound(InfoLevel, pt.NoSampleProfileFound):
    def code(self):
        return "A019"

    def message(self) -> str:
        return f"No sample profile found for {self.adapter}."


@dataclass
class ProfileWrittenWithSample(InfoLevel, pt.ProfileWrittenWithSample):
    def code(self):
        return "A020"

    def message(self) -> str:
        return (
            f"Profile {self.name} written to {self.path} "
            "using target's sample configuration. Once updated, you'll be able to "
            "start developing with dbt."
        )


@dataclass
class ProfileWrittenWithTargetTemplateYAML(InfoLevel, pt.ProfileWrittenWithTargetTemplateYAML):
    def code(self):
        return "A021"

    def message(self) -> str:
        return (
            f"Profile {self.name} written to {self.path} using target's "
            "profile_template.yml and your supplied values. Run 'dbt debug' to "
            "validate the connection."
        )


@dataclass
class ProfileWrittenWithProjectTemplateYAML(InfoLevel, pt.ProfileWrittenWithProjectTemplateYAML):
    def code(self):
        return "A022"

    def message(self) -> str:
        return (
            f"Profile {self.name} written to {self.path} using project's "
            "profile_template.yml and your supplied values. Run 'dbt debug' to "
            "validate the connection."
        )


@dataclass
class SettingUpProfile(InfoLevel, pt.SettingUpProfile):
    def code(self):
        return "A023"

    def message(self) -> str:
        return "Setting up your profile."


@dataclass
class InvalidProfileTemplateYAML(InfoLevel, pt.InvalidProfileTemplateYAML):
    def code(self):
        return "A024"

    def message(self) -> str:
        return "Invalid profile_template.yml in project."


@dataclass
class ProjectNameAlreadyExists(InfoLevel, pt.ProjectNameAlreadyExists):
    def code(self):
        return "A025"

    def message(self) -> str:
        return f"A project called {self.name} already exists here."


@dataclass
class ProjectCreated(InfoLevel, pt.ProjectCreated):
    def code(self):
        return "A026"

    def message(self) -> str:
        return """
Your new dbt project "{self.project_name}" was created!

For more information on how to configure the profiles.yml file,
please consult the dbt documentation here:

  {self.docs_url}

One more thing:

Need help? Don't hesitate to reach out to us via GitHub issues or on Slack:

  {self.slack_url}

Happy modeling!
"""


# =======================================================
# E - DB Adapter
# =======================================================


@dataclass
class AdapterEventDebug(DebugLevel, AdapterEventStringFunctor, pt.AdapterEventDebug):  # noqa
    def code(self):
        return "E001"

    def message(self):
        return format_adapter_message(self.name, self.base_msg, self.args)


@dataclass
class AdapterEventInfo(InfoLevel, AdapterEventStringFunctor, pt.AdapterEventInfo):  # noqa
    def code(self):
        return "E002"

    def message(self):
        return format_adapter_message(self.name, self.base_msg, self.args)


@dataclass
class AdapterEventWarning(WarnLevel, AdapterEventStringFunctor, pt.AdapterEventWarning):  # noqa
    def code(self):
        return "E003"

    def message(self):
        return format_adapter_message(self.name, self.base_msg, self.args)


@dataclass
class AdapterEventError(ErrorLevel, AdapterEventStringFunctor, pt.AdapterEventError):  # noqa
    def code(self):
        return "E004"

    def message(self):
        return format_adapter_message(self.name, self.base_msg, self.args)


@dataclass
class NewConnection(DebugLevel, pt.NewConnection):
    def code(self):
        return "E005"

    def message(self) -> str:
        return f'Acquiring new {self.conn_type} connection "{self.conn_name}"'


@dataclass
class ConnectionReused(DebugLevel, pt.ConnectionReused):
    def code(self):
        return "E006"

    def message(self) -> str:
        return f"Re-using an available connection from the pool (formerly {self.conn_name})"


@dataclass
class ConnectionLeftOpen(DebugLevel, pt.ConnectionLeftOpen):
    def code(self):
        return "E007"

    def message(self) -> str:
        return f"Connection '{self.conn_name}' was left open."


@dataclass
class ConnectionClosed(DebugLevel, pt.ConnectionClosed):
    def code(self):
        return "E008"

    def message(self) -> str:
        return f"Connection '{self.conn_name}' was properly closed."


@dataclass
class RollbackFailed(DebugLevel, pt.RollbackFailed):  # noqa
    def code(self):
        return "E009"

    def message(self) -> str:
        return f"Failed to rollback '{self.conn_name}'"


# TODO: can we combine this with ConnectionClosed?
@dataclass
class ConnectionClosed2(DebugLevel, pt.ConnectionClosed2):
    def code(self):
        return "E010"

    def message(self) -> str:
        return f"On {self.conn_name}: Close"


# TODO: can we combine this with ConnectionLeftOpen?
@dataclass
class ConnectionLeftOpen2(DebugLevel, pt.ConnectionLeftOpen2):
    def code(self):
        return "E011"

    def message(self) -> str:
        return f"On {self.conn_name}: No close available on handle"


@dataclass
class Rollback(DebugLevel, pt.Rollback):
    def code(self):
        return "E012"

    def message(self) -> str:
        return f"On {self.conn_name}: ROLLBACK"


@dataclass
class CacheMiss(DebugLevel, pt.CacheMiss):
    def code(self):
        return "E013"

    def message(self) -> str:
        return (
            f'On "{self.conn_name}": cache miss for schema '
            '"{self.database}.{self.schema}", this is inefficient'
        )


@dataclass
class ListRelations(DebugLevel, pt.ListRelations):
    def code(self):
        return "E014"

    def message(self) -> str:
        return f"with database={self.database}, schema={self.schema}, relations={self.relations}"


@dataclass
class ConnectionUsed(DebugLevel, pt.ConnectionUsed):
    def code(self):
        return "E015"

    def message(self) -> str:
        return f'Using {self.conn_type} connection "{self.conn_name}"'


@dataclass
class SQLQuery(DebugLevel, pt.SQLQuery):
    def code(self):
        return "E016"

    def message(self) -> str:
        return f"On {self.conn_name}: {self.sql}"


@dataclass
class SQLQueryStatus(DebugLevel, pt.SQLQueryStatus):
    def code(self):
        return "E017"

    def message(self) -> str:
        return f"SQL status: {self.status} in {self.elapsed} seconds"


@dataclass
class SQLCommit(DebugLevel, pt.SQLCommit):
    def code(self):
        return "E018"

    def message(self) -> str:
        return f"On {self.conn_name}: COMMIT"


@dataclass
class ColTypeChange(DebugLevel, pt.ColTypeChange):
    def code(self):
        return "E019"

    def message(self) -> str:
        return f"Changing col type from {self.orig_type} to {self.new_type} in table {self.table}"


@dataclass
class SchemaCreation(DebugLevel, pt.SchemaCreation):
    def code(self):
        return "E020"

    def message(self) -> str:
        return f'Creating schema "{self.relation}"'


@dataclass
class SchemaDrop(DebugLevel, pt.SchemaDrop):
    def code(self):
        return "E021"

    def message(self) -> str:
        return f'Dropping schema "{self.relation}".'


# TODO pretty sure this is only ever called in dead code
# see: core/dbt/adapters/cache.py _add_link vs add_link
@dataclass
class UncachedRelation(DebugLevel, Cache, pt.UncachedRelation):
    def code(self):
        return "E022"

    def message(self) -> str:
        return (
            f"{self.dep_key} references {str(self.ref_key)} "
            "but {self.ref_key.database}.{self.ref_key.schema}"
            "is not in the cache, skipping assumed external relation"
        )


@dataclass
class AddLink(DebugLevel, Cache, pt.AddLink):
    def code(self):
        return "E023"

    def message(self) -> str:
        return f"adding link, {self.dep_key} references {self.ref_key}"


@dataclass
class AddRelation(DebugLevel, Cache, pt.AddRelation):
    def code(self):
        return "E024"

    def message(self) -> str:
        return f"Adding relation: {str(self.relation)}"


@dataclass
class DropMissingRelation(DebugLevel, Cache, pt.DropMissingRelation):
    def code(self):
        return "E025"

    def message(self) -> str:
        return f"dropped a nonexistent relationship: {str(self.relation)}"


@dataclass
class DropCascade(DebugLevel, Cache, pt.DropCascade):
    def code(self):
        return "E026"

    def message(self) -> str:
        return f"drop {self.dropped} is cascading to {self.consequences}"


@dataclass
class DropRelation(DebugLevel, Cache, pt.DropRelation):
    def code(self):
        return "E027"

    def message(self) -> str:
        return f"Dropping relation: {self.dropped}"


@dataclass
class UpdateReference(DebugLevel, Cache, pt.UpdateReference):
    def code(self):
        return "E028"

    def message(self) -> str:
        return (
            f"updated reference from {self.old_key} -> {self.cached_key} to "
            "{self.new_key} -> {self.cached_key}"
        )


@dataclass
class TemporaryRelation(DebugLevel, Cache, pt.TemporaryRelation):
    def code(self):
        return "E029"

    def message(self) -> str:
        return f"old key {self.key} not found in self.relations, assuming temporary"


@dataclass
class RenameSchema(DebugLevel, Cache, pt.RenameSchema):
    def code(self):
        return "E030"

    def message(self) -> str:
        return f"Renaming relation {self.old_key} to {self.new_key}"


@dataclass
class DumpBeforeAddGraph(DebugLevel, Cache, pt.DumpBeforeAddGraph):
    def code(self):
        return "E031"

    def message(self) -> str:
        return f"before adding : {self.dump}"


@dataclass
class DumpAfterAddGraph(DebugLevel, Cache, pt.DumpAfterAddGraph):
    def code(self):
        return "E032"

    def message(self) -> str:
        return f"after adding: {self.dump}"


@dataclass
class DumpBeforeRenameSchema(DebugLevel, Cache, pt.DumpBeforeRenameSchema):
    def code(self):
        return "E033"

    def message(self) -> str:
        return f"before rename: {self.dump}"


@dataclass
class DumpAfterRenameSchema(DebugLevel, Cache, pt.DumpAfterRenameSchema):
    def code(self):
        return "E034"

    def message(self) -> str:
        return f"after rename: {self.dump}"


@dataclass
class AdapterImportError(InfoLevel, pt.AdapterImportError):
    def code(self):
        return "E035"

    def message(self) -> str:
        return f"Error importing adapter: {self.exc}"


@dataclass
class PluginLoadError(DebugLevel, pt.PluginLoadError):  # noqa
    def code(self):
        return "E036"

    def message(self):
        pass


@dataclass
class NewConnectionOpening(DebugLevel, pt.NewConnectionOpening):
    def code(self):
        return "E037"

    def message(self) -> str:
        return f"Opening a new connection, currently in state {self.connection_state}"


@dataclass
class CodeExecution(DebugLevel, pt.CodeExecution):
    def code(self):
        return "E038"

    def message(self) -> str:
        return f"On {self.conn_name}: {self.code_content}"


@dataclass
class CodeExecutionStatus(DebugLevel, pt.CodeExecutionStatus):
    def code(self):
        return "E039"

    def message(self) -> str:
        return f"Execution status: {self.status} in {self.elapsed} seconds"


# Skipped E040


@dataclass
class WriteCatalogFailure(ErrorLevel, pt.WriteCatalogFailure):
    def code(self):
        return "E041"

    def message(self) -> str:
        return (
            f"dbt encountered {self.num_exceptions} failure{(self.num_exceptions != 1) * 's'} "
            "while writing the catalog"
        )


@dataclass
class CatalogWritten(InfoLevel, pt.CatalogWritten):
    def code(self):
        return "E042"

    def message(self) -> str:
        return f"Catalog written to {self.path}"


@dataclass
class CannotGenerateDocs(InfoLevel, pt.CannotGenerateDocs):
    def code(self):
        return "E043"

    def message(self) -> str:
        return "compile failed, cannot generate docs"


@dataclass
class BuildingCatalog(InfoLevel, pt.BuildingCatalog):
    def code(self):
        return "E044"

    def message(self) -> str:
        return "Building catalog"


@dataclass
class DatabaseErrorRunningHook(InfoLevel, pt.DatabaseErrorRunningHook):
    def code(self):
        return "E045"

    def message(self) -> str:
        return f"Database error while running {self.hook_type}"


@dataclass
class HooksRunning(InfoLevel, pt.HooksRunning):
    def code(self):
        return "E046"

    def message(self) -> str:
        plural = "hook" if self.num_hooks == 1 else "hooks"
        return f"Running {self.num_hooks} {self.hook_type} {plural}"


@dataclass
class HookFinished(InfoLevel, pt.HookFinished):
    def code(self):
        return "E047"

    def message(self) -> str:
        return f"Finished running {self.stat_line}{self.execution} ({self.execution_time:0.2f}s)."


# =======================================================
# I - Project parsing
# =======================================================


@dataclass
class ParseCmdStart(InfoLevel, pt.ParseCmdStart):
    def code(self):
        return "I001"

    def message(self) -> str:
        return "Start parsing."


@dataclass
class ParseCmdCompiling(InfoLevel, pt.ParseCmdCompiling):
    def code(self):
        return "I002"

    def message(self) -> str:
        return "Compiling."


@dataclass
class ParseCmdWritingManifest(InfoLevel, pt.ParseCmdWritingManifest):
    def code(self):
        return "I003"

    def message(self) -> str:
        return "Writing manifest."


@dataclass
class ParseCmdDone(InfoLevel, pt.ParseCmdDone):
    def code(self):
        return "I004"

    def message(self) -> str:
        return "Done."


@dataclass
class ManifestDependenciesLoaded(InfoLevel, pt.ManifestDependenciesLoaded):
    def code(self):
        return "I005"

    def message(self) -> str:
        return "Dependencies loaded"


@dataclass
class ManifestLoaderCreated(InfoLevel, pt.ManifestLoaderCreated):
    def code(self):
        return "I006"

    def message(self) -> str:
        return "ManifestLoader created"


@dataclass
class ManifestLoaded(InfoLevel, pt.ManifestLoaded):
    def code(self):
        return "I007"

    def message(self) -> str:
        return "Manifest loaded"


@dataclass
class ManifestChecked(InfoLevel, pt.ManifestChecked):
    def code(self):
        return "I008"

    def message(self) -> str:
        return "Manifest checked"


@dataclass
class ManifestFlatGraphBuilt(InfoLevel, pt.ManifestFlatGraphBuilt):
    def code(self):
        return "I009"

    def message(self) -> str:
        return "Flat graph built"


@dataclass
class ParseCmdPerfInfoPath(InfoLevel, pt.ParseCmdPerfInfoPath):
    def code(self):
        return "I010"

    def message(self) -> str:
        return f"Performance info: {self.path}"


@dataclass
class GenericTestFileParse(DebugLevel, pt.GenericTestFileParse):
    def code(self):
        return "I011"

    def message(self) -> str:
        return f"Parsing {self.path}"


@dataclass
class MacroFileParse(DebugLevel, pt.MacroFileParse):
    def code(self):
        return "I012"

    def message(self) -> str:
        return f"Parsing {self.path}"


@dataclass
class PartialParsingFullReparseBecauseOfError(
    InfoLevel, pt.PartialParsingFullReparseBecauseOfError
):
    def code(self):
        return "I013"

    def message(self) -> str:
        return "Partial parsing enabled but an error occurred. Switching to a full re-parse."


@dataclass
class PartialParsingExceptionFile(DebugLevel, pt.PartialParsingExceptionFile):
    def code(self):
        return "I014"

    def message(self) -> str:
        return f"Partial parsing exception processing file {self.file}"


@dataclass
class PartialParsingFile(DebugLevel, pt.PartialParsingFile):
    def code(self):
        return "I015"

    def message(self) -> str:
        return f"PP file: {self.file_id}"


@dataclass
class PartialParsingException(DebugLevel, pt.PartialParsingException):
    def code(self):
        return "I016"

    def message(self) -> str:
        return f"PP exception info: {self.exc_info}"


@dataclass
class PartialParsingSkipParsing(DebugLevel, pt.PartialParsingSkipParsing):
    def code(self):
        return "I017"

    def message(self) -> str:
        return "Partial parsing enabled, no changes found, skipping parsing"


@dataclass
class PartialParsingMacroChangeStartFullParse(
    InfoLevel, pt.PartialParsingMacroChangeStartFullParse
):
    def code(self):
        return "I018"

    def message(self) -> str:
        return "Change detected to override macro used during parsing. Starting full parse."


@dataclass
class PartialParsingProjectEnvVarsChanged(InfoLevel, pt.PartialParsingProjectEnvVarsChanged):
    def code(self):
        return "I019"

    def message(self) -> str:
        return "Unable to do partial parsing because env vars used in dbt_project.yml have changed"


@dataclass
class PartialParsingProfileEnvVarsChanged(InfoLevel, pt.PartialParsingProfileEnvVarsChanged):
    def code(self):
        return "I020"

    def message(self) -> str:
        return "Unable to do partial parsing because env vars used in profiles.yml have changed"


@dataclass
class PartialParsingDeletedMetric(DebugLevel, pt.PartialParsingDeletedMetric):
    def code(self):
        return "I021"

    def message(self) -> str:
        return f"Partial parsing: deleted metric {self.unique_id}"


@dataclass
class ManifestWrongMetadataVersion(DebugLevel, pt.ManifestWrongMetadataVersion):
    def code(self):
        return "I022"

    def message(self) -> str:
        return (
            "Manifest metadata did not contain correct version. "
            f"Contained '{self.version}' instead."
        )


@dataclass
class PartialParsingVersionMismatch(InfoLevel, pt.PartialParsingVersionMismatch):
    def code(self):
        return "I023"

    def message(self) -> str:
        return (
            "Unable to do partial parsing because of a dbt version mismatch. "
            f"Saved manifest version: {self.saved_version}. "
            f"Current version: {self.current_version}."
        )


@dataclass
class PartialParsingFailedBecauseConfigChange(
    InfoLevel, pt.PartialParsingFailedBecauseConfigChange
):
    def code(self):
        return "I024"

    def message(self) -> str:
        return (
            "Unable to do partial parsing because config vars, "
            "config profile, or config target have changed"
        )


@dataclass
class PartialParsingFailedBecauseProfileChange(
    InfoLevel, pt.PartialParsingFailedBecauseProfileChange
):
    def code(self):
        return "I025"

    def message(self) -> str:
        return "Unable to do partial parsing because profile has changed"


@dataclass
class PartialParsingFailedBecauseNewProjectDependency(
    InfoLevel, pt.PartialParsingFailedBecauseNewProjectDependency
):
    def code(self):
        return "I026"

    def message(self) -> str:
        return "Unable to do partial parsing because a project dependency has been added"


@dataclass
class PartialParsingFailedBecauseHashChanged(InfoLevel, pt.PartialParsingFailedBecauseHashChanged):
    def code(self):
        return "I027"

    def message(self) -> str:
        return "Unable to do partial parsing because a project config has changed"


@dataclass
class PartialParsingNotEnabled(DebugLevel, pt.PartialParsingNotEnabled):
    def code(self):
        return "I028"

    def message(self) -> str:
        return "Partial parsing not enabled"


@dataclass
class ParsedFileLoadFailed(DebugLevel, pt.ParsedFileLoadFailed):  # noqa
    def code(self):
        return "I029"

    def message(self) -> str:
        return f"Failed to load parsed file from disk at {self.path}: {self.exc}"


@dataclass
class PartialParseSaveFileNotFound(InfoLevel, pt.PartialParseSaveFileNotFound):
    def code(self):
        return "I030"

    def message(self) -> str:
        return "Partial parse save file not found. Starting full parse."


@dataclass
class StaticParserCausedJinjaRendering(DebugLevel, pt.StaticParserCausedJinjaRendering):
    def code(self):
        return "I031"

    def message(self) -> str:
        return f"1605: jinja rendering because of STATIC_PARSER flag. file: {self.path}"


# TODO: Experimental/static parser uses these for testing and some may be a good use case for
#       the `TestLevel` logger once we implement it.  Some will probably stay `DebugLevel`.
@dataclass
class UsingExperimentalParser(DebugLevel, pt.UsingExperimentalParser):
    def code(self):
        return "I032"

    def message(self) -> str:
        return f"1610: conducting experimental parser sample on {self.path}"


@dataclass
class SampleFullJinjaRendering(DebugLevel, pt.SampleFullJinjaRendering):
    def code(self):
        return "I033"

    def message(self) -> str:
        return f"1611: conducting full jinja rendering sample on {self.path}"


@dataclass
class StaticParserFallbackJinjaRendering(DebugLevel, pt.StaticParserFallbackJinjaRendering):
    def code(self):
        return "I034"

    def message(self) -> str:
        return f"1602: parser fallback to jinja rendering on {self.path}"


@dataclass
class StaticParsingMacroOverrideDetected(DebugLevel, pt.StaticParsingMacroOverrideDetected):
    def code(self):
        return "I035"

    def message(self) -> str:
        return f"1601: detected macro override of ref/source/config in the scope of {self.path}"


@dataclass
class StaticParserSuccess(DebugLevel, pt.StaticParserSuccess):
    def code(self):
        return "I036"

    def message(self) -> str:
        return f"1699: static parser successfully parsed {self.path}"


@dataclass
class StaticParserFailure(DebugLevel, pt.StaticParserFailure):
    def code(self):
        return "I037"

    def message(self) -> str:
        return f"1603: static parser failed on {self.path}"


@dataclass
class ExperimentalParserSuccess(DebugLevel, pt.ExperimentalParserSuccess):
    def code(self):
        return "I038"

    def message(self) -> str:
        return f"1698: experimental parser successfully parsed {self.path}"


@dataclass
class ExperimentalParserFailure(DebugLevel, pt.ExperimentalParserFailure):
    def code(self):
        return "I039"

    def message(self) -> str:
        return f"1604: experimental parser failed on {self.path}"


@dataclass
class PartialParsingEnabled(DebugLevel, pt.PartialParsingEnabled):
    def code(self):
        return "I040"

    def message(self) -> str:
        return (
            f"Partial parsing enabled: "
            f"{self.deleted} files deleted, "
            f"{self.added} files added, "
            f"{self.changed} files changed."
        )


@dataclass
class PartialParsingAddedFile(DebugLevel, pt.PartialParsingAddedFile):
    def code(self):
        return "I041"

    def message(self) -> str:
        return f"Partial parsing: added file: {self.file_id}"


@dataclass
class PartialParsingDeletedFile(DebugLevel, pt.PartialParsingDeletedFile):
    def code(self):
        return "I042"

    def message(self) -> str:
        return f"Partial parsing: deleted file: {self.file_id}"


@dataclass
class PartialParsingUpdatedFile(DebugLevel, pt.PartialParsingUpdatedFile):
    def code(self):
        return "I043"

    def message(self) -> str:
        return f"Partial parsing: updated file: {self.file_id}"


@dataclass
class PartialParsingNodeMissingInSourceFile(DebugLevel, pt.PartialParsingNodeMissingInSourceFile):
    def code(self):
        return "I044"

    def message(self) -> str:
        return f"Partial parsing: nodes list not found in source_file {self.file_id}"


@dataclass
class PartialParsingMissingNodes(DebugLevel, pt.PartialParsingMissingNodes):
    def code(self):
        return "I045"

    def message(self) -> str:
        return f"No nodes found for source file {self.file_id}"


@dataclass
class PartialParsingChildMapMissingUniqueID(DebugLevel, pt.PartialParsingChildMapMissingUniqueID):
    def code(self):
        return "I046"

    def message(self) -> str:
        return f"Partial parsing: {self.unique_id} not found in child_map"


@dataclass
class PartialParsingUpdateSchemaFile(DebugLevel, pt.PartialParsingUpdateSchemaFile):
    def code(self):
        return "I047"

    def message(self) -> str:
        return f"Partial parsing: update schema file: {self.file_id}"


@dataclass
class PartialParsingDeletedSource(DebugLevel, pt.PartialParsingDeletedSource):
    def code(self):
        return "I048"

    def message(self) -> str:
        return f"Partial parsing: deleted source {self.unique_id}"


@dataclass
class PartialParsingDeletedExposure(DebugLevel, pt.PartialParsingDeletedExposure):
    def code(self):
        return "I049"

    def message(self) -> str:
        return f"Partial parsing: deleted exposure {self.unique_id}"


# TODO: switch to storing structured info and calling get_target_failure_msg
@dataclass
class InvalidDisabledSourceInTestNode(
    WarnLevel, EventStringFunctor, pt.InvalidDisabledSourceInTestNode
):
    def code(self):
        return "I050"

    def message(self) -> str:
        return ui.warning_tag(self.msg)


@dataclass
class InvalidRefInTestNode(DebugLevel, EventStringFunctor, pt.InvalidRefInTestNode):
    def code(self):
        return "I051"

    def message(self) -> str:
        return self.msg


# =======================================================
# M - Deps generation
# =======================================================


@dataclass
class GitSparseCheckoutSubdirectory(DebugLevel, pt.GitSparseCheckoutSubdirectory):
    def code(self):
        return "M001"

    def message(self) -> str:
        return f"  Subdirectory specified: {self.subdir}, using sparse checkout."


@dataclass
class GitProgressCheckoutRevision(DebugLevel, pt.GitProgressCheckoutRevision):
    def code(self):
        return "M002"

    def message(self) -> str:
        return f"  Checking out revision {self.revision}."


@dataclass
class GitProgressUpdatingExistingDependency(DebugLevel, pt.GitProgressUpdatingExistingDependency):
    def code(self):
        return "M003"

    def message(self) -> str:
        return f"Updating existing dependency {self.dir}."


@dataclass
class GitProgressPullingNewDependency(DebugLevel, pt.GitProgressPullingNewDependency):
    def code(self):
        return "M004"

    def message(self) -> str:
        return f"Pulling new dependency {self.dir}."


@dataclass
class GitNothingToDo(DebugLevel, pt.GitNothingToDo):
    def code(self):
        return "M005"

    def message(self) -> str:
        return f"Already at {self.sha}, nothing to do."


@dataclass
class GitProgressUpdatedCheckoutRange(DebugLevel, pt.GitProgressUpdatedCheckoutRange):
    def code(self):
        return "M006"

    def message(self) -> str:
        return f"  Updated checkout from {self.start_sha} to {self.end_sha}."


@dataclass
class GitProgressCheckedOutAt(DebugLevel, pt.GitProgressCheckedOutAt):
    def code(self):
        return "M007"

    def message(self) -> str:
        return f"  Checked out at {self.end_sha}."


@dataclass
class RegistryProgressGETRequest(DebugLevel, pt.RegistryProgressGETRequest):
    def code(self):
        return "M008"

    def message(self) -> str:
        return f"Making package registry request: GET {self.url}"


@dataclass
class RegistryProgressGETResponse(DebugLevel, pt.RegistryProgressGETResponse):
    def code(self):
        return "M009"

    def message(self) -> str:
        return f"Response from registry: GET {self.url} {self.resp_code}"


@dataclass
class SelectorReportInvalidSelector(InfoLevel, pt.SelectorReportInvalidSelector):
    def code(self):
        return "M010"

    def message(self) -> str:
        return (
            f"The '{self.spec_method}' selector specified in {self.raw_spec} is "
            f"invalid. Must be one of [{self.valid_selectors}]"
        )


@dataclass
class MacroEventInfo(InfoLevel, EventStringFunctor, pt.MacroEventInfo):
    def code(self):
        return "M011"

    def message(self) -> str:
        return self.msg


@dataclass
class MacroEventDebug(DebugLevel, EventStringFunctor, pt.MacroEventDebug):
    def code(self):
        return "M012"

    def message(self) -> str:
        return self.msg


@dataclass
class DepsNoPackagesFound(InfoLevel, pt.DepsNoPackagesFound):
    def code(self):
        return "M013"

    def message(self) -> str:
        return "Warning: No packages were found in packages.yml"


@dataclass
class DepsStartPackageInstall(InfoLevel, pt.DepsStartPackageInstall):
    def code(self):
        return "M014"

    def message(self) -> str:
        return f"Installing {self.package_name}"


@dataclass
class DepsInstallInfo(InfoLevel, pt.DepsInstallInfo):
    def code(self):
        return "M015"

    def message(self) -> str:
        return f"  Installed from {self.version_name}"


@dataclass
class DepsUpdateAvailable(InfoLevel, pt.DepsUpdateAvailable):
    def code(self):
        return "M016"

    def message(self) -> str:
        return f"  Updated version available: {self.version_latest}"


@dataclass
class DepsUpToDate(InfoLevel, pt.DepsUpToDate):
    def code(self):
        return "M017"

    def message(self) -> str:
        return "  Up to date!"


@dataclass
class DepsListSubdirectory(InfoLevel, pt.DepsListSubdirectory):
    def code(self):
        return "M018"

    def message(self) -> str:
        return f"   and subdirectory {self.subdirectory}"


@dataclass
class DepsNotifyUpdatesAvailable(InfoLevel, pt.DepsNotifyUpdatesAvailable):
    def code(self):
        return "M019"

    def message(self) -> str:
        return "Updates available for packages: {} \
                \nUpdate your versions in packages.yml, then run dbt deps".format(
            self.packages
        )


@dataclass
class RetryExternalCall(DebugLevel, pt.RetryExternalCall):
    def code(self):
        return "M020"

    def message(self) -> str:
        return f"Retrying external call. Attempt: {self.attempt} Max attempts: {self.max}"


@dataclass
class RecordRetryException(DebugLevel, pt.RecordRetryException):
    def code(self):
        return "M021"

    def message(self) -> str:
        return f"External call exception: {self.exc}"


@dataclass
class RegistryIndexProgressGETRequest(DebugLevel, pt.RegistryIndexProgressGETRequest):
    def code(self):
        return "M022"

    def message(self) -> str:
        return f"Making package index registry request: GET {self.url}"


@dataclass
class RegistryIndexProgressGETResponse(DebugLevel, pt.RegistryIndexProgressGETResponse):
    def code(self):
        return "M023"

    def message(self) -> str:
        return f"Response from registry index: GET {self.url} {self.resp_code}"


@dataclass
class RegistryResponseUnexpectedType(DebugLevel, pt.RegistryResponseUnexpectedType):
    def code(self):
        return "M024"

    def message(self) -> str:
        return f"Response was None: {self.response}"


@dataclass
class RegistryResponseMissingTopKeys(DebugLevel, pt.RegistryResponseMissingTopKeys):
    def code(self):
        return "M025"

    def message(self) -> str:
        # expected/actual keys logged in exception
        return f"Response missing top level keys: {self.response}"


@dataclass
class RegistryResponseMissingNestedKeys(DebugLevel, pt.RegistryResponseMissingNestedKeys):
    def code(self):
        return "M026"

    def message(self) -> str:
        # expected/actual keys logged in exception
        return f"Response missing nested keys: {self.response}"


@dataclass
class RegistryResponseExtraNestedKeys(DebugLevel, pt.RegistryResponseExtraNestedKeys):
    def code(self):
        return "M027"

    def message(self) -> str:
        # expected/actual keys logged in exception
        return f"Response contained inconsistent keys: {self.response}"


@dataclass
class DepsSetDownloadDirectory(DebugLevel, pt.DepsSetDownloadDirectory):
    def code(self):
        return "M028"

    def message(self) -> str:
        return f"Set downloads directory='{self.path}'"


# =======================================================
# Q - Node execution
# =======================================================


@dataclass
class RunningOperationCaughtError(ErrorLevel, pt.RunningOperationCaughtError):
    def code(self):
        return "Q001"

    def message(self) -> str:
        return f"Encountered an error while running operation: {self.exc}"


@dataclass
class CompileComplete(InfoLevel, pt.CompileComplete):
    def code(self):
        return "Q002"

    def message(self) -> str:
        return "Done."


@dataclass
class FreshnessCheckComplete(InfoLevel, pt.FreshnessCheckComplete):
    def code(self):
        return "Q003"

    def message(self) -> str:
        return "Done."


@dataclass
class SeedHeader(InfoLevel, pt.SeedHeader):
    def code(self):
        return "Q004"

    def message(self) -> str:
        return self.header


@dataclass
class SeedHeaderSeparator(InfoLevel, pt.SeedHeaderSeparator):
    def code(self):
        return "Q005"

    def message(self) -> str:
        return "-" * self.len_header


@dataclass
class SQLRunnerException(DebugLevel, pt.SQLRunnerException):  # noqa
    def code(self):
        return "Q006"

    def message(self) -> str:
        return f"Got an exception: {self.exc}"


@dataclass
@dataclass
class PrintErrorTestResult(ErrorLevel, pt.PrintErrorTestResult):
    def code(self):
        return "Q007"

    def message(self) -> str:
        info = "ERROR"
        msg = f"{info} {self.name}"
        return format_fancy_output_line(
            msg=msg,
            status=ui.red(info),
            index=self.index,
            total=self.num_models,
            execution_time=self.execution_time,
        )


@dataclass
class PrintPassTestResult(InfoLevel, pt.PrintPassTestResult):
    def code(self):
        return "Q008"

    def message(self) -> str:
        info = "PASS"
        msg = f"{info} {self.name}"
        return format_fancy_output_line(
            msg=msg,
            status=ui.green(info),
            index=self.index,
            total=self.num_models,
            execution_time=self.execution_time,
        )


@dataclass
class PrintWarnTestResult(WarnLevel, pt.PrintWarnTestResult):
    def code(self):
        return "Q009"

    def message(self) -> str:
        info = f"WARN {self.num_failures}"
        msg = f"{info} {self.name}"
        return format_fancy_output_line(
            msg=msg,
            status=ui.yellow(info),
            index=self.index,
            total=self.num_models,
            execution_time=self.execution_time,
        )


@dataclass
class PrintFailureTestResult(ErrorLevel, pt.PrintFailureTestResult):
    def code(self):
        return "Q010"

    def message(self) -> str:
        info = f"FAIL {self.num_failures}"
        msg = f"{info} {self.name}"
        return format_fancy_output_line(
            msg=msg,
            status=ui.red(info),
            index=self.index,
            total=self.num_models,
            execution_time=self.execution_time,
        )


@dataclass
class PrintStartLine(InfoLevel, pt.PrintStartLine):  # noqa
    def code(self):
        return "Q011"

    def message(self) -> str:
        msg = f"START {self.description}"
        return format_fancy_output_line(msg=msg, status="RUN", index=self.index, total=self.total)


@dataclass
class PrintModelResultLine(InfoLevel, pt.PrintModelResultLine):
    def code(self):
        return "Q012"

    def message(self) -> str:
        info = "OK created"
        msg = f"{info} {self.description}"
        return format_fancy_output_line(
            msg=msg,
            status=ui.green(self.status),
            index=self.index,
            total=self.total,
            execution_time=self.execution_time,
        )


@dataclass
class PrintModelErrorResultLine(ErrorLevel, pt.PrintModelErrorResultLine):
    def code(self):
        return "Q013"

    def message(self) -> str:
        info = "ERROR creating"
        msg = f"{info} {self.description}"
        return format_fancy_output_line(
            msg=msg,
            status=ui.red(self.status.upper()),
            index=self.index,
            total=self.total,
            execution_time=self.execution_time,
        )


@dataclass
class PrintSnapshotErrorResultLine(ErrorLevel, pt.PrintSnapshotErrorResultLine):
    def code(self):
        return "Q014"

    def message(self) -> str:
        info = "ERROR snapshotting"
        msg = "{info} {description}".format(info=info, description=self.description, **self.cfg)
        return format_fancy_output_line(
            msg=msg,
            status=ui.red(self.status.upper()),
            index=self.index,
            total=self.total,
            execution_time=self.execution_time,
        )


@dataclass
class PrintSnapshotResultLine(InfoLevel, pt.PrintSnapshotResultLine):
    def code(self):
        return "Q015"

    def message(self) -> str:
        info = "OK snapshotted"
        msg = "{info} {description}".format(info=info, description=self.description, **self.cfg)
        return format_fancy_output_line(
            msg=msg,
            status=ui.green(self.status),
            index=self.index,
            total=self.total,
            execution_time=self.execution_time,
        )


@dataclass
class PrintSeedErrorResultLine(ErrorLevel, pt.PrintSeedErrorResultLine):
    def code(self):
        return "Q016"

    def message(self) -> str:
        info = "ERROR loading"
        msg = f"{info} seed file {self.schema}.{self.relation}"
        return format_fancy_output_line(
            msg=msg,
            status=ui.red(self.status.upper()),
            index=self.index,
            total=self.total,
            execution_time=self.execution_time,
        )


@dataclass
class PrintSeedResultLine(InfoLevel, pt.PrintSeedResultLine):
    def code(self):
        return "Q017"

    def message(self) -> str:
        info = "OK loaded"
        msg = f"{info} seed file {self.schema}.{self.relation}"
        return format_fancy_output_line(
            msg=msg,
            status=ui.green(self.status),
            index=self.index,
            total=self.total,
            execution_time=self.execution_time,
        )


@dataclass
class PrintFreshnessErrorLine(ErrorLevel, pt.PrintFreshnessErrorLine):
    def code(self):
        return "Q018"

    def message(self) -> str:
        info = "ERROR"
        msg = f"{info} freshness of {self.source_name}.{self.table_name}"
        return format_fancy_output_line(
            msg=msg,
            status=ui.red(info),
            index=self.index,
            total=self.total,
            execution_time=self.execution_time,
        )


@dataclass
class PrintFreshnessErrorStaleLine(ErrorLevel, pt.PrintFreshnessErrorStaleLine):
    def code(self):
        return "Q019"

    def message(self) -> str:
        info = "ERROR STALE"
        msg = f"{info} freshness of {self.source_name}.{self.table_name}"
        return format_fancy_output_line(
            msg=msg,
            status=ui.red(info),
            index=self.index,
            total=self.total,
            execution_time=self.execution_time,
        )


@dataclass
class PrintFreshnessWarnLine(WarnLevel, pt.PrintFreshnessWarnLine):
    def code(self):
        return "Q020"

    def message(self) -> str:
        info = "WARN"
        msg = f"{info} freshness of {self.source_name}.{self.table_name}"
        return format_fancy_output_line(
            msg=msg,
            status=ui.yellow(info),
            index=self.index,
            total=self.total,
            execution_time=self.execution_time,
        )


@dataclass
class PrintFreshnessPassLine(InfoLevel, pt.PrintFreshnessPassLine):
    def code(self):
        return "Q021"

    def message(self) -> str:
        info = "PASS"
        msg = f"{info} freshness of {self.source_name}.{self.table_name}"
        return format_fancy_output_line(
            msg=msg,
            status=ui.green(info),
            index=self.index,
            total=self.total,
            execution_time=self.execution_time,
        )


@dataclass
class PrintCancelLine(ErrorLevel, pt.PrintCancelLine):
    def code(self):
        return "Q022"

    def message(self) -> str:
        msg = "CANCEL query {}".format(self.conn_name)
        return format_fancy_output_line(msg=msg, status=ui.red("CANCEL"), index=None, total=None)


@dataclass
class DefaultSelector(InfoLevel, pt.DefaultSelector):
    def code(self):
        return "Q023"

    def message(self) -> str:
        return f"Using default selector {self.name}"


@dataclass
class NodeStart(DebugLevel, pt.NodeStart):
    def code(self):
        return "Q024"

    def message(self) -> str:
        return f"Began running node {self.unique_id}"


@dataclass
class NodeFinished(DebugLevel, pt.NodeFinished):
    def code(self):
        return "Q025"

    def message(self) -> str:
        return f"Finished running node {self.unique_id}"


@dataclass
class QueryCancelationUnsupported(InfoLevel, pt.QueryCancelationUnsupported):
    def code(self):
        return "Q026"

    def message(self) -> str:
        msg = (
            f"The {self.type} adapter does not support query "
            "cancellation. Some queries may still be "
            "running!"
        )
        return ui.yellow(msg)


@dataclass
class ConcurrencyLine(InfoLevel, pt.ConcurrencyLine):  # noqa
    def code(self):
        return "Q027"

    def message(self) -> str:
        return f"Concurrency: {self.num_threads} threads (target='{self.target_name}')"


@dataclass
class CompilingNode(DebugLevel, pt.CompilingNode):
    def code(self):
        return "Q028"

    def message(self) -> str:
        return f"Compiling {self.unique_id}"


@dataclass
class WritingInjectedSQLForNode(DebugLevel, pt.WritingInjectedSQLForNode):
    def code(self):
        return "Q029"

    def message(self) -> str:
        return f'Writing injected SQL for node "{self.unique_id}"'


@dataclass
class NodeCompiling(DebugLevel, pt.NodeCompiling):
    def code(self):
        return "Q030"

    def message(self) -> str:
        return f"Began compiling node {self.unique_id}"


@dataclass
class NodeExecuting(DebugLevel, pt.NodeExecuting):
    def code(self):
        return "Q031"

    def message(self) -> str:
        return f"Began executing node {self.unique_id}"


@dataclass
class PrintHookStartLine(InfoLevel, pt.PrintHookStartLine):  # noqa
    def code(self):
        return "Q032"

    def message(self) -> str:
        msg = f"START hook: {self.statement}"
        return format_fancy_output_line(
            msg=msg, status="RUN", index=self.index, total=self.total, truncate=True
        )


@dataclass
class PrintHookEndLine(InfoLevel, pt.PrintHookEndLine):  # noqa
    def code(self):
        return "Q033"

    def message(self) -> str:
        msg = "OK hook: {}".format(self.statement)
        return format_fancy_output_line(
            msg=msg,
            status=ui.green(self.status),
            index=self.index,
            total=self.total,
            execution_time=self.execution_time,
            truncate=True,
        )


@dataclass
class SkippingDetails(InfoLevel, pt.SkippingDetails):
    def code(self):
        return "Q034"

    def message(self) -> str:
        if self.resource_type in NodeType.refable():
            msg = f"SKIP relation {self.schema}.{self.node_name}"
        else:
            msg = f"SKIP {self.resource_type} {self.node_name}"
        return format_fancy_output_line(
            msg=msg, status=ui.yellow("SKIP"), index=self.index, total=self.total
        )


# Skipped Q035


@dataclass
class RunningOperationUncaughtError(ErrorLevel, pt.RunningOperationUncaughtError):
    def code(self):
        return "Q036"

    def message(self) -> str:
        return f"Encountered an error while running operation: {self.exc}"


@dataclass
class EndRunResult(DebugLevel, pt.EndRunResult):
    def code(self):
        return "Q037"

    def message(self) -> str:
        return "Command end result"


# =======================================================
# W - Node testing
# =======================================================

# Skipped W001


@dataclass
class CatchableExceptionOnRun(DebugLevel, pt.CatchableExceptionOnRun):  # noqa
    def code(self):
        return "W002"

    def message(self) -> str:
        return str(self.exc)


@dataclass
class InternalExceptionOnRun(DebugLevel, pt.InternalExceptionOnRun):
    def code(self):
        return "W003"

    def message(self) -> str:
        prefix = "Internal error executing {}".format(self.build_path)

        internal_error_string = """This is an error in dbt. Please try again. If \
the error persists, open an issue at https://github.com/dbt-labs/dbt-core
""".strip()

        return "{prefix}\n{error}\n\n{note}".format(
            prefix=ui.red(prefix), error=str(self.exc).strip(), note=internal_error_string
        )


@dataclass
class GenericExceptionOnRun(ErrorLevel, pt.GenericExceptionOnRun):
    def code(self):
        return "W004"

    def message(self) -> str:
        node_description = self.build_path
        if node_description is None:
            node_description = self.unique_id
        prefix = "Unhandled error while executing {}".format(node_description)
        return "{prefix}\n{error}".format(prefix=ui.red(prefix), error=str(self.exc).strip())


@dataclass
class NodeConnectionReleaseError(DebugLevel, pt.NodeConnectionReleaseError):  # noqa
    def code(self):
        return "W005"

    def message(self) -> str:
        return "Error releasing connection for node {}: {!s}".format(self.node_name, self.exc)


@dataclass
class FoundStats(InfoLevel, pt.FoundStats):
    def code(self):
        return "W006"

    def message(self) -> str:
        return f"Found {self.stat_line}"


# =======================================================
# Z - Misc
# =======================================================


@dataclass
class MainKeyboardInterrupt(InfoLevel, pt.MainKeyboardInterrupt):
    def code(self):
        return "Z001"

    def message(self) -> str:
        return "ctrl-c"


@dataclass
class MainEncounteredError(ErrorLevel, pt.MainEncounteredError):  # noqa
    def code(self):
        return "Z002"

    def message(self) -> str:
        return f"Encountered an error:\n{self.exc}"


@dataclass
class MainStackTrace(ErrorLevel, pt.MainStackTrace):
    def code(self):
        return "Z003"

    def message(self) -> str:
        return self.stack_trace


@dataclass
class SystemErrorRetrievingModTime(ErrorLevel, pt.SystemErrorRetrievingModTime):
    def code(self):
        return "Z004"

    def message(self) -> str:
        return f"Error retrieving modification time for file {self.path}"


@dataclass
class SystemCouldNotWrite(DebugLevel, pt.SystemCouldNotWrite):
    def code(self):
        return "Z005"

    def message(self) -> str:
        return (
            f"Could not write to path {self.path}({len(self.path)} characters): "
            f"{self.reason}\nexception: {self.exc}"
        )


@dataclass
class SystemExecutingCmd(DebugLevel, pt.SystemExecutingCmd):
    def code(self):
        return "Z006"

    def message(self) -> str:
        return f'Executing "{" ".join(self.cmd)}"'


@dataclass
class SystemStdOutMsg(DebugLevel, pt.SystemStdOutMsg):
    def code(self):
        return "Z007"

    def message(self) -> str:
        return f'STDOUT: "{str(self.bmsg)}"'


@dataclass
class SystemStdErrMsg(DebugLevel, pt.SystemStdErrMsg):
    def code(self):
        return "Z008"

    def message(self) -> str:
        return f'STDERR: "{str(self.bmsg)}"'


@dataclass
class SystemReportReturnCode(DebugLevel, pt.SystemReportReturnCode):
    def code(self):
        return "Z009"

    def message(self) -> str:
        return f"command return code={self.returncode}"


@dataclass
class TimingInfoCollected(DebugLevel, pt.TimingInfoCollected):
    def code(self):
        return "Z010"

    def message(self) -> str:
        return "finished collecting timing info"


# This prints the stack trace at the debug level while allowing just the nice exception message
# at the error level - or whatever other level chosen.  Used in multiple places.
@dataclass
class PrintDebugStackTrace(DebugLevel, pt.PrintDebugStackTrace):  # noqa
    def code(self):
        return "Z011"

    def message(self) -> str:
        return ""


# We don't write "clean" events to the log, because the clean command
# may have removed the log directory.
@dataclass
class CheckCleanPath(InfoLevel, NoFile, pt.CheckCleanPath):
    def code(self):
        return "Z012"

    def message(self) -> str:
        return f"Checking {self.path}/*"


@dataclass
class ConfirmCleanPath(InfoLevel, NoFile, pt.ConfirmCleanPath):
    def code(self):
        return "Z013"

    def message(self) -> str:
        return f"Cleaned {self.path}/*"


@dataclass
class ProtectedCleanPath(InfoLevel, NoFile, pt.ProtectedCleanPath):
    def code(self):
        return "Z014"

    def message(self) -> str:
        return f"ERROR: not cleaning {self.path}/* because it is protected"


@dataclass
class FinishedCleanPaths(InfoLevel, NoFile, pt.FinishedCleanPaths):
    def code(self):
        return "Z015"

    def message(self) -> str:
        return "Finished cleaning all paths."


@dataclass
class OpenCommand(InfoLevel, pt.OpenCommand):
    def code(self):
        return "Z016"

    def message(self) -> str:
        msg = f"""To view your profiles.yml file, run:

{self.open_cmd} {self.profiles_dir}"""

        return msg


@dataclass
class EmptyLine(InfoLevel, pt.EmptyLine):
    def code(self):
        return "Z017"

    def message(self) -> str:
        return ""


@dataclass
class ServingDocsPort(InfoLevel, pt.ServingDocsPort):
    def code(self):
        return "Z018"

    def message(self) -> str:
        return f"Serving docs at {self.address}:{self.port}"


@dataclass
class ServingDocsAccessInfo(InfoLevel, pt.ServingDocsAccessInfo):
    def code(self):
        return "Z019"

    def message(self) -> str:
        return f"To access from your browser, navigate to:  http://localhost:{self.port}"


@dataclass
class ServingDocsExitInfo(InfoLevel, pt.ServingDocsExitInfo):
    def code(self):
        return "Z020"

    def message(self) -> str:
        return "Press Ctrl+C to exit."


@dataclass
class RunResultWarning(WarnLevel, pt.RunResultWarning):
    def code(self):
        return "Z021"

    def message(self) -> str:
        info = "Warning"
        return ui.yellow(f"{info} in {self.resource_type} {self.node_name} ({self.path})")


@dataclass
class RunResultFailure(ErrorLevel, pt.RunResultFailure):
    def code(self):
        return "Z022"

    def message(self) -> str:
        info = "Failure"
        return ui.red(f"{info} in {self.resource_type} {self.node_name} ({self.path})")


@dataclass
class StatsLine(InfoLevel, pt.StatsLine):
    def code(self):
        return "Z023"

    def message(self) -> str:
        stats_line = "Done. PASS={pass} WARN={warn} ERROR={error} SKIP={skip} TOTAL={total}"
        return stats_line.format(**self.stats)


@dataclass
class RunResultError(ErrorLevel, EventStringFunctor, pt.RunResultError):
    def code(self):
        return "Z024"

    def message(self) -> str:
        return f"  {self.msg}"


@dataclass
class RunResultErrorNoMessage(ErrorLevel, pt.RunResultErrorNoMessage):
    def code(self):
        return "Z025"

    def message(self) -> str:
        return f"  Status: {self.status}"


@dataclass
class SQLCompiledPath(InfoLevel, pt.SQLCompiledPath):
    def code(self):
        return "Z026"

    def message(self) -> str:
        return f"  compiled Code at {self.path}"


@dataclass
class CheckNodeTestFailure(InfoLevel, pt.CheckNodeTestFailure):
    def code(self):
        return "Z027"

    def message(self) -> str:
        msg = f"select * from {self.relation_name}"
        border = "-" * len(msg)
        return f"  See test failures:\n  {border}\n  {msg}\n  {border}"


@dataclass
class FirstRunResultError(ErrorLevel, EventStringFunctor, pt.FirstRunResultError):
    def code(self):
        return "Z028"

    def message(self) -> str:
        return ui.yellow(self.msg)


@dataclass
class AfterFirstRunResultError(ErrorLevel, EventStringFunctor, pt.AfterFirstRunResultError):
    def code(self):
        return "Z029"

    def message(self) -> str:
        return self.msg


@dataclass
class EndOfRunSummary(InfoLevel, pt.EndOfRunSummary):
    def code(self):
        return "Z030"

    def message(self) -> str:
        error_plural = pluralize(self.num_errors, "error")
        warn_plural = pluralize(self.num_warnings, "warning")
        if self.keyboard_interrupt:
            message = ui.yellow("Exited because of keyboard interrupt.")
        elif self.num_errors > 0:
            message = ui.red("Completed with {} and {}:".format(error_plural, warn_plural))
        elif self.num_warnings > 0:
            message = ui.yellow("Completed with {}:".format(warn_plural))
        else:
            message = ui.green("Completed successfully")
        return message


# Skipped Z031, Z032, Z033


@dataclass
class PrintSkipBecauseError(ErrorLevel, pt.PrintSkipBecauseError):
    def code(self):
        return "Z034"

    def message(self) -> str:
        msg = f"SKIP relation {self.schema}.{self.relation} due to ephemeral model error"
        return format_fancy_output_line(
            msg=msg, status=ui.red("ERROR SKIP"), index=self.index, total=self.total
        )


# Skipped Z035


@dataclass
class EnsureGitInstalled(ErrorLevel, pt.EnsureGitInstalled):
    def code(self):
        return "Z036"

    def message(self) -> str:
        return (
            "Make sure git is installed on your machine. More "
            "information: "
            "https://docs.getdbt.com/docs/package-management"
        )


@dataclass
class DepsCreatingLocalSymlink(DebugLevel, pt.DepsCreatingLocalSymlink):
    def code(self):
        return "Z037"

    def message(self) -> str:
        return "  Creating symlink to local dependency."


@dataclass
class DepsSymlinkNotAvailable(DebugLevel, pt.DepsSymlinkNotAvailable):
    def code(self):
        return "Z038"

    def message(self) -> str:
        return "  Symlinks are not available on this OS, copying dependency."


@dataclass
class DisableTracking(DebugLevel, pt.DisableTracking):
    def code(self):
        return "Z039"

    def message(self) -> str:
        return (
            "Error sending anonymous usage statistics. Disabling tracking for this execution. "
            "If you wish to permanently disable tracking, see: "
            "https://docs.getdbt.com/reference/global-configs#send-anonymous-usage-stats."
        )


@dataclass
class SendingEvent(DebugLevel, pt.SendingEvent):
    def code(self):
        return "Z040"

    def message(self) -> str:
        return f"Sending event: {self.kwargs}"


@dataclass
class SendEventFailure(DebugLevel, pt.SendEventFailure):
    def code(self):
        return "Z041"

    def message(self) -> str:
        return "An error was encountered while trying to send an event"


@dataclass
class FlushEvents(DebugLevel, pt.FlushEvents):
    def code(self):
        return "Z042"

    def message(self) -> str:
        return "Flushing usage events"


@dataclass
class FlushEventsFailure(DebugLevel, pt.FlushEventsFailure):
    def code(self):
        return "Z043"

    def message(self) -> str:
        return "An error was encountered while trying to flush usage events"


@dataclass
class TrackingInitializeFailure(DebugLevel, pt.TrackingInitializeFailure):  # noqa
    def code(self):
        return "Z044"

    def message(self) -> str:
        return "Got an exception trying to initialize tracking"


# Skipped Z045


@dataclass
class GeneralWarningMsg(WarnLevel, EventStringFunctor, pt.GeneralWarningMsg):
    def code(self):
        return "Z046"

    def message(self) -> str:
        return self.log_fmt.format(self.msg) if self.log_fmt is not None else self.msg


@dataclass
class GeneralWarningException(WarnLevel, pt.GeneralWarningException):
    def code(self):
        return "Z047"

    def message(self) -> str:
        return self.log_fmt.format(str(self.exc)) if self.log_fmt is not None else str(self.exc)


@dataclass
class EventBufferFull(WarnLevel, pt.EventBufferFull):
    def code(self):
        return "Z048"

    def message(self) -> str:
        return (
            "Internal logging/event buffer full."
            "Earliest logs/events will be dropped as new ones are fired (FIFO)."
        )


@dataclass
class RunResultWarningMessage(WarnLevel, EventStringFunctor, pt.RunResultWarningMessage):
    def code(self):
        return "Z049"

    def message(self) -> str:
        return self.msg


# since mypy doesn't run on every file we need to suggest to mypy that every
# class gets instantiated. But we don't actually want to run this code.
# making the conditional `if False` causes mypy to skip it as dead code so
# we need to skirt around that by computing something it doesn't check statically.
#
# TODO remove these lines once we run mypy everywhere.
if 1 == 0:

    # A - pre-project loading
    MainReportVersion(version="")
    MainReportArgs(args={})
    MainTrackingUserState(user_state="")
    MergedFromState(num_merged=0, sample=[])
    MissingProfileTarget(profile_name="", target_name="")
    InvalidVarsYAML()
    DbtProjectError()
    DbtProjectErrorException(exc="")
    DbtProfileError()
    DbtProfileErrorException(exc="")
    ProfileListTitle()
    ListSingleProfile(profile="")
    NoDefinedProfiles()
    ProfileHelpMessage()
    StarterProjectPath(dir="")
    ConfigFolderDirectory(dir="")
    NoSampleProfileFound(adapter="")
    ProfileWrittenWithSample(name="", path="")
    ProfileWrittenWithTargetTemplateYAML(name="", path="")
    ProfileWrittenWithProjectTemplateYAML(name="", path="")
    SettingUpProfile()
    InvalidProfileTemplateYAML()
    ProjectNameAlreadyExists(name="")
    ProjectCreated(project_name="")

    # E - DB Adapter ======================
    AdapterEventDebug()
    AdapterEventInfo()
    AdapterEventWarning()
    AdapterEventError()
    NewConnection(conn_type="", conn_name="")
    ConnectionReused(conn_name="")
    ConnectionLeftOpen(conn_name="")
    ConnectionClosed(conn_name="")
    RollbackFailed(conn_name="")
    ConnectionClosed2(conn_name="")
    ConnectionLeftOpen2(conn_name="")
    Rollback(conn_name="")
    CacheMiss(conn_name="", database="", schema="")
    ListRelations(database="", schema="")
    ConnectionUsed(conn_type="", conn_name="")
    SQLQuery(conn_name="", sql="")
    SQLQueryStatus(status="", elapsed=0.1)
    SQLCommit(conn_name="")
    ColTypeChange(
        orig_type="", new_type="", table=ReferenceKeyMsg(database="", schema="", identifier="")
    )
    SchemaCreation(relation=ReferenceKeyMsg(database="", schema="", identifier=""))
    SchemaDrop(relation=ReferenceKeyMsg(database="", schema="", identifier=""))
    UncachedRelation(
        dep_key=ReferenceKeyMsg(database="", schema="", identifier=""),
        ref_key=ReferenceKeyMsg(database="", schema="", identifier=""),
    )
    AddLink(
        dep_key=ReferenceKeyMsg(database="", schema="", identifier=""),
        ref_key=ReferenceKeyMsg(database="", schema="", identifier=""),
    )
    AddRelation(relation=ReferenceKeyMsg(database="", schema="", identifier=""))
    DropMissingRelation(relation=ReferenceKeyMsg(database="", schema="", identifier=""))
    DropCascade(
        dropped=ReferenceKeyMsg(database="", schema="", identifier=""),
        consequences=[ReferenceKeyMsg(database="", schema="", identifier="")],
    )
    DropRelation(dropped=ReferenceKeyMsg())
    UpdateReference(
        old_key=ReferenceKeyMsg(database="", schema="", identifier=""),
        new_key=ReferenceKeyMsg(database="", schema="", identifier=""),
        cached_key=ReferenceKeyMsg(database="", schema="", identifier=""),
    )
    TemporaryRelation(key=ReferenceKeyMsg(database="", schema="", identifier=""))
    RenameSchema(
        old_key=ReferenceKeyMsg(database="", schema="", identifier=""),
        new_key=ReferenceKeyMsg(database="", schema="", identifier=""),
    )
    DumpBeforeAddGraph(dump=dict())
    DumpAfterAddGraph(dump=dict())
    DumpBeforeRenameSchema(dump=dict())
    DumpAfterRenameSchema(dump=dict())
    AdapterImportError(exc="")
    PluginLoadError(exc_info="")
    NewConnectionOpening(connection_state="")
    CodeExecution(conn_name="", code_content="")
    CodeExecutionStatus(status="", elapsed=0.1)
    WriteCatalogFailure(num_exceptions=0)
    CatalogWritten(path="")
    CannotGenerateDocs()
    BuildingCatalog()
    DatabaseErrorRunningHook(hook_type="")
    HooksRunning(num_hooks=0, hook_type="")
    HookFinished(stat_line="", execution="", execution_time=0)

    # I - Project parsing ======================
    ParseCmdStart()
    ParseCmdCompiling()
    ParseCmdWritingManifest()
    ParseCmdDone()
    ManifestDependenciesLoaded()
    ManifestLoaderCreated()
    ManifestLoaded()
    ManifestChecked()
    ManifestFlatGraphBuilt()
    ParseCmdPerfInfoPath(path="")
    GenericTestFileParse(path="")
    MacroFileParse(path="")
    PartialParsingFullReparseBecauseOfError()
    PartialParsingExceptionFile(file="")
    PartialParsingFile(file_id="")
    PartialParsingException(exc_info={})
    PartialParsingSkipParsing()
    PartialParsingMacroChangeStartFullParse()
    PartialParsingProjectEnvVarsChanged()
    PartialParsingProfileEnvVarsChanged()
    PartialParsingDeletedMetric(unique_id="")
    ManifestWrongMetadataVersion(version="")
    PartialParsingVersionMismatch(saved_version="", current_version="")
    PartialParsingFailedBecauseConfigChange()
    PartialParsingFailedBecauseProfileChange()
    PartialParsingFailedBecauseNewProjectDependency()
    PartialParsingFailedBecauseHashChanged()
    PartialParsingNotEnabled()
    ParsedFileLoadFailed(path="", exc="", exc_info="")
    PartialParseSaveFileNotFound()
    StaticParserCausedJinjaRendering(path="")
    UsingExperimentalParser(path="")
    SampleFullJinjaRendering(path="")
    StaticParserFallbackJinjaRendering(path="")
    StaticParsingMacroOverrideDetected(path="")
    StaticParserSuccess(path="")
    StaticParserFailure(path="")
    ExperimentalParserSuccess(path="")
    ExperimentalParserFailure(path="")
    PartialParsingEnabled(deleted=0, added=0, changed=0)
    PartialParsingAddedFile(file_id="")
    PartialParsingDeletedFile(file_id="")
    PartialParsingUpdatedFile(file_id="")
    PartialParsingNodeMissingInSourceFile(file_id="")
    PartialParsingMissingNodes(file_id="")
    PartialParsingChildMapMissingUniqueID(unique_id="")
    PartialParsingUpdateSchemaFile(file_id="")
    PartialParsingDeletedSource(unique_id="")
    PartialParsingDeletedExposure(unique_id="")
    InvalidDisabledSourceInTestNode(msg="")
    InvalidRefInTestNode(msg="")

    # M - Deps generation ======================

    GitSparseCheckoutSubdirectory(subdir="")
    GitProgressCheckoutRevision(revision="")
    GitProgressUpdatingExistingDependency(dir="")
    GitProgressPullingNewDependency(dir="")
    GitNothingToDo(sha="")
    GitProgressUpdatedCheckoutRange(start_sha="", end_sha="")
    GitProgressCheckedOutAt(end_sha="")
    RegistryProgressGETRequest(url="")
    RegistryProgressGETResponse(url="", resp_code=1234)
    SelectorReportInvalidSelector(valid_selectors="", spec_method="", raw_spec="")
    MacroEventInfo(msg="")
    MacroEventDebug(msg="")
    DepsNoPackagesFound()
    DepsStartPackageInstall(package_name="")
    DepsInstallInfo(version_name="")
    DepsUpdateAvailable(version_latest="")
    DepsUpToDate()
    DepsListSubdirectory(subdirectory="")
    DepsNotifyUpdatesAvailable(packages=ListOfStrings())
    RetryExternalCall(attempt=0, max=0)
    RecordRetryException(exc="")
    RegistryIndexProgressGETRequest(url="")
    RegistryIndexProgressGETResponse(url="", resp_code=1234)
    RegistryResponseUnexpectedType(response=""),
    RegistryResponseMissingTopKeys(response=""),
    RegistryResponseMissingNestedKeys(response=""),
    RegistryResponseExtraNestedKeys(response=""),
    DepsSetDownloadDirectory(path="")

    # Q - Node execution ======================

    RunningOperationCaughtError(exc="")
    CompileComplete()
    FreshnessCheckComplete()
    SeedHeader(header="")
    SeedHeaderSeparator(len_header=0)
    SQLRunnerException(exc="")
    PrintErrorTestResult(
        name="",
        index=0,
        num_models=0,
        execution_time=0,
    )
    PrintPassTestResult(
        name="",
        index=0,
        num_models=0,
        execution_time=0,
    )
    PrintWarnTestResult(
        name="",
        index=0,
        num_models=0,
        execution_time=0,
        num_failures=0,
    )
    PrintFailureTestResult(
        name="",
        index=0,
        num_models=0,
        execution_time=0,
        num_failures=0,
    )
    PrintStartLine(description="", index=0, total=0, node_info=NodeInfo())
    PrintModelResultLine(
        description="",
        status="",
        index=0,
        total=0,
        execution_time=0,
    )
    PrintModelErrorResultLine(
        description="",
        status="",
        index=0,
        total=0,
        execution_time=0,
    )
    PrintSnapshotErrorResultLine(
        status="",
        description="",
        cfg={},
        index=0,
        total=0,
        execution_time=0,
    )
    PrintSnapshotResultLine(
        status="",
        description="",
        cfg={},
        index=0,
        total=0,
        execution_time=0,
    )
    PrintSeedErrorResultLine(
        status="",
        index=0,
        total=0,
        execution_time=0,
        schema="",
        relation="",
    )
    PrintSeedResultLine(
        status="",
        index=0,
        total=0,
        execution_time=0,
        schema="",
        relation="",
    )
    PrintFreshnessErrorLine(
        source_name="",
        table_name="",
        index=0,
        total=0,
        execution_time=0,
    )
    PrintFreshnessErrorStaleLine(
        source_name="",
        table_name="",
        index=0,
        total=0,
        execution_time=0,
    )
    PrintFreshnessWarnLine(
        source_name="",
        table_name="",
        index=0,
        total=0,
        execution_time=0,
    )
    PrintFreshnessPassLine(
        source_name="",
        table_name="",
        index=0,
        total=0,
        execution_time=0,
    )
    PrintCancelLine(conn_name="")
    DefaultSelector(name="")
    NodeStart(unique_id="")
    NodeFinished(unique_id="")
    QueryCancelationUnsupported(type="")
    ConcurrencyLine(num_threads=0, target_name="")
    CompilingNode(unique_id="")
    WritingInjectedSQLForNode(unique_id="")
    NodeCompiling(unique_id="")
    NodeExecuting(unique_id="")
    PrintHookStartLine(
        statement="",
        index=0,
        total=0,
    )
    PrintHookEndLine(
        statement="",
        status="",
        index=0,
        total=0,
        execution_time=0,
    )
    SkippingDetails(
        resource_type="",
        schema="",
        node_name="",
        index=0,
        total=0,
    )
    RunningOperationUncaughtError(exc="")
    EndRunResult()

    # W - Node testing ======================

    CatchableExceptionOnRun(exc="")
    InternalExceptionOnRun(build_path="", exc="")
    GenericExceptionOnRun(build_path="", unique_id="", exc="")
    NodeConnectionReleaseError(node_name="", exc="")
    FoundStats(stat_line="")

    # Z - misc ======================

    MainKeyboardInterrupt()
    MainEncounteredError(exc="")
    MainStackTrace(stack_trace="")
    SystemErrorRetrievingModTime(path="")
    SystemCouldNotWrite(path="", reason="", exc="")
    SystemExecutingCmd(cmd=[""])
    SystemStdOutMsg(bmsg=b"")
    SystemStdErrMsg(bmsg=b"")
    SystemReportReturnCode(returncode=0)
    TimingInfoCollected()
    PrintDebugStackTrace()
    CheckCleanPath(path="")
    ConfirmCleanPath(path="")
    ProtectedCleanPath(path="")
    FinishedCleanPaths()
    OpenCommand(open_cmd="", profiles_dir="")
    EmptyLine()
    ServingDocsPort(address="", port=0)
    ServingDocsAccessInfo(port="")
    ServingDocsExitInfo()
    RunResultWarning(resource_type="", node_name="", path="")
    RunResultFailure(resource_type="", node_name="", path="")
    StatsLine(stats={})
    RunResultError(msg="")
    RunResultErrorNoMessage(status="")
    SQLCompiledPath(path="")
    CheckNodeTestFailure(relation_name="")
    FirstRunResultError(msg="")
    AfterFirstRunResultError(msg="")
    EndOfRunSummary(num_errors=0, num_warnings=0, keyboard_interrupt=False)
    PrintSkipBecauseError(schema="", relation="", index=0, total=0)
    EnsureGitInstalled()
    DepsCreatingLocalSymlink()
    DepsSymlinkNotAvailable()
    DisableTracking()
    SendingEvent(kwargs="")
    SendEventFailure()
    FlushEvents()
    FlushEventsFailure()
    TrackingInitializeFailure()
    GeneralWarningMsg(msg="", log_fmt="")
    GeneralWarningException(exc="", log_fmt="")
    EventBufferFull()
