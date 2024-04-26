from copy import deepcopy
import pytest
from typing import List

from dbt.artifacts.resources import Dimension, Entity, Measure, Defaults
from dbt.contracts.graph.nodes import SemanticModel
from dbt.artifacts.resources.v1.semantic_model import NodeRelation
from dbt.node_types import NodeType
from dbt_semantic_interfaces.references import MeasureReference
from dbt_semantic_interfaces.type_enums import AggregationType, DimensionType, EntityType


class TestSemanticModel:
    @pytest.fixture(scope="function")
    def dimensions(self) -> List[Dimension]:
        return [Dimension(name="ds", type=DimensionType)]

    @pytest.fixture(scope="function")
    def entities(self) -> List[Entity]:
        return [Entity(name="test_entity", type=EntityType.PRIMARY, expr="id")]

    @pytest.fixture(scope="function")
    def measures(self) -> List[Measure]:
        return [Measure(name="test_measure", agg=AggregationType.COUNT, expr="id")]

    @pytest.fixture(scope="function")
    def default_semantic_model(
        self, dimensions: List[Dimension], entities: List[Entity], measures: List[Measure]
    ) -> SemanticModel:
        return SemanticModel(
            name="test_semantic_model",
            resource_type=NodeType.SemanticModel,
            model="ref('test_model')",
            package_name="test",
            path="test_path",
            original_file_path="test_fixture",
            unique_id=f"{NodeType.SemanticModel}.test.test_semantic_model",
            fqn=[],
            defaults=Defaults(agg_time_dimension="ds"),
            dimensions=dimensions,
            entities=entities,
            measures=measures,
            node_relation=NodeRelation(
                alias="test_alias", schema_name="test_schema", database="test_database"
            ),
        )

    def test_checked_agg_time_dimension_for_measure_via_defaults(
        self,
        default_semantic_model: SemanticModel,
    ):
        assert default_semantic_model.defaults.agg_time_dimension is not None
        measure = default_semantic_model.measures[0]
        measure.agg_time_dimension = None
        default_semantic_model.checked_agg_time_dimension_for_measure(
            MeasureReference(element_name=measure.name)
        )

    def test_checked_agg_time_dimension_for_measure_via_measure(
        self, default_semantic_model: SemanticModel
    ):
        default_semantic_model.defaults = None
        measure = default_semantic_model.measures[0]
        measure.agg_time_dimension = default_semantic_model.dimensions[0].name
        default_semantic_model.checked_agg_time_dimension_for_measure(
            MeasureReference(element_name=measure.name)
        )

    def test_checked_agg_time_dimension_for_measure_exception(
        self, default_semantic_model: SemanticModel
    ):
        default_semantic_model.defaults = None
        measure = default_semantic_model.measures[0]
        measure.agg_time_dimension = None

        with pytest.raises(AssertionError) as execinfo:
            default_semantic_model.checked_agg_time_dimension_for_measure(
                MeasureReference(measure.name)
            )

        assert (
            f"Aggregation time dimension for measure {measure.name} on semantic model {default_semantic_model.name}"
            in str(execinfo.value)
        )

    def test_semantic_model_same_contents(self, default_semantic_model: SemanticModel):
        default_semantic_model_copy = deepcopy(default_semantic_model)

        assert default_semantic_model.same_contents(default_semantic_model_copy)

    def test_semantic_model_same_contents_update_model(
        self, default_semantic_model: SemanticModel
    ):
        default_semantic_model_copy = deepcopy(default_semantic_model)
        default_semantic_model_copy.model = "ref('test_another_model')"

        assert not default_semantic_model.same_contents(default_semantic_model_copy)

    def test_semantic_model_same_contents_different_node_relation(
        self,
        default_semantic_model: SemanticModel,
    ):
        default_semantic_model_copy = deepcopy(default_semantic_model)
        default_semantic_model_copy.node_relation.alias = "test_another_alias"
        # Relation should not be consided in same_contents
        assert default_semantic_model.same_contents(default_semantic_model_copy)
