import uuid

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.benchmarks import summarize_benchmarks
from app.models import AuditEvent, ComplianceFinding, MitigationScenario, NonConformance
from app.procurement import imported_shipment_assessments


class ExecutiveSummary(BaseModel):
    project_id: uuid.UUID
    critical_deviations: int
    equipment_at_risk: int
    schedule_exposure_days: int
    supply_chain_alerts: int
    commissioning_readiness: int | None
    open_ncrs: int
    measured_hours_saved: float
    projected_monthly_hours_saved: float
    recommended_mitigation: str | None
    evidence_confidence: float | None
    synthetic_data: bool


async def executive_summary(session: AsyncSession, project_id: uuid.UUID, commissioning) -> ExecutiveSummary:
    findings = list((await session.scalars(select(ComplianceFinding).where(
        ComplianceFinding.project_id == project_id,
        ComplianceFinding.status == "NON_COMPLIANT",
    ))).all())
    critical = [item for item in findings if item.severity.lower() in {"high", "critical"}]
    assessments = await imported_shipment_assessments(session, project_id, alerts_only=True)
    equipment = sorted({item.equipment_id for item in critical} | {item.equipment_id for item in assessments})
    readiness = [await commissioning.readiness(session, project_id, item) for item in equipment]
    benchmark = await summarize_benchmarks(session, project_id)
    mitigations = list((await session.scalars(select(MitigationScenario).where(
        MitigationScenario.project_id == project_id,
        MitigationScenario.equipment_id.in_(equipment or [""]),
        MitigationScenario.scenario_key.in_(("expedite_shipment", "resequence_installation")),
    ))).all())
    recommended = min(
        mitigations,
        key=lambda item: (
            int((item.impact or {}).get("critical_path_exposure_days", 10**9)),
            int((item.impact or {}).get("projected_delay_days", 10**9)),
        ),
        default=None,
    )
    synthetic = await session.scalar(select(AuditEvent.id).where(
        AuditEvent.project_id == project_id,
        AuditEvent.event_type == "vertical_demo_seeded",
    ))
    return ExecutiveSummary(
        project_id=project_id,
        critical_deviations=len(critical),
        equipment_at_risk=len(equipment),
        schedule_exposure_days=sum(item.schedule_exposure_days for item in assessments),
        supply_chain_alerts=len(assessments),
        commissioning_readiness=min((item.score for item in readiness if item), default=None),
        open_ncrs=await session.scalar(select(func.count()).select_from(NonConformance).where(
            NonConformance.project_id == project_id,
            NonConformance.status == "open",
        )) or 0,
        measured_hours_saved=benchmark.measured_hours_saved,
        projected_monthly_hours_saved=benchmark.projected_monthly_hours_saved,
        recommended_mitigation=recommended.description if recommended else None,
        evidence_confidence=(sum(item.confidence for item in critical) / len(critical)) if critical else None,
        synthetic_data=synthetic is not None,
    )
