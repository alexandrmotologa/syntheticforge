"""Configuration models and YAML schema parser for SyntheticForge."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class FieldType(str, Enum):
    UUID = "uuid"
    ULID = "ulid"
    INTEGER = "integer"
    SEQUENCE = "sequence"
    DECIMAL = "decimal"
    NAME = "name"
    EMAIL = "email"
    CREDIT_CARD = "credit_card"
    TIMESTAMP = "timestamp"
    ENUM = "enum"
    REGEX = "regex"
    TEMPLATE = "template"


class SamplingDistribution(str, Enum):
    UNIFORM = "uniform"
    PARETO = "pareto"
    ZIPFIAN = "zipfian"
    GAUSSIAN = "gaussian"
    RECENT_WEIGHTED = "recent_weighted"


class DelayDistribution(str, Enum):
    CONSTANT = "constant"
    UNIFORM = "uniform"
    EXPONENTIAL = "exponential"
    NORMAL = "normal"


class FieldConfig(BaseModel):
    type: FieldType
    min: float | None = None
    max: float | None = None
    precision: int = 2
    start: int = 1
    step: int = 1
    past_days: int = 30
    future_days: int = 0
    values: list[Any] = Field(default_factory=list)
    weights: list[float] = Field(default_factory=list)
    pattern: str | None = None
    format: str | None = None
    domain: str | None = None
    nullable: bool = False
    null_probability: float = 0.0

    @model_validator(mode="after")
    def validate_field_params(self) -> FieldConfig:
        if self.type == FieldType.ENUM:
            if not self.values:
                raise ValueError("Enum field requires non-empty 'values' list.")
            if self.weights and len(self.weights) != len(self.values):
                raise ValueError("Enum 'weights' length must match 'values' length.")
        if self.type == FieldType.REGEX and not self.pattern:
            raise ValueError("Regex field requires a 'pattern'.")
        if self.type == FieldType.TEMPLATE and not self.format:
            raise ValueError("Template field requires a 'format' string.")
        return self


class ForeignKeyConfig(BaseModel):
    entity: str
    field: str = "id"
    distribution: SamplingDistribution = SamplingDistribution.UNIFORM
    pareto_alpha: float = 1.16  # Approx 80/20 rule
    zipf_alpha: float = 1.0
    self_referential: bool = False
    deferred: bool = False
    root_null_ratio: float = 0.1


class TransitionConfig(BaseModel):
    from_state: str = Field(alias="from")
    to_state: str = Field(alias="to")
    probability: float = 1.0
    delay_seconds: float = 0.0
    delay_distribution: DelayDistribution = DelayDistribution.CONSTANT
    delay_min: float | None = None
    delay_max: float | None = None
    delay_std: float | None = None

    model_config = ConfigDict(populate_by_name=True)


class LifecycleConfig(BaseModel):
    initial_state: str
    states: list[str]
    transitions: list[TransitionConfig] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_lifecycle(self) -> LifecycleConfig:
        if self.initial_state not in self.states:
            raise ValueError(
                f"initial_state '{self.initial_state}' must be in states {self.states}"
            )
        for t in self.transitions:
            if t.from_state not in self.states:
                raise ValueError(f"Transition from '{t.from_state}' is not in states {self.states}")
            if t.to_state not in self.states:
                raise ValueError(f"Transition to '{t.to_state}' is not in states {self.states}")
        return self


class EntityConfig(BaseModel):
    count: int = Field(default=100, ge=1)
    primary_key: str = "id"
    depends_on: list[str] = Field(default_factory=list)
    foreign_keys: dict[str, ForeignKeyConfig] = Field(default_factory=dict)
    fields: dict[str, FieldConfig] = Field(default_factory=dict)
    lifecycle: LifecycleConfig | None = None

    @model_validator(mode="after")
    def sync_dependencies_from_foreign_keys(self) -> EntityConfig:
        for fk in self.foreign_keys.values():
            if fk.self_referential or fk.deferred:
                continue
            if fk.entity not in self.depends_on:
                self.depends_on.append(fk.entity)
        return self


class AnomalyConfig(BaseModel):
    duplicate_key_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    schema_mutation_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    payload_corruption_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    null_injection_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    out_of_order_rate: float = Field(default=0.0, ge=0.0, le=1.0)


class SchemaEvolutionConfig(BaseModel):
    trigger_event_count: int | None = None
    trigger_seconds: float | None = None
    target_version: str = "2.0"
    add_fields: dict[str, FieldConfig] = Field(default_factory=dict)
    remove_fields: list[str] = Field(default_factory=list)
    rename_fields: dict[str, str] = Field(default_factory=dict)


class ForgeConfig(BaseModel):
    version: str = "1.0"
    name: str = "syntheticforge-spec"
    description: str | None = None
    entities: dict[str, EntityConfig]
    anomalies: AnomalyConfig = Field(default_factory=AnomalyConfig)
    evolutions: dict[str, list[SchemaEvolutionConfig]] = Field(default_factory=dict)

    @field_validator("entities")
    @classmethod
    def validate_entities(cls, v: dict[str, EntityConfig]) -> dict[str, EntityConfig]:
        if not v:
            raise ValueError("Schema must define at least one entity.")
        for entity_name, entity_cfg in v.items():
            for dep in entity_cfg.depends_on:
                if dep not in v:
                    raise ValueError(f"Entity '{entity_name}' depends on undefined entity '{dep}'.")
        return v


def load_config(source: str | Path | dict[str, Any]) -> ForgeConfig:
    """Load and validate a ForgeConfig from a YAML file path, raw YAML string, or dictionary."""
    if isinstance(source, dict):
        return ForgeConfig.model_validate(source)

    if isinstance(source, Path) or (isinstance(source, str) and Path(source).is_file()):
        content = Path(source).read_text(encoding="utf-8")
        parsed = yaml.safe_load(content)
        return ForgeConfig.model_validate(parsed)

    if isinstance(source, str):
        parsed = yaml.safe_load(source)
        return ForgeConfig.model_validate(parsed)

    raise TypeError(f"Unsupported source type for config: {type(source)}")
