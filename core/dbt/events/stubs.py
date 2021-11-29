from typing import (
    Any,
    NamedTuple,
    Optional,
)

# N.B.:
# These stubs were autogenerated by stubgen and then hacked
# to pieces to ensure we had something other than "Any" types
# where using external classes to instantiate event subclasses
# in events/types.py.
#
# This goes away when we turn mypy on for everything.
#
# Don't trust them too much at all!


class _ReferenceKey(NamedTuple):
    database: Any
    schema: Any
    identifier: Any


class _CachedRelation:
    referenced_by: Any
    inner: Any


class BaseRelation:
    path: Any
    type: Optional[Any]
    quote_character: str
    include_policy: Any
    quote_policy: Any
    dbt_created: bool


class InformationSchema(BaseRelation):
    information_schema_view: Optional[str]
