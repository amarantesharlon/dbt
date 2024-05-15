from argparse import Namespace
from copy import deepcopy

from pytest_mock import MockerFixture

from dbt.events.logging import setup_event_logger
from dbt.flags import get_flags, set_from_args
from dbt_common.events.base_types import BaseEvent
from dbt_common.events.event_manager_client import get_event_manager
from dbt_common.events.logger import LoggerConfig
from tests.utils import EventCatcher


class TestSetupEventLogger:
    def test_clears_preexisting_event_manager_state(self, mock_global_event_manager) -> None:
        manager = get_event_manager()
        manager.add_logger(LoggerConfig(name="test_logger"))
        manager.callbacks.append(EventCatcher(BaseEvent).catch)
        assert len(manager.loggers) == 1
        assert len(manager.callbacks) == 1

        flags = deepcopy(get_flags())
        # setting both of these to none guarantees that no logger will be added
        object.__setattr__(flags, "LOG_LEVEL", "none")
        object.__setattr__(flags, "LOG_LEVEL_FILE", "none")

        setup_event_logger(flags=flags)
        assert len(manager.loggers) == 0
        assert len(manager.callbacks) == 0

    def test_specify_max_bytes(
        self,
        mocker: MockerFixture,
        mock_global_event_manager,
    ) -> None:
        patched_file_handler = mocker.patch("dbt_common.events.logger.RotatingFileHandler")
        args = Namespace(log_file_max_bytes=1234567)
        set_from_args(args, {})
        setup_event_logger(get_flags())
        patched_file_handler.assert_called_once_with(
            filename="logs/dbt.log", encoding="utf8", maxBytes=1234567, backupCount=5
        )
