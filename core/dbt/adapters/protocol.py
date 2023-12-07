from dataclasses import dataclass
from typing import Type, Hashable, Optional, ContextManager, List, Generic, TypeVar, Tuple, Any
from typing_extensions import Protocol

import agate

from dbt.adapters.contracts.connection import Connection, AdapterRequiredConfig, AdapterResponse
from dbt.adapters.contracts.relation import Policy, HasQuoting, RelationConfig
from dbt.common.contracts.config.base import BaseConfig
from dbt.contracts.graph.manifest import Manifest


@dataclass
class AdapterConfig(BaseConfig):
    pass


class ConnectionManagerProtocol(Protocol):
    TYPE: str


class ColumnProtocol(Protocol):
    pass


Self = TypeVar("Self", bound="RelationProtocol")


class RelationProtocol(Protocol):
    @classmethod
    def get_default_quote_policy(cls) -> Policy:
        ...

    @classmethod
    def create_from(
        cls: Type[Self], quoting: HasQuoting, relation_config: RelationConfig, **kwargs: Any
    ) -> Self:
        ...


AdapterConfig_T = TypeVar("AdapterConfig_T", bound=AdapterConfig)
ConnectionManager_T = TypeVar("ConnectionManager_T", bound=ConnectionManagerProtocol)
Relation_T = TypeVar("Relation_T", bound=RelationProtocol)
Column_T = TypeVar("Column_T", bound=ColumnProtocol)


# TODO CT-211
class AdapterProtocol(  # type: ignore[misc]
    Protocol,
    Generic[
        AdapterConfig_T,
        ConnectionManager_T,
        Relation_T,
        Column_T,
    ],
):
    # N.B. Technically these are ClassVars, but mypy doesn't support putting type vars in a
    # ClassVar due to the restrictiveness of PEP-526
    # See: https://github.com/python/mypy/issues/5144
    AdapterSpecificConfigs: Type[AdapterConfig_T]
    Column: Type[Column_T]
    Relation: Type[Relation_T]
    ConnectionManager: Type[ConnectionManager_T]
    connections: ConnectionManager_T

    def __init__(self, config: AdapterRequiredConfig) -> None:
        ...

    @classmethod
    def type(cls) -> str:
        pass

    def set_query_header(self, manifest: Manifest) -> None:
        ...

    @staticmethod
    def get_thread_identifier() -> Hashable:
        ...

    def get_thread_connection(self) -> Connection:
        ...

    def set_thread_connection(self, conn: Connection) -> None:
        ...

    def get_if_exists(self) -> Optional[Connection]:
        ...

    def clear_thread_connection(self) -> None:
        ...

    def clear_transaction(self) -> None:
        ...

    def exception_handler(self, sql: str) -> ContextManager:
        ...

    def set_connection_name(self, name: Optional[str] = None) -> Connection:
        ...

    def cancel_open(self) -> Optional[List[str]]:
        ...

    def open(cls, connection: Connection) -> Connection:
        ...

    def release(self) -> None:
        ...

    def cleanup_all(self) -> None:
        ...

    def begin(self) -> None:
        ...

    def commit(self) -> None:
        ...

    def close(cls, connection: Connection) -> Connection:
        ...

    def commit_if_has_connection(self) -> None:
        ...

    def execute(
        self, sql: str, auto_begin: bool = False, fetch: bool = False
    ) -> Tuple[AdapterResponse, agate.Table]:
        ...
