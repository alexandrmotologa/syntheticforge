"""Unit tests for FieldGenerator data types and constraints."""

from datetime import datetime, timezone
import re
from syntheticforge.config import FieldConfig, FieldType
from syntheticforge.generator.field_generators import FieldGenerator


def test_uuid_and_ulid_generation() -> None:
    fg = FieldGenerator(seed=42)
    uuid_cfg = FieldConfig(type=FieldType.UUID)
    ulid_cfg = FieldConfig(type=FieldType.ULID)

    val_uuid = fg.generate("id", uuid_cfg)
    assert len(val_uuid) == 36
    assert re.match(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", val_uuid)

    val_ulid = fg.generate("id", ulid_cfg)
    assert len(val_ulid) == 26


def test_integer_and_sequence_generation() -> None:
    fg = FieldGenerator(seed=42)
    int_cfg = FieldConfig(type=FieldType.INTEGER, min=10, max=20)
    for _ in range(50):
        val = fg.generate("age", int_cfg)
        assert 10 <= val <= 20

    seq_cfg = FieldConfig(type=FieldType.SEQUENCE, start=100, step=5)
    assert fg.generate("seq", seq_cfg) == 100
    assert fg.generate("seq", seq_cfg) == 105
    assert fg.generate("seq", seq_cfg) == 110


def test_decimal_and_precision() -> None:
    fg = FieldGenerator(seed=42)
    dec_cfg = FieldConfig(type=FieldType.DECIMAL, min=5.0, max=15.0, precision=2)
    val = fg.generate("amount", dec_cfg)
    assert 5.0 <= val <= 15.0
    assert len(str(val).split(".")[1]) <= 2


def test_luhn_credit_card_validity() -> None:
    fg = FieldGenerator(seed=123)
    card_cfg = FieldConfig(type=FieldType.CREDIT_CARD)

    for _ in range(25):
        card = fg.generate("card_num", card_cfg)
        assert len(card) == 16
        # Validate Luhn algorithm
        digits = [int(d) for d in card]
        checksum = 0
        for i, d in enumerate(reversed(digits)):
            if i % 2 == 1:
                doubled = d * 2
                checksum += doubled - 9 if doubled > 9 else doubled
            else:
                checksum += d
        assert checksum % 10 == 0


def test_enum_distribution() -> None:
    fg = FieldGenerator(seed=42)
    enum_cfg = FieldConfig(
        type=FieldType.ENUM,
        values=["RED", "GREEN", "BLUE"],
        weights=[0.8, 0.15, 0.05],
    )
    results = [fg.generate("color", enum_cfg) for _ in range(200)]
    assert results.count("RED") > results.count("GREEN")
    assert results.count("GREEN") > results.count("BLUE")


def test_regex_generation() -> None:
    fg = FieldGenerator(seed=42)
    regex_cfg = FieldConfig(type=FieldType.REGEX, pattern="[A-Z]{2}[0-9]{4}")
    for _ in range(20):
        val = fg.generate("code", regex_cfg)
        assert re.match(r"^[A-Z]{2}[0-9]{4}$", val)


def test_template_interpolation() -> None:
    fg = FieldGenerator(seed=42)
    tpl_cfg = FieldConfig(type=FieldType.TEMPLATE, format="USER-{country}-{code}")
    record = {"country": "RO", "code": "42"}
    val = fg.generate("user_code", tpl_cfg, current_record=record)
    assert val == "USER-RO-42"
