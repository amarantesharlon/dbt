from dbt.contracts.graph.parsed import ParsedNode, ParsedMacro, \
    ParsedDocumentation
from dbt.contracts.graph.compiled import CompileResultNode
from dbt.contracts.util import Writable, Replaceable
from dbt.config import Project
from dbt.exceptions import raise_duplicate_resource_name
from dbt.node_types import NodeType
from dbt.logger import GLOBAL_LOGGER as logger
from dbt import tracking
import dbt.utils

from hologram import JsonSchemaMixin

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID


NodeEdgeMap = Dict[str, List[str]]


@dataclass
class ManifestMetadata(JsonSchemaMixin, Replaceable):
    project_id: Optional[str]
    user_id: Optional[UUID]
    send_anonymous_usage_stats: Optional[bool]


def _sort_values(dct):
    """Given a dictionary, sort each value. This makes output deterministic,
    which helps for tests.
    """
    return {k: sorted(v) for k, v in dct.items()}


def build_edges(nodes):
    """Build the forward and backward edges on the given list of ParsedNodes
    and return them as two separate dictionaries, each mapping unique IDs to
    lists of edges.
    """
    backward_edges = {}
    # pre-populate the forward edge dict for simplicity
    forward_edges = {node.unique_id: [] for node in nodes}
    for node in nodes:
        backward_edges[node.unique_id] = node.depends_on_nodes[:]
        for unique_id in node.depends_on_nodes:
            forward_edges[unique_id].append(node.unique_id)
    return _sort_values(forward_edges), _sort_values(backward_edges)


def _deepcopy(value):
    return value.from_dict(value.to_dict())


@dataclass(init=False)
class Manifest:
    """The manifest for the full graph, after parsing and during compilation.
    """
    nodes: Dict[str, CompileResultNode]
    macros: Dict[str, ParsedMacro]
    docs: Dict[str, ParsedDocumentation]
    generated_at: datetime
    disabled: List[ParsedNode]
    metadata: ManifestMetadata = field(init=False)

    def __init__(
        self,
        nodes: Dict[str, CompileResultNode],
        macros: Dict[str, ParsedMacro],
        docs: Dict[str, ParsedDocumentation],
        generated_at: datetime,
        disabled: List[ParsedNode],
        config: Optional[Project] = None
    ) -> None:
        self.metadata = self.get_metadata(config)
        self.nodes = nodes
        self.macros = macros
        self.docs = docs
        self.generated_at = generated_at
        self.disabled = disabled

    @staticmethod
    def get_metadata(config: Optional[Project]) -> ManifestMetadata:
        project_id = None
        user_id = None
        send_anonymous_usage_stats = None

        if config is not None:
            project_id = config.hashed_name()

        if tracking.active_user is not None:
            user_id = tracking.active_user.id
            send_anonymous_usage_stats = not tracking.active_user.do_not_track

        return ManifestMetadata(
            project_id=project_id,
            user_id=user_id,
            send_anonymous_usage_stats=send_anonymous_usage_stats,
        )

    def serialize(self):
        """Convert the parsed manifest to a nested dict structure that we can
        safely serialize to JSON.
        """
        forward_edges, backward_edges = build_edges(self.nodes.values())

        return {
            'nodes': {k: v.to_dict() for k, v in self.nodes.items()},
            'macros': {k: v.to_dict() for k, v in self.macros.items()},
            'docs': {k: v.to_dict() for k, v in self.docs.items()},
            'parent_map': backward_edges,
            'child_map': forward_edges,
            'generated_at': self.generated_at,
            'metadata': self.metadata,
            'disabled': [v.to_dict() for v in self.disabled],
        }

    def find_disabled_by_name(self, name, package=None):
        return dbt.utils.find_in_list_by_name(self.disabled, name, package,
                                              NodeType.refable())

    def _find_by_name(self, name, package, subgraph, nodetype):
        """

        Find a node by its given name in the appropriate sugraph. If package is
        None, all pacakges will be searched.
        nodetype should be a list of NodeTypes to accept.
        """
        if subgraph == 'nodes':
            search = self.nodes
        elif subgraph == 'macros':
            search = self.macros
        else:
            raise NotImplementedError(
                'subgraph search for {} not implemented'.format(subgraph)
            )
        return dbt.utils.find_in_subgraph_by_name(
            search,
            name,
            package,
            nodetype)

    def find_docs_by_name(self, name, package=None):
        for unique_id, doc in self.docs.items():
            parts = unique_id.split('.')
            if len(parts) != 2:
                msg = "documentation names cannot contain '.' characters"
                dbt.exceptions.raise_compiler_error(msg, doc)

            found_package, found_node = parts

            if (name == found_node and package in {None, found_package}):
                return doc
        return None

    def find_macro_by_name(self, name, package):
        """Find a macro in the graph by its name and package name, or None for
        any package.
        """
        return self._find_by_name(name, package, 'macros', [NodeType.Macro])

    def find_refable_by_name(self, name, package):
        """Find any valid target for "ref()" in the graph by its name and
        package name, or None for any package.
        """
        return self._find_by_name(name, package, 'nodes', NodeType.refable())

    def find_source_by_name(self, source_name, table_name, package):
        """Find any valid target for "source()" in the graph by its name and
        package name, or None for any package.
        """
        name = '{}.{}'.format(source_name, table_name)
        return self._find_by_name(name, package, 'nodes', [NodeType.Source])

    def get_materialization_macro(self, materialization_name,
                                  adapter_type=None):
        macro_name = dbt.utils.get_materialization_macro_name(
            materialization_name=materialization_name,
            adapter_type=adapter_type,
            with_prefix=False)

        macro = self.find_macro_by_name(
            macro_name,
            None)

        if adapter_type not in ('default', None) and macro is None:
            macro_name = dbt.utils.get_materialization_macro_name(
                materialization_name=materialization_name,
                adapter_type='default',
                with_prefix=False)
            macro = self.find_macro_by_name(
                macro_name,
                None)

        return macro

    def get_resource_fqns(self):
        resource_fqns = {}
        for unique_id, node in self.nodes.items():
            if node.resource_type == NodeType.Source:
                continue  # sources have no FQNs and can't be configured
            resource_type_plural = node.resource_type + 's'
            if resource_type_plural not in resource_fqns:
                resource_fqns[resource_type_plural] = set()
            resource_fqns[resource_type_plural].add(tuple(node.fqn))

        return resource_fqns

    def _filter_subgraph(self, subgraph, predicate):
        """
        Given a subgraph of the manifest, and a predicate, filter
        the subgraph using that predicate. Generates a list of nodes.
        """
        to_return = []

        for unique_id, item in subgraph.items():
            if predicate(item):
                to_return.append(item)

        return to_return

    def _model_matches_schema_and_table(self, schema, table, model):
        if model.resource_type == NodeType.Source:
            return (model.schema.lower() == schema.lower() and
                    model.identifier.lower() == table.lower())
        return (model.schema.lower() == schema.lower() and
                model.alias.lower() == table.lower())

    def get_unique_ids_for_schema_and_table(self, schema, table):
        """
        Given a schema and table, find matching models, and return
        their unique_ids. A schema and table may have more than one
        match if the relation matches both a source and a seed, for instance.
        """
        def predicate(model):
            return self._model_matches_schema_and_table(schema, table, model)

        matching = list(self._filter_subgraph(self.nodes, predicate))
        return [match.unique_id for match in matching]

    def add_nodes(self, new_nodes):
        """Add the given dict of new nodes to the manifest."""
        for unique_id, node in new_nodes.items():
            if unique_id in self.nodes:
                raise_duplicate_resource_name(node, self.nodes[unique_id])
            self.nodes[unique_id] = node

    def patch_nodes(self, patches):
        """Patch nodes with the given dict of patches. Note that this consumes
        the input!
        """
        # because we don't have any mapping from node _names_ to nodes, and we
        # only have the node name in the patch, we have to iterate over all the
        # nodes looking for matching names. We could use _find_by_name if we
        # were ok with doing an O(n*m) search (one nodes scan per patch)
        for node in self.nodes.values():
            if node.resource_type != NodeType.Model:
                continue
            patch = patches.pop(node.name, None)
            if not patch:
                continue
            node.patch(patch)

        # log debug-level warning about nodes we couldn't find
        if patches:
            for patch in patches.values():
                # since patches aren't nodes, we can't use the existing
                # target_not_found warning
                logger.debug((
                    'WARNING: Found documentation for model "{}" which was '
                    'not found or is disabled').format(patch.name)
                )

    def to_flat_graph(self):
        """Convert the parsed manifest to the 'flat graph' that the compiler
        expects.

        Kind of hacky note: everything in the code is happy to deal with
        macros as ParsedMacro objects (in fact, it's been changed to require
        that), so those can just be returned without any work. Nodes sadly
        require a lot of work on the compiler side.

        Ideally in the future we won't need to have this method.
        """
        return {
            'nodes': {
                k: v.to_dict(omit_none=False)
                for k, v in self.nodes.items()
            },
            'macros': self.macros,
        }

    def __getattr__(self, name):
        raise AttributeError("'{}' object has no attribute '{}'".format(
            type(self).__name__, name)
        )

    def get_used_schemas(self, resource_types=None):
        return frozenset({
            (node.database, node.schema)
            for node in self.nodes.values()
            if not resource_types or node.resource_type in resource_types
        })

    def get_used_databases(self):
        return frozenset(node.database for node in self.nodes.values())

    def deepcopy(self, config=None):
        return Manifest(
            nodes={k: _deepcopy(v) for k, v in self.nodes.items()},
            macros={k: _deepcopy(v) for k, v in self.macros.items()},
            docs={k: _deepcopy(v) for k, v in self.docs.items()},
            generated_at=self.generated_at,
            disabled=[_deepcopy(n) for n in self.disabled],
            config=config
        )

    def writable_manifest(self):
        forward_edges, backward_edges = build_edges(self.nodes.values())
        return WritableManifest(
            nodes=self.nodes,
            macros=self.macros,
            docs=self.docs,
            generated_at=self.generated_at,
            metadata=self.metadata,
            disabled=self.disabled,
            child_map=forward_edges,
            parent_map=backward_edges
        )

    @classmethod
    def from_writable_manifest(cls, writable):
        self = cls(
            nodes=writable.nodes,
            macros=writable.macros,
            docs=writable.docs,
            generated_at=writable.generated_at,
            metadata=writable.metadata,
            disabled=writable.disabled,
        )
        self.metadata = writable.metadata
        return self

    @classmethod
    def from_dict(cls, data, validate=True):
        writable = WritableManifest.from_dict(data=data, validate=validate)
        return cls.from_writable_manifest(writable)

    def to_dict(self, omit_none=True, validate=False):
        return self.writable_manifest().to_dict(
            omit_none=omit_none, validate=validate
        )

    def write(self, path):
        self.writable_manifest().write(path)


@dataclass
class WritableManifest(JsonSchemaMixin, Writable):
    nodes: Dict[str, CompileResultNode]
    macros: Dict[str, ParsedMacro]
    docs: Dict[str, ParsedDocumentation]
    disabled: Optional[List[ParsedNode]]
    generated_at: datetime
    parent_map: Optional[NodeEdgeMap]
    child_map: Optional[NodeEdgeMap]
    metadata: ManifestMetadata
