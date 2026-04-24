"""Scenario IO models (pydantic v2)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field, field_validator, model_validator


class Weights(BaseModel):
    water: float
    food: float
    energy: float

    @field_validator("water", "food", "energy")
    @classmethod
    def _nonneg(cls, v):
        if v < 0:
            raise ValueError("weights must be non-negative")
        return v

    @model_validator(mode="after")
    def _sum_one(self):
        s = self.water + self.food + self.energy
        if abs(s - 1.0) > 1e-6:
            raise ValueError(f"weights must sum to 1.0 (got {s})")
        return self


class ReservoirPolicy(BaseModel):
    mode: str = "historical"
    release_m3s_by_month: dict[str, float] = Field(default_factory=dict)


class DemandPolicy(BaseModel):
    area_scale: float = 1.0
    population_scale: float = 1.0


class Constraints(BaseModel):
    min_delta_flow_m3s: float = 0.0


class Policy(BaseModel):
    reservoirs: dict[str, ReservoirPolicy] = Field(default_factory=dict)
    demands: dict[str, DemandPolicy] = Field(default_factory=dict)
    constraints: Constraints = Field(default_factory=Constraints)
    weights: Weights


class ScenarioResults(BaseModel):
    timeseries_per_node: dict[str, list[dict]] = Field(default_factory=dict)
    kpi_monthly: list[dict] = Field(default_factory=list)
    score: float | None = None
    score_breakdown: dict[str, float] = Field(default_factory=dict)


class Scenario(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    period: list[str]
    policy: Policy
    results: ScenarioResults | None = None

    @classmethod
    def from_file(cls, path: Path | str) -> "Scenario":
        return cls.model_validate_json(Path(path).read_text())

    def to_file(self, path: Path | str) -> None:
        Path(path).write_text(self.model_dump_json(indent=2))
