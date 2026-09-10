"""Integration tests for SyntheticForge Web Studio FastAPI app."""

import httpx
import pytest

from syntheticforge.studio.app import create_studio_app


@pytest.mark.asyncio
async def test_studio_api_endpoints() -> None:
    app = create_studio_app("schemas/e-commerce-flow.yaml")

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        # 1. Test HTML UI
        ui_resp = await client.get("/")
        assert ui_resp.status_code == 200
        assert "SyntheticForge" in ui_resp.text
        assert "e-commerce-flow" in ui_resp.text

        # 2. Test /api/schema
        schema_resp = await client.get("/api/schema")
        assert schema_resp.status_code == 200
        data = schema_resp.json()
        assert data["name"] == "e-commerce-flow"
        assert "customers" in data["entities"]
        assert "orders" in data["entities"]

        # 3. Test /api/dag
        dag_resp = await client.get("/api/dag")
        assert dag_resp.status_code == 200
        dag = dag_resp.json()
        node_ids = {n["id"] for n in dag["nodes"]}
        assert "customers" in node_ids
        assert "orders" in node_ids
        assert len(dag["edges"]) > 0

        # 4. Test /api/preview/customers
        preview_resp = await client.get("/api/preview/customers?count=3")
        assert preview_resp.status_code == 200
        records = preview_resp.json()
        assert len(records) == 3
        assert "id" in records[0]

        # 5. Test /api/lifecycle/orders
        lc_resp = await client.get("/api/lifecycle/orders")
        assert lc_resp.status_code == 200
        lc = lc_resp.json()
        assert lc["has_lifecycle"] is True
        assert lc["initial_state"] == "CREATED"
