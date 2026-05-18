from __future__ import annotations

from pydantic import BaseModel


class ModelInput(BaseModel):
    """A single input field parsed from a Replicate model's OpenAPI schema."""
    name: str
    type: str  # "string", "number", "integer", "boolean"
    default: str | float | int | bool | None = None
    description: str = ""
    minimum: float | None = None
    maximum: float | None = None
    enum: list[str] | None = None
    sweepable: bool = True
    order: int = 0


class SweepAxis(BaseModel):
    """Which input is being swept and with what values."""
    input_name: str
    values: list[str | float | int | bool]
    labels: list[str]


class SweepRun(BaseModel):
    """Mirrors a sweep_runs row."""
    id: int
    model_slug: str
    fixed_inputs: dict
    axis_config: SweepAxis
    created_at: str


class Generation(BaseModel):
    """Mirrors a generations row."""
    id: int
    sweep_run_id: int
    inputs: dict
    axis_position: int
    label: str
    status: str = "pending"
    output_url: str | None = None
    error: str | None = None
    generation_ms: int | None = None
    created_at: str
