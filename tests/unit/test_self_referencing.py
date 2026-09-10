"""Unit tests for self-referential hierarchies and deferred bidirectional foreign keys."""

from syntheticforge.config import load_config
from syntheticforge.generator.entity_generator import EntityGenerator
from syntheticforge.inspector.verifier import RelationalVerifier


def test_self_referencing_organization_hierarchy() -> None:
    schema_yaml = """
    version: "1.0"
    name: "org-chart"
    entities:
      employees:
        count: 50
        primary_key: "id"
        foreign_keys:
          manager_id:
            entity: "employees"
            field: "id"
            self_referential: true
            root_null_ratio: 0.1
        fields:
          id: { type: "uuid" }
          name: { type: "name" }
    """
    config = load_config(schema_yaml)
    generator = EntityGenerator(config, seed=42)
    dataset = generator.generate_all()

    employees = dataset["employees"]
    assert len(employees) == 50

    emp_ids = {e["id"] for e in employees}
    managers = [e["manager_id"] for e in employees]

    # At least some employees must be top-level managers with None
    assert None in managers
    # Non-root employees must reference an existing employee ID
    non_root_managers = [m for m in managers if m is not None]
    assert len(non_root_managers) > 0
    for m in non_root_managers:
        assert m in emp_ids


def test_deferred_bidirectional_foreign_keys() -> None:
    schema_yaml = """
    version: "1.0"
    name: "bidirectional-test"
    entities:
      users:
        count: 20
        primary_key: "id"
        foreign_keys:
          active_account_id:
            entity: "accounts"
            field: "id"
            deferred: true
        fields:
          id: { type: "uuid" }
          name: { type: "name" }

      accounts:
        count: 20
        primary_key: "id"
        depends_on: ["users"]
        foreign_keys:
          user_id:
            entity: "users"
            field: "id"
        fields:
          id: { type: "uuid" }
    """
    config = load_config(schema_yaml)
    generator = EntityGenerator(config, seed=42)
    dataset = generator.generate_all()

    users = dataset["users"]
    accounts = dataset["accounts"]

    user_ids = {u["id"] for u in users}
    account_ids = {a["id"] for a in accounts}

    # After reconciliation, all users should have a valid active_account_id
    for u in users:
        assert u["active_account_id"] in account_ids

    # All accounts should reference a valid user_id
    for a in accounts:
        assert a["user_id"] in user_ids

    # Verify with DuckDB RelationalVerifier
    verifier = RelationalVerifier(config)
    report = verifier.verify_dataset(dataset)
    assert report.passed is True
