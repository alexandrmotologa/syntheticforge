"""Unit tests verifying referential integrity in EntityGenerator."""

from syntheticforge.config import load_config
from syntheticforge.generator.entity_generator import EntityGenerator


def test_referential_integrity_between_customers_and_orders() -> None:
    schema_yaml = """
    version: "1.0"
    name: "integrity-test"
    entities:
      customers:
        count: 50
        primary_key: "id"
        fields:
          id: { type: "uuid" }
          name: { type: "name" }
          email: { type: "email" }

      orders:
        count: 200
        primary_key: "id"
        depends_on: ["customers"]
        foreign_keys:
          customer_id:
            entity: "customers"
            field: "id"
            distribution: "pareto"
        fields:
          id: { type: "uuid" }
          amount: { type: "decimal", min: 10.0, max: 500.0, precision: 2 }

      payments:
        count: 180
        primary_key: "id"
        depends_on: ["orders"]
        foreign_keys:
          order_id:
            entity: "orders"
            field: "id"
            distribution: "uniform"
        fields:
          id: { type: "uuid" }
          card: { type: "credit_card" }
    """
    config = load_config(schema_yaml)
    generator = EntityGenerator(config, seed=42)

    dataset = generator.generate_all()

    customers = dataset["customers"]
    orders = dataset["orders"]
    payments = dataset["payments"]

    assert len(customers) == 50
    assert len(orders) == 200
    assert len(payments) == 180

    customer_ids = {c["id"] for c in customers}
    order_ids = {o["id"] for o in orders}

    # 1. Verify 100% of orders reference a valid customer ID
    for order in orders:
        assert "customer_id" in order
        assert order["customer_id"] in customer_ids, (
            f"Order {order['id']} references unknown customer {order['customer_id']}"
        )

    # 2. Verify 100% of payments reference a valid order ID
    for payment in payments:
        assert "order_id" in payment
        assert payment["order_id"] in order_ids, (
            f"Payment {payment['id']} references unknown order {payment['order_id']}"
        )


def test_e_commerce_schema_full_generation() -> None:
    config = load_config("schemas/e-commerce-flow.yaml")
    # Reduce count for fast unit test
    config.entities["customers"].count = 20
    config.entities["orders"].count = 50
    config.entities["payments"].count = 45
    config.entities["shipments"].count = 40

    generator = EntityGenerator(config, seed=100)
    data = generator.generate_all()

    cust_ids = {c["id"] for c in data["customers"]}
    order_ids = {o["id"] for o in data["orders"]}

    for o in data["orders"]:
        assert o["customer_id"] in cust_ids

    for p in data["payments"]:
        assert p["order_id"] in order_ids

    for s in data["shipments"]:
        assert s["order_id"] in order_ids
