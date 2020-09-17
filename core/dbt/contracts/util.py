import dataclasses
from datetime import datetime
from typing import (
    List, Tuple, ClassVar, Type, TypeVar, Dict, Any
)

from dbt.clients.system import write_json, read_json
from dbt.exceptions import (
    IncompatibleSchemaException,
    InternalException,
    RuntimeException,
)
from dbt.version import __version__
from hologram import JsonSchemaMixin

MacroKey = Tuple[str, str]
SourceKey = Tuple[str, str]


def list_str() -> List[str]:
    """Mypy gets upset about stuff like:

    from dataclasses import dataclass, field
    from typing import Optional, List

    @dataclass
    class Foo:
        x: Optional[List[str]] = field(default_factory=list)


    Because `list` could be any kind of list, I guess
    """
    return []


class Replaceable:
    def replace(self, **kwargs):
        return dataclasses.replace(self, **kwargs)


class Mergeable(Replaceable):
    def merged(self, *args):
        """Perform a shallow merge, where the last non-None write wins. This is
        intended to merge dataclasses that are a collection of optional values.
        """
        replacements = {}
        cls = type(self)
        for arg in args:
            for field in dataclasses.fields(cls):
                value = getattr(arg, field.name)
                if value is not None:
                    replacements[field.name] = value

        return self.replace(**replacements)


class Writable:
    def write(self, path: str, omit_none: bool = False):
        write_json(path, self.to_dict(omit_none=omit_none))  # type: ignore


class AdditionalPropertiesMixin:
    """Make this class an extensible property.

    The underlying class definition must include a type definition for a field
    named '_extra' that is of type `Dict[str, Any]`.
    """
    ADDITIONAL_PROPERTIES = True

    @classmethod
    def from_dict(cls, data, validate=True):
        self = super().from_dict(data=data, validate=validate)
        keys = self.to_dict(validate=False, omit_none=False)
        for key, value in data.items():
            if key not in keys:
                self.extra[key] = value
        return self

    def to_dict(self, omit_none=True, validate=False):
        data = super().to_dict(omit_none=omit_none, validate=validate)
        data.update(self.extra)
        return data

    def replace(self, **kwargs):
        dct = self.to_dict(omit_none=False, validate=False)
        dct.update(kwargs)
        return self.from_dict(dct)

    @property
    def extra(self):
        return self._extra


class Readable:
    @classmethod
    def read(cls, path: str):
        try:
            data = read_json(path)
        except (EnvironmentError, ValueError) as exc:
            raise RuntimeException(
                f'Could not read {cls.__name__} at "{path}" as JSON: {exc}'
            ) from exc

        return cls.from_dict(data)  # type: ignore


BASE_SCHEMAS_URL = 'https://schemas.getdbt.com/dbt/{name}/v{version}.json'


@dataclasses.dataclass
class SchemaVersion:
    name: str
    version: int

    def __str__(self) -> str:
        return BASE_SCHEMAS_URL.format(
            name=self.name,
            version=self.version,
        )


SCHEMA_VERSION_KEY = 'dbt_schema_version'


@dataclasses.dataclass
class BaseArtifactMetadata(JsonSchemaMixin):
    dbt_schema_version: str
    dbt_version: str = __version__
    generated_at: datetime = dataclasses.field(
        default_factory=datetime.utcnow
    )


def schema_version(name: str, version: int):
    def inner(cls: Type[VersionedSchema]):
        cls.dbt_schema_version = SchemaVersion(
            name=name,
            version=version,
        )
        return cls
    return inner


@dataclasses.dataclass
class VersionedSchema(JsonSchemaMixin):
    dbt_schema_version: ClassVar[SchemaVersion]

    @classmethod
    def json_schema(cls, embeddable: bool = False) -> Dict[str, Any]:
        result = super().json_schema(embeddable=embeddable)
        if not embeddable:
            result['$id'] = str(cls.dbt_schema_version)
        return result


T = TypeVar('T', bound='ArtifactMixin')


# metadata should really be a Generic[T_M] where T_M is a TypeVar bound to
# BaseArtifactMetadata. Unfortunately this isn't possible due to a mypy issue:
# https://github.com/python/mypy/issues/7520
@dataclasses.dataclass(init=False)
class ArtifactMixin(VersionedSchema, Writable, Readable):
    metadata: BaseArtifactMetadata

    @classmethod
    def from_dict(
        cls: Type[T], data: Dict[str, Any], validate: bool = True
    ) -> T:
        if cls.dbt_schema_version is None:
            raise InternalException(
                'Cannot call from_dict with no schema version!'
            )

        if validate:
            expected = str(cls.dbt_schema_version)
            found = data.get('metadata', {}).get(SCHEMA_VERSION_KEY)
            if found != expected:
                raise IncompatibleSchemaException(expected, found)

        return super().from_dict(data=data, validate=validate)
