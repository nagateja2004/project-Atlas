import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import WorkflowBenchmark

WorkflowType = Literal[
    "rfi_search",
    "submittal_review",
    "schedule_impact_tracing",
    "commissioning_checklist_preparation",
    "coordination_report_preparation",
]
MeasurementKind = Literal["measured", "projected"]


class BenchmarkCreate(BaseModel):
    project_id: uuid.UUID
    workflow_type: WorkflowType
    manual_baseline_seconds: float = Field(ge=0)
    atlas_execution_seconds: float = Field(ge=0)
    measurement_source: str = Field(min_length=1, max_length=255)
    sample_count: int = Field(gt=0, description="Observed samples, or projected monthly volume for projected records")
    measurement_kind: MeasurementKind = Field(description="Whether timing is observed or a monthly projection")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    synthetic_data: bool


class BenchmarkResponse(BenchmarkCreate):
    id: uuid.UUID
    hours_saved: float
    total_hours_saved: float


class WorkflowBenchmarkSummary(BaseModel):
    workflow_type: WorkflowType
    measured_hours_saved: float
    projected_monthly_hours_saved: float
    measured_sample_count: int
    projected_monthly_sample_count: int


class BenchmarkSummary(BaseModel):
    project_id: uuid.UUID
    measured_hours_saved: float
    projected_monthly_hours_saved: float
    measured_sample_count: int
    projected_monthly_sample_count: int
    record_count: int
    synthetic_data_present: bool
    label: str
    workflows: list[WorkflowBenchmarkSummary]


def _saved_hours(record: WorkflowBenchmark) -> float:
    return (record.manual_baseline_seconds - record.atlas_execution_seconds) / 3600


def benchmark_response(record: WorkflowBenchmark) -> BenchmarkResponse:
    per_sample = _saved_hours(record)
    return BenchmarkResponse(
        id=record.id,
        project_id=record.project_id,
        workflow_type=record.workflow_type,
        manual_baseline_seconds=record.manual_baseline_seconds,
        atlas_execution_seconds=record.atlas_execution_seconds,
        measurement_source=record.measurement_source,
        sample_count=record.sample_count,
        measurement_kind=record.measurement_kind,
        timestamp=record.timestamp,
        synthetic_data=record.synthetic_data,
        hours_saved=per_sample,
        total_hours_saved=per_sample * record.sample_count,
    )


async def record_benchmark(session: AsyncSession, payload: BenchmarkCreate) -> BenchmarkResponse:
    record = WorkflowBenchmark(**payload.model_dump())
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return benchmark_response(record)


async def summarize_benchmarks(session: AsyncSession, project_id: uuid.UUID) -> BenchmarkSummary:
    records = list((await session.scalars(
        select(WorkflowBenchmark).where(WorkflowBenchmark.project_id == project_id)
    )).all())
    rows: list[WorkflowBenchmarkSummary] = []
    for workflow_type in WorkflowType.__args__:
        matching = [record for record in records if record.workflow_type == workflow_type]
        measured = [record for record in matching if record.measurement_kind == "measured"]
        projected = [record for record in matching if record.measurement_kind == "projected"]
        rows.append(WorkflowBenchmarkSummary(
            workflow_type=workflow_type,
            measured_hours_saved=sum(_saved_hours(record) * record.sample_count for record in measured),
            projected_monthly_hours_saved=sum(_saved_hours(record) * record.sample_count for record in projected),
            measured_sample_count=sum(record.sample_count for record in measured),
            projected_monthly_sample_count=sum(record.sample_count for record in projected),
        ))
    synthetic = any(record.synthetic_data for record in records)
    return BenchmarkSummary(
        project_id=project_id,
        measured_hours_saved=sum(row.measured_hours_saved for row in rows),
        projected_monthly_hours_saved=sum(row.projected_monthly_hours_saved for row in rows),
        measured_sample_count=sum(row.measured_sample_count for row in rows),
        projected_monthly_sample_count=sum(row.projected_monthly_sample_count for row in rows),
        record_count=len(records),
        synthetic_data_present=synthetic,
        label="Includes synthetic demo measurements" if synthetic else "Recorded project measurements only",
        workflows=rows,
    )
