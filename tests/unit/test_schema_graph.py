"""Unit tests for SchemaGraph topological sorting and cycle detection."""

import pytest

from syntheticforge.config import ForgeConfig, load_config
from syntheticforge.graph.schema_graph import CircularDependencyError, SchemaGraph


def test_linear_dependency_topological_sort() -> None:
    raw_schema = """
    version: "1.0"
    name: "linear-test"
    entities:
      customers:
        count: 10
        fields:
          id: { type: "uuid" }
      orders:
        count: 20
        depends_on: ["customers"]
        foreign_keys:
          customer_id: { entity: "customers", field: "id" }
        fields:
          id: { type: "uuid" }
      payments:
        count: 20
        depends_on: ["orders"]
        foreign_keys:
          order_id: { entity: "orders", field: "id" }
        fields:
          id: { type: "uuid" }
    """
    config = load_config(raw_schema)
    graph = SchemaGraph(config)

    order = graph.topological_order()
    assert order == ["customers", "orders", "payments"]

    stages = graph.generation_stages()
    assert stages == [["customers"], ["orders"], ["payments"]]
    assert graph.get_parents("orders") == ["customers"]
    assert graph.get_children("orders") == ["payments"]


def test_branching_dependency_dag() -> None:
    raw_schema = """
    version: "1.0"
    name: "branching-test"
    entities:
      users:
        count: 10
        fields:
          id: { type: "uuid" }
      posts:
        count: 30
        depends_on: ["users"]
        foreign_keys:
          author_id: { entity: "users", field: "id" }
        fields:
          id: { type: "uuid" }
      comments:
        count: 50
        depends_on: ["users", "posts"]
        foreign_keys:
          user_id: { entity: "users", field: "id" }
          post_id: { entity: "posts", field: "id" }
        fields:
          id: { type: "uuid" }
      reactions:
        count: 100
        depends_on: ["posts"]
        foreign_keys:
          post_id: { entity: "posts", field: "id" }
        fields:
          id: { type: "uuid" }
    """
    config = load_config(raw_schema)
    graph = SchemaGraph(config)

    order = graph.topological_order()
    # Users must come before posts and comments
    assert order.index("users") < order.index("posts")
    assert order.index("users") < order.index("comments")
    assert order.index("posts") < order.index("comments")
    assert order.index("posts") < order.index("reactions")

    stages = graph.generation_stages()
    assert stages[0] == ["users"]
    assert stages[1] == ["posts"]
    assert sorted(stages[2]) == ["comments", "reactions"]


def test_circular_dependency_raises_error() -> None:
    # Note: Pydantic validates depends_on existence, but cyclic check is done by SchemaGraph
    config_dict = {
        "version": "1.0",
        "name": "cyclic-test",
        "entities": {
            "entity_a": {
                "count": 10,
                "depends_on": ["entity_b"],
                "fields": {"id": {"type": "uuid"}},
            },
            "entity_b": {
                "count": 10,
                "depends_on": ["entity_a"],
                "fields": {"id": {"type": "uuid"}},
            },
        },
    }
    config = ForgeConfig.model_validate(config_dict)
    with pytest.raises(CircularDependencyError) as exc_info:
        SchemaGraph(config)

    assert "Circular dependency detected" in str(exc_info.value)
