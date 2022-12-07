from colorama import Style
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import json
import logging
from logging.handlers import RotatingFileHandler
import threading
from typing import Any, Callable, List, Optional, TextIO
from uuid import uuid4

from dbt.events.base_types import BaseEvent, EventLevel


# A Filter is a function which takes a BaseEvent and returns True if the event
# should be logged, False otherwise.
Filter = Callable[[BaseEvent], bool]


# Default filter which logs every event
def NoFilter(_: BaseEvent) -> bool:
    return True


# A Scrubber removes secrets from an input string, returning a sanitized string.
Scrubber = Callable[[str], str]


# Provide a pass-through scrubber implementation, also used as a default
def NoScrubber(s: str) -> str:
    return s


class LineFormat(Enum):
    PlainText = 1
    DebugText = 2
    Json = 3


# Map from dbt event levels to python log levels
_log_level_map = {
    EventLevel.DEBUG: 10,
    EventLevel.TEST: 10,
    EventLevel.INFO: 20,
    EventLevel.WARN: 30,
    EventLevel.ERROR: 40,
}


@dataclass
class LoggerConfig:
    name: str
    filter: Filter = NoFilter
    scrubber: Scrubber = NoScrubber
    line_format: LineFormat = LineFormat.PlainText
    level: EventLevel = EventLevel.WARN
    use_colors: bool = False
    output_stream: Optional[TextIO] = None
    output_file_name: Optional[str] = None
    logger: Optional[Any] = None


class _Logger:
    def __init__(self, event_manager: "EventManager", config: LoggerConfig) -> None:
        self.name: str = config.name
        self.filter: Filter = config.filter
        self.scrubber: Scrubber = config.scrubber
        self.level: EventLevel = config.level
        self.event_manager: EventManager = event_manager
        self._python_logger: Optional[logging.Logger] = config.logger
        self._stream: Optional[TextIO] = config.output_stream

        if config.output_file_name:
            log = logging.getLogger(config.name)
            log.setLevel(_log_level_map[config.level])
            handler = RotatingFileHandler(
                filename=str(config.output_file_name),
                encoding="utf8",
                maxBytes=10 * 1024 * 1024,  # 10 mb
                backupCount=5,
            )

            handler.setFormatter(logging.Formatter(fmt="%(message)s"))
            log.handlers.clear()
            log.addHandler(handler)

            self._python_logger = log

    def create_line(self, e: BaseEvent) -> str:
        raise NotImplementedError()

    def write_line(self, e: BaseEvent):
        line = self.create_line(e)
        python_level = _log_level_map[e.log_level()]
        if self._python_logger is not None:
            self._python_logger.log(python_level, line)
        elif self._stream is not None and _log_level_map[self.level] <= python_level:
            self._stream.write(line + "\n")

    def flush(self):
        if self._python_logger is not None:
            for handler in self._python_logger.handlers:
                handler.flush()
        elif self._stream is not None:
            self._stream.flush()


class _TextLogger(_Logger):
    def __init__(self, event_manager: "EventManager", config: LoggerConfig) -> None:
        super().__init__(event_manager, config)
        self.use_colors = config.use_colors
        self.use_debug_format = config.line_format == LineFormat.DebugText

    def create_line(self, e: BaseEvent) -> str:
        return self.create_debug_line(e) if self.use_debug_format else self.create_info_line(e)

    def create_info_line(self, e: BaseEvent) -> str:
        ts: str = datetime.utcnow().strftime("%H:%M:%S")
        scrubbed_msg: str = self.scrubber(e.message())  # type: ignore
        return f"{self._get_color_tag()}{ts}  {scrubbed_msg}"

    def create_debug_line(self, e: BaseEvent) -> str:
        log_line: str = ""
        # Create a separator if this is the beginning of an invocation
        # TODO: This is an ugly hack, get rid of it if we can
        if type(e).__name__ == "MainReportVersion":
            separator = 30 * "="
            log_line = f"\n\n{separator} {datetime.utcnow()} | {self.event_manager.invocation_id} {separator}\n"
        ts: str = datetime.utcnow().strftime("%H:%M:%S.%f")
        scrubbed_msg: str = self.scrubber(e.message())  # type: ignore
        # log_level() for DynamicLevel events returns str instead of EventLevel
        level = e.log_level().value if isinstance(e.log_level(), EventLevel) else e.log_level()
        log_line += (
            f"{self._get_color_tag()}{ts} [{level:<5}]{self._get_thread_name()} {scrubbed_msg}"
        )
        return log_line

    def _get_color_tag(self) -> str:
        return "" if not self.use_colors else Style.RESET_ALL

    def _get_thread_name(self) -> str:
        thread_name = ""
        if threading.current_thread().name:
            thread_name = threading.current_thread().name
            thread_name = thread_name[:10]
            thread_name = thread_name.ljust(10, " ")
            thread_name = f" [{thread_name}]:"
        return thread_name


class _JsonLogger(_Logger):
    def create_line(self, e: BaseEvent) -> str:
        from dbt.events.functions import event_to_dict

        event_dict = event_to_dict(e)
        raw_log_line = json.dumps(event_dict, sort_keys=True)
        line = self.scrubber(raw_log_line)  # type: ignore
        return line


class EventManager:
    def __init__(self) -> None:
        self.loggers: List[_Logger] = []
        self.callbacks: List[Callable[[BaseEvent], None]] = []
        self.invocation_id: str = str(uuid4())

    def fire_event(self, e: BaseEvent) -> None:
        for logger in self.loggers:
            if logger.filter(e):  # type: ignore
                logger.write_line(e)

        for callback in self.callbacks:
            callback(e)

    def add_logger(self, config: LoggerConfig):
        logger = (
            _JsonLogger(self, config)
            if config.line_format == LineFormat.Json
            else _TextLogger(self, config)
        )
        logger.event_manager = self
        self.loggers.append(logger)

    def flush(self):
        for logger in self.loggers:
            logger.flush()
