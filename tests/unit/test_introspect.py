"""Unit tests for SchemaIntrospector."""

import pytest
from syntheticforge.inspector.introspect import SchemaIntrospector


@pytest.mark.asyncio
async def test_introspector_mock_and_yaml_export() -> None:
    mock_schema = {
        "version": "1.0",
        "name": "mock-db",
        "entities": {
            "users": {
                "count": 500,
                "primary_key": "id",
                "fields": {
                    "id": {"type": "uuid"},
                    "email": {"type": "email"},
                },
            }
        },
    }

    introspector = SchemaIntrospector("postgresql://test:test@localhost:5432/test", mock_data=mock_schema)
    result = await introspector.introspect()

    assert result["name"] == "mock-db"
    assert "users" in result["entities"]

    yaml_str = introspector.to_yaml(result)
    assert "version: '1.0'" in yaml_str or 'version: "1.0"' in yaml_str
    assert "users:" in yaml_str
