"""Unit tests for DuckDB RelationalVerifier."""

from syntheticforge.config import load_config
from syntheticforge.generator.entity_generator import EntityGenerator
from syntheticforge.inspector.verifier import RelationalVerifier


def test_duckdb_verifier_with_valid_dataset() -> None:
    schema_yaml = """
    version: "1.0"
    name: "verifier-test"
    entities:
      departments:
        count: 5
        primary_key: "id"
        fields:
          id: { type: "uuid" }
          name: { type: "name" }

      employees:
        count: 30
        primary_key: "id"
        depends_on: ["departments"]
        foreign_keys:
          dept_id:
            entity: "departments"
            field: "id"
            distribution: "uniform"
        fields:
          id: { type: "uuid" }
          name: { type: "name" }
    """
    config = load_config(schema_yaml)
    generator = EntityGenerator(config, seed=42)
    dataset = generator.generate_all()

    verifier = RelationalVerifier(config)
    report = verifier.verify_dataset(dataset)

    assert report.passed is True
    assert report.total_records == 35
    assert len(report.orphan_fks) == 0
    assert len(report.violations) == 0


def test_duckdb_verifier_detects_orphan_foreign_keys() -> None:
    schema_yaml = """
    version: "1.0"
    name: "orphan-test"
    entities:
      parents:
        count: 2
        primary_key: "id"
        fields:
          id: { type: "uuid" }

      children:
        count: 2
        primary_key: "id"
        depends_on: ["parents"]
        foreign_keys:
          parent_id:
            entity: "parents"
            field: "id"
        fields:
          id: { type: "uuid" }
    """
    config = load_config(schema_yaml)
    # Deliberately craft an orphan foreign key
    corrupt_dataset = {
        "parents": [{"id": "parent_1"}, {"id": "parent_2"}],
        "children": [
            {"id": "child_1", "parent_id": "parent_1"},
            {"id": "child_2", "parent_id": "UNKNOWN_PARENT_ID_999"},
        ],
    }

    verifier = RelationalVerifier(config)
    report = verifier.verify_dataset(corrupt_dataset)

    assert report.passed is False
    assert len(report.orphan_fks) > 0
    assert any(
        "UNKNOWN_PARENT_ID_999" in str(report.violations) or "orphan" in v
        for v in report.violations
    )
