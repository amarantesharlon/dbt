from dataclasses import dataclass
import os
import threading
from datetime import datetime

# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# These base types define the _required structure_ for the concrete event #
# types defined in types.py                                               #
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #


class Cache:
    # Events with this class will only be logged when the `--log-cache-events` flag is passed
    pass


def get_global_metadata_vars() -> dict:
    from dbt.events.functions import get_metadata_vars

    return get_metadata_vars()


def get_invocation_id() -> str:
    from dbt.events.functions import get_invocation_id

    return get_invocation_id()


# exactly one pid per concrete event
def get_pid() -> int:
    return os.getpid()


# preformatted time stamp
def get_ts_rfc3339() -> str:
    ts = datetime.utcnow()
    ts_rfc3339 = ts.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    return ts_rfc3339


# in theory threads can change so we don't cache them.
def get_thread_name() -> str:
    return threading.current_thread().name


@dataclass
class BaseEvent:
    """BaseEvent for proto message generated python events"""

    def __post_init__(self):
        super().__post_init__()
        self.info.level = self.level_tag()
        if not hasattr(self.info, "msg") or not self.info.msg:
            self.info.msg = self.message()
        self.info.invocation_id = get_invocation_id()
        self.info.extra = get_global_metadata_vars()
        self.info.ts = datetime.utcnow()
        self.info.pid = get_pid()
        self.info.thread = get_thread_name()
        self.info.code = self.code()
        self.info.name = type(self).__name__

    def level_tag(self):
        raise Exception("level_tag() not implemented for event")

    def message(self):
        raise Exception("message() not implemented for event")


@dataclass
class TestLevel(BaseEvent):
    __test__ = False

    def level_tag(self) -> str:
        return "test"


@dataclass  # type: ignore[misc]
class DebugLevel(BaseEvent):
    def level_tag(self) -> str:
        return "debug"


@dataclass  # type: ignore[misc]
class InfoLevel(BaseEvent):
    def level_tag(self) -> str:
        return "info"


@dataclass  # type: ignore[misc]
class WarnLevel(BaseEvent):
    def level_tag(self) -> str:
        return "warn"


@dataclass  # type: ignore[misc]
class ErrorLevel(BaseEvent):
    def level_tag(self) -> str:
        return "error"


# prevents an event from going to the file
# This should rarely be used in core code. It is currently
# only used in integration tests and for the 'clean' command.
class NoFile:
    pass


# prevents an event from going to stdout
class NoStdOut:
    pass
