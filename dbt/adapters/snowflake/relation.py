from dbt.adapters.default.relation import DefaultRelation
from dbt.utils import filter_null_values


class SnowflakeRelation(DefaultRelation):
    DEFAULTS = {
        'metadata': {
            '_type': 'SnowflakeRelation'
        },
        'quote_character': '"',
        'quote_policy': {
            'database': True,
            'schema': True,
            'identifier': True,
        },
        'include_policy': {
            'database': False,
            'schema': True,
            'identifier': True,
        }
    }

    SCHEMA = {
        'type': 'object',
        'properties': {
            'metadata': {
                '_type': {
                    'type': 'string',
                    'const': 'SnowflakeRelation',
                },
            },
            'type': {
                'enum': DefaultRelation.RelationTypes + [None],
            },
            'path': DefaultRelation.PATH_SCHEMA,
            'include_policy': DefaultRelation.POLICY_SCHEMA,
            'quote_policy': DefaultRelation.POLICY_SCHEMA,
            'quote_character': {'type': 'string'},
        },
        'required': ['metadata', 'type', 'path', 'include_policy',
                     'quote_policy', 'quote_character']
    }

    @classmethod
    def create_from_node(cls, profile, node, **kwargs):
        return cls.create(
            database=profile.get('database'),
            schema=node.get('schema'),
            identifier=node.get('name'),
            **kwargs)

    def get_path_part(self, part):
        return self.path.get(part)
