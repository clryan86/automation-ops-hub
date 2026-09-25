from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class WorkflowCreate(BaseModel):
    name: str = Field(min_length=3, max_length=160)
    description: str = ""
    steps: list[dict[str, Any]] = Field(min_length=1)


class WorkflowResponse(BaseModel):
    id: int
    name: str
    description: str
    enabled: bool
    webhook_token: str
    steps: list[dict[str, Any]]
    created_at: datetime


class RunRequest(BaseModel):
    payload: dict[str, Any] = {}


class StepRunResponse(BaseModel):
    position: int
    step_name: str
    action: str
    status: str
    attempts: int
    output: dict[str, Any] | None
    error: str | None
    duration_ms: float | None


class RunResponse(BaseModel):
    id: int
    workflow_id: int
    trigger_type: str
    status: str
    input: dict[str, Any]
    output: dict[str, Any] | None
    error: str | None
    duration_ms: float | None
    created_at: datetime
    finished_at: datetime | None
    steps: list[StepRunResponse]


class ScheduleCreate(BaseModel):
    name: str = Field(min_length=3, max_length=160)
    interval_minutes: int = Field(ge=1, le=10080)
    payload: dict[str, Any] = {}


class ScheduleResponse(BaseModel):
    id: int
    workflow_id: int
    name: str
    interval_minutes: int
    enabled: bool
    payload: dict[str, Any]
    last_run_at: datetime | None
    next_run_at: datetime


class MetricsResponse(BaseModel):
    workflows: int
    runs: int
    successful_runs: int
    failed_runs: int
    success_rate: float
    schedules: int
