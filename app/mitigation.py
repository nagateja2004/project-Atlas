import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion import IngestionError
from app.models import (
    AuditEvent,
    EvidenceRecord,
    ImpactEvent,
    MitigationScenario,
    ScheduleTask,
    Shipment,
)
from app.procurement import assess_persisted_shipment, schedule_exposure_severity

ScenarioKey = Literal["do_nothing", "expedite_shipment", "resequence_installation"]


class MitigationRules(BaseModel):
    expedite_recovery_days: int | None = Field(default=None, ge=0, le=3650)
    expedite_additional_cost: float | None = Field(default=None, ge=0)
    resequence_recovery_days: int | None = Field(default=None, ge=0, le=3650)
    resequence_additional_cost: float | None = Field(default=None, ge=0)


class MitigationSimulationRequest(BaseModel):
    project_id: uuid.UUID
    shipment_id: uuid.UUID
    impact_event_id: uuid.UUID
    rules: MitigationRules = Field(default_factory=MitigationRules)


class EvidenceReference(BaseModel):
    source: str
    document: str
    page: int | None = None
    clause: str | None = None
    excerpt: str


class ReadinessImpact(BaseModel):
    current_score: int
    projected_score: int
    score_delta: int
    basis: str


class CounterfactualScenario(BaseModel):
    id: uuid.UUID
    key: ScenarioKey
    action: str
    assumptions: list[str]
    projected_delay_days: int
    critical_path_exposure_days: int
    commissioning_date: date | None
    readiness_impact: ReadinessImpact
    additional_cost: float | None
    residual_risk: str
    evidence_references: list[EvidenceReference]
    confidence: float = Field(ge=0, le=1)


class MitigationSimulationResponse(BaseModel):
    simulation_id: uuid.UUID
    project_id: uuid.UUID
    equipment_id: str
    shipment_id: uuid.UUID
    impact_event_id: uuid.UUID
    baseline_delay_days: int
    baseline_exposure_days: int
    scenarios: list[CounterfactualScenario]


class MitigationSelectionRequest(BaseModel):
    project_id: uuid.UUID
    scenario_key: ScenarioKey
    reviewer_note: str | None = Field(default=None, max_length=2_000)


class RecalculatedImpactChain(BaseModel):
    source_event_id: uuid.UUID
    shipment_id: uuid.UUID
    equipment_id: str
    selected_scenario_id: uuid.UUID
    projected_schedule_delay_days: int
    projected_critical_path_exposure_days: int
    projected_commissioning_date: date | None
    projected_readiness_score: int
    residual_risk: str
    evidence_references: list[EvidenceReference]


class MitigationSelectionResponse(BaseModel):
    simulation_id: uuid.UUID
    selected: CounterfactualScenario
    recalculated_impact_chain: RecalculatedImpactChain


async def simulate_mitigations(
    session: AsyncSession,
    payload: MitigationSimulationRequest,
    commissioning_service,
) -> MitigationSimulationResponse:
    shipment = await session.scalar(
        select(Shipment).where(
            Shipment.id == payload.shipment_id,
            Shipment.project_id == payload.project_id,
        )
    )
    event = await session.scalar(
        select(ImpactEvent).where(
            ImpactEvent.id == payload.impact_event_id,
            ImpactEvent.project_id == payload.project_id,
            ImpactEvent.equipment_id == shipment.equipment_id if shipment else False,
            ImpactEvent.type.in_(("DELIVERY_RISK", "SCHEDULE_IMPACT")),
        )
    )
    if not shipment or not event or event.source_id != str(shipment.id):
        raise IngestionError("mitigation_risk_not_found", "Select a project-scoped shipment risk", 404)
    risk = await assess_persisted_shipment(session, payload.project_id, shipment.id)
    if not risk:
        raise IngestionError("mitigation_risk_unavailable", "Shipment dates required for simulation are missing")
    readiness = await commissioning_service.readiness(session, payload.project_id, shipment.equipment_id)
    if not readiness:
        raise IngestionError("mitigation_readiness_unavailable", "Equipment readiness is unavailable")
    simulation_id = uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"atlas:{payload.project_id}:{shipment.id}:{event.id}:{payload.rules.model_dump_json()}",
    )
    existing = list((await session.scalars(
        select(MitigationScenario).where(
            MitigationScenario.project_id == payload.project_id,
            MitigationScenario.simulation_id == simulation_id,
        )
    )).all())
    if len(existing) == 3:
        order = {"do_nothing": 0, "expedite_shipment": 1, "resequence_installation": 2}
        scenarios = [CounterfactualScenario.model_validate(item.impact) for item in existing]
        scenarios.sort(key=lambda item: order[item.key])
        return MitigationSimulationResponse(
            simulation_id=simulation_id,
            project_id=payload.project_id,
            equipment_id=shipment.equipment_id,
            shipment_id=shipment.id,
            impact_event_id=event.id,
            baseline_delay_days=max(0, risk.eta_variance_days),
            baseline_exposure_days=risk.schedule_exposure_days,
            scenarios=scenarios,
        )
    tasks = list((await session.scalars(
        select(ScheduleTask).where(
            ScheduleTask.project_id == payload.project_id,
            ScheduleTask.equipment_id == shipment.equipment_id,
        )
    )).all())
    commissioning_tasks = [
        item for item in tasks
        if any(term in item.name.lower() for term in ("install", "test", "commission"))
    ] or tasks
    current_commissioning = max(
        (item.forecast_finish for item in commissioning_tasks if item.forecast_finish), default=None
    )
    planned_commissioning = max(
        (item.planned_finish for item in commissioning_tasks if item.planned_finish), default=None
    )
    evidence = await _evidence(session, payload.project_id, event, shipment)
    definitions = (
        ("do_nothing", "Do nothing", 0, 0.0, "baseline"),
        (
            "expedite_shipment",
            "Expedite shipment",
            payload.rules.expedite_recovery_days,
            payload.rules.expedite_additional_cost,
            "expedite",
        ),
        (
            "resequence_installation",
            "Resequence installation",
            payload.rules.resequence_recovery_days,
            payload.rules.resequence_additional_cost,
            "resequence",
        ),
    )
    scenarios = []
    for key, action, configured_recovery, cost, mode in definitions:
        recovery = configured_recovery or 0
        if mode == "expedite":
            projected_eta = shipment.forecast_delivery - timedelta(days=recovery)
            projected_delay = max(0, (projected_eta - shipment.planned_delivery).days)
            exposure = max(
                0,
                (projected_eta - shipment.required_on_site_date).days - shipment.available_float_days,
            )
        elif mode == "resequence":
            projected_delay = max(0, risk.eta_variance_days)
            exposure = max(0, risk.schedule_exposure_days - recovery)
        else:
            projected_delay = max(0, risk.eta_variance_days)
            exposure = risk.schedule_exposure_days
        recovered_exposure = risk.schedule_exposure_days - exposure
        commissioning_date = (
            current_commissioning - timedelta(days=recovered_exposure) if current_commissioning else None
        )
        if commissioning_date and planned_commissioning:
            commissioning_date = max(commissioning_date, planned_commissioning)
        assumptions = _assumptions(mode, configured_recovery, cost)
        confidence = event.confidence if mode == "baseline" or configured_recovery is not None else 0.0
        scenario = CounterfactualScenario(
            id=uuid.uuid4(),
            key=key,
            action=action,
            assumptions=assumptions,
            projected_delay_days=projected_delay,
            critical_path_exposure_days=exposure,
            commissioning_date=commissioning_date,
            readiness_impact=ReadinessImpact(
                current_score=readiness.score,
                projected_score=readiness.score,
                score_delta=0,
                basis="Counterfactual dates do not award readiness points until project delivery and test records change.",
            ),
            additional_cost=cost,
            residual_risk=schedule_exposure_severity(projected_delay, exposure),
            evidence_references=evidence,
            confidence=confidence,
        )
        session.add(
            MitigationScenario(
                id=scenario.id,
                simulation_id=simulation_id,
                project_id=payload.project_id,
                equipment_id=shipment.equipment_id,
                name=f"Counterfactual {simulation_id} {key}",
                scenario_key=key,
                status="simulated",
                description=action,
                impact={
                    **scenario.model_dump(mode="json"),
                    "_shipment_id": str(shipment.id),
                    "_impact_event_id": str(event.id),
                },
                revision="counterfactual-v1",
                approval_status="not_selected",
                evidence=[item.model_dump(mode="json") for item in evidence],
            )
        )
        scenarios.append(scenario)
    await session.commit()
    return MitigationSimulationResponse(
        simulation_id=simulation_id,
        project_id=payload.project_id,
        equipment_id=shipment.equipment_id,
        shipment_id=shipment.id,
        impact_event_id=event.id,
        baseline_delay_days=max(0, risk.eta_variance_days),
        baseline_exposure_days=risk.schedule_exposure_days,
        scenarios=scenarios,
    )


async def select_mitigation(
    session: AsyncSession,
    simulation_id: uuid.UUID,
    payload: MitigationSelectionRequest,
) -> MitigationSelectionResponse | None:
    scenarios = list((await session.scalars(
        select(MitigationScenario).where(
            MitigationScenario.simulation_id == simulation_id,
            MitigationScenario.project_id == payload.project_id,
        )
    )).all())
    selected = next((item for item in scenarios if item.scenario_key == payload.scenario_key), None)
    if not selected:
        return None
    at = datetime.now(UTC)
    for item in scenarios:
        item.status = "selected" if item.id == selected.id else "not_selected"
        item.approval_status = item.status
        item.selected_at = at if item.id == selected.id else None
    scenario = CounterfactualScenario.model_validate(selected.impact)
    shipment = await session.scalar(
        select(Shipment).where(
            Shipment.project_id == payload.project_id,
            Shipment.id == uuid.UUID(selected.impact["_shipment_id"]),
        )
    )
    source_event = await session.scalar(
        select(ImpactEvent).where(
            ImpactEvent.id == uuid.UUID(selected.impact["_impact_event_id"]),
            ImpactEvent.project_id == payload.project_id,
        )
    )
    if not shipment or not source_event:
        return None
    chain = RecalculatedImpactChain(
        source_event_id=source_event.id,
        shipment_id=shipment.id,
        equipment_id=selected.equipment_id,
        selected_scenario_id=selected.id,
        projected_schedule_delay_days=scenario.projected_delay_days,
        projected_critical_path_exposure_days=scenario.critical_path_exposure_days,
        projected_commissioning_date=scenario.commissioning_date,
        projected_readiness_score=scenario.readiness_impact.projected_score,
        residual_risk=scenario.residual_risk,
        evidence_references=scenario.evidence_references,
    )
    session.add(
        AuditEvent(
            project_id=payload.project_id,
            event_type="counterfactual_mitigation_selected",
            payload={
                "simulation_id": str(simulation_id),
                "scenario_id": str(selected.id),
                "scenario_key": payload.scenario_key,
                "reviewer_note": payload.reviewer_note,
                "recalculated_impact_chain": chain.model_dump(mode="json"),
            },
        )
    )
    await session.commit()
    return MitigationSelectionResponse(
        simulation_id=simulation_id,
        selected=scenario,
        recalculated_impact_chain=chain,
    )


async def _evidence(session, project_id, event, shipment) -> list[EvidenceReference]:
    records = list((await session.scalars(
        select(EvidenceRecord).where(
            EvidenceRecord.project_id == project_id,
            EvidenceRecord.impact_event_id == event.id,
        )
    )).all())
    evidence = [
        EvidenceReference(
            source="impact_evidence",
            document=item.document,
            page=item.page,
            clause=item.clause,
            excerpt=item.excerpt,
        )
        for item in records
    ]
    source = shipment.evidence or {}
    evidence.append(
        EvidenceReference(
            source="shipment_record",
            document=str(source.get("filename") or shipment.reference),
            page=source.get("row"),
            clause="shipment dates and schedule link",
            excerpt=(
                f"planned={shipment.planned_delivery}; eta={shipment.forecast_delivery}; "
                f"required_on_site={shipment.required_on_site_date}; float={shipment.available_float_days}; "
                f"task={shipment.schedule_task_id}"
            ),
        )
    )
    return evidence


def _assumptions(mode: str, recovery: int | None, cost: float | None) -> list[str]:
    if mode == "baseline":
        return ["Current ETA, schedule float, task dates, and readiness records remain unchanged."]
    label = "Expedite" if mode == "expedite" else "Resequencing"
    return [
        (
            f"{label} recovery of {recovery} days is a configured scenario input."
            if recovery is not None
            else f"{label} recovery duration is not configured; no recovery is applied."
        ),
        (
            f"Additional cost {cost} is a configured scenario input, not a quotation."
            if cost is not None
            else "Additional cost is not configured and remains unknown."
        ),
    ]
