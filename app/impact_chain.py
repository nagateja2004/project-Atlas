import math
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.commissioning import CommissioningService, EquipmentReadiness
from app.ingestion import IngestionError
from app.models import (
    AuditEvent,
    ComplianceFinding,
    Document,
    Equipment,
    EvidenceRecord,
    ImpactEdge,
    ImpactEvent,
    MitigationScenario,
    NonConformance,
    RFI,
)
from app.procurement import ShipmentRiskResponse, shipment_risk
from app.schedule import ProcurementInput, ScheduleScenario, ScheduleService, classify_risk

HumanAction = Literal["APPROVE", "REJECT", "REQUEST_REVIEW", "CREATE_RFI", "CREATE_NCR"]
ImpactEventType = Literal[
    "SPEC_DEVIATION",
    "VENDOR_RESUBMISSION",
    "DELIVERY_RISK",
    "SCHEDULE_IMPACT",
    "COMMISSIONING_IMPACT",
]

EVENT_SEQUENCE: tuple[ImpactEventType, ...] = (
    "SPEC_DEVIATION",
    "VENDOR_RESUBMISSION",
    "DELIVERY_RISK",
    "SCHEDULE_IMPACT",
    "COMMISSIONING_IMPACT",
)
RELATIONSHIPS = (
    "requires_resubmission",
    "creates_delivery_risk",
    "propagates_to_schedule",
    "affects_commissioning",
)


class PropagationAssumptions(BaseModel):
    vendor_resubmission_days: int = Field(default=7, ge=0, le=3650)
    delivery_risk_days: int = Field(default=14, ge=0, le=3650)
    schedule_impact_days: int = Field(default=14, ge=0, le=3650)
    commissioning_impact_days: int = Field(default=0, ge=0, le=3650)

    def delays(self) -> tuple[int, ...]:
        return (
            self.vendor_resubmission_days,
            self.delivery_risk_days,
            self.schedule_impact_days,
            self.commissioning_impact_days,
        )


class EvidenceRecordInput(BaseModel):
    claim: str = Field(min_length=1, max_length=4_000)
    document: str = Field(min_length=1, max_length=512)
    page: int | None = Field(default=None, ge=1)
    clause: str | None = Field(default=None, max_length=255)
    excerpt: str = Field(min_length=1, max_length=8_000)
    model_version: str = Field(default="source", min_length=1, max_length=100)
    verification_status: Literal["VERIFIED", "UNVERIFIED"] = "UNVERIFIED"


class ImpactEventCreate(BaseModel):
    type: ImpactEventType
    source_id: str = Field(min_length=1, max_length=255)
    severity: Literal["low", "medium", "high", "critical"]
    confidence: float = Field(ge=0, le=1)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    assumptions: PropagationAssumptions = Field(default_factory=PropagationAssumptions)
    evidence: list[EvidenceRecordInput] = Field(default_factory=list, max_length=50)


class ImpactEventResponse(BaseModel):
    id: uuid.UUID
    type: ImpactEventType
    project_id: uuid.UUID
    equipment_id: str
    source_id: str
    severity: str
    confidence: float
    timestamp: datetime
    assumptions: dict


class ImpactEdgeResponse(BaseModel):
    id: uuid.UUID
    source_event: uuid.UUID
    target_event: uuid.UUID
    relationship: str
    delay_days: int
    confidence: float


class EvidenceRecordResponse(EvidenceRecordInput):
    id: uuid.UUID
    impact_event_id: uuid.UUID


class EquipmentImpactChain(BaseModel):
    project_id: uuid.UUID
    equipment_id: str
    events: list[ImpactEventResponse]
    edges: list[ImpactEdgeResponse]
    evidence: list[EvidenceRecordResponse]


async def propagate_event(
    session: AsyncSession,
    project_id: uuid.UUID,
    equipment_id: str,
    payload: ImpactEventCreate,
) -> EquipmentImpactChain:
    start = EVENT_SEQUENCE.index(payload.type)
    event_types = EVENT_SEQUENCE[start:]
    delays = payload.assumptions.delays()[start:]
    events: list[ImpactEvent] = []
    timestamp = payload.timestamp
    confidence = payload.confidence
    for index, event_type in enumerate(event_types):
        assumptions = payload.assumptions.model_dump() if index == 0 else {
            "derived_from": event_types[index - 1],
            "delay_days": delays[index - 1],
        }
        event = ImpactEvent(
            id=uuid.uuid4(),
            project_id=project_id,
            equipment_id=equipment_id,
            type=event_type,
            source_id=payload.source_id,
            severity=payload.severity,
            confidence=round(confidence, 4),
            timestamp=timestamp,
            assumptions=assumptions,
        )
        events.append(event)
        if index < len(event_types) - 1:
            delay = delays[index]
            confidence = round(confidence * 0.95, 4)
            timestamp += timedelta(days=delay)
    session.add_all(events)
    # Persist parent rows before evidence/edge foreign keys; PostgreSQL enforces this immediately.
    await session.flush()
    session.add_all(
        ImpactEdge(
            project_id=project_id,
            equipment_id=equipment_id,
            source_event=source.id,
            target_event=target.id,
            relationship=RELATIONSHIPS[start + index],
            delay_days=delays[index],
            confidence=target.confidence,
        )
        for index, (source, target) in enumerate(zip(events, events[1:], strict=False))
    )
    for item in payload.evidence:
        session.add(
            EvidenceRecord(
                project_id=project_id,
                equipment_id=equipment_id,
                impact_event_id=events[0].id,
                **item.model_dump(),
            )
        )
    session.add(
        AuditEvent(
            project_id=project_id,
            event_type="impact_event_propagated",
            payload={
                "equipment_id": equipment_id,
                "source_id": payload.source_id,
                "root_event_id": str(events[0].id),
                "event_types": list(event_types),
            },
        )
    )
    await session.commit()
    return await equipment_impact_chain(session, project_id, equipment_id)


async def equipment_impact_chain(
    session: AsyncSession, project_id: uuid.UUID, equipment_id: str
) -> EquipmentImpactChain:
    events = list((await session.scalars(
        select(ImpactEvent)
        .where(ImpactEvent.project_id == project_id, ImpactEvent.equipment_id == equipment_id)
    )).all())
    events.sort(key=lambda item: (item.timestamp, EVENT_SEQUENCE.index(item.type), str(item.id)))
    event_ids = [item.id for item in events]
    edges = list((await session.scalars(
        select(ImpactEdge)
        .where(ImpactEdge.project_id == project_id, ImpactEdge.equipment_id == equipment_id)
    )).all())
    evidence = list((await session.scalars(
        select(EvidenceRecord)
        .where(EvidenceRecord.project_id == project_id, EvidenceRecord.equipment_id == equipment_id)
        .order_by(EvidenceRecord.id)
    )).all())
    event_order = {event_id: index for index, event_id in enumerate(event_ids)}
    edges.sort(key=lambda item: event_order.get(item.source_event, len(event_order)))
    return EquipmentImpactChain(
        project_id=project_id,
        equipment_id=equipment_id,
        events=[ImpactEventResponse.model_validate(item, from_attributes=True) for item in events],
        edges=[ImpactEdgeResponse.model_validate(item, from_attributes=True) for item in edges if item.source_event in event_ids and item.target_event in event_ids],
        evidence=[EvidenceRecordResponse.model_validate(item, from_attributes=True) for item in evidence if item.impact_event_id in event_ids],
    )


class ImpactChainStart(BaseModel):
    compliance_finding_id: uuid.UUID
    shipment_id: uuid.UUID
    schedule_document_id: uuid.UUID
    replacement_lead_time_days: int = Field(gt=0)
    replacement_cost: float = Field(ge=0)
    analysis_date: date


class ImpactDecision(BaseModel):
    action: HumanAction
    scenario_id: uuid.UUID | None = None
    note: str | None = Field(default=None, max_length=2_000)

    @model_validator(mode="after")
    def require_scenario_for_approval(self):
        if self.action == "APPROVE" and not self.scenario_id:
            raise ValueError("scenario_id is required for APPROVE")
        return self


class ProcurementImpact(BaseModel):
    shipment_id: uuid.UUID
    shipment_reference: str
    replacement_lead_time_days: int
    current_forecast_delay_days: int
    schedule_task_id: str


class ScheduleImpact(BaseModel):
    affected_task: str
    available_float_days: int
    predicted_delay_days: int
    critical_path_impact_days: int
    affected_completion_date: date
    severity: str
    evidence: list[dict]


class ImpactMitigationScenario(BaseModel):
    id: uuid.UUID
    action: str
    days_recovered: int
    added_cost: float
    remaining_delay: int
    remaining_risk: str
    assumptions: list[str]
    confidence: float = Field(ge=0, le=1)
    evidence: list[dict]


class ApprovedAction(BaseModel):
    id: uuid.UUID
    action: HumanAction
    scenario_id: uuid.UUID | None
    status: str
    created_record_id: uuid.UUID | None = None
    note: str | None = None


class ImpactChainResponse(BaseModel):
    chain_id: uuid.UUID
    project_id: uuid.UUID
    finding_id: uuid.UUID
    equipment_id: str
    finding_parameter: str
    finding_required_value: str
    finding_observed_value: str | None
    procurement: ProcurementImpact
    schedule: ScheduleImpact
    commissioning_readiness: EquipmentReadiness
    mitigation_scenarios: list[ImpactMitigationScenario]
    status: Literal["AWAITING_HUMAN_DECISION", "ACTION_CREATED"]
    human_decision: ImpactDecision | None = None
    approved_action: ApprovedAction | None = None
    evidence_chain: list[dict]


class ImpactState(TypedDict, total=False):
    session: AsyncSession
    project_id: uuid.UUID
    chain_id: uuid.UUID
    request: ImpactChainStart
    decision: ImpactDecision | None
    finding: ComplianceFinding
    equipment_id: str
    procurement: ProcurementImpact
    procurement_risk: ShipmentRiskResponse
    schedule: ScheduleImpact
    readiness: EquipmentReadiness
    scenarios: list[ImpactMitigationScenario]
    status: str
    approved_action: ApprovedAction | None
    evidence_chain: list[dict]


class ImpactChainService:
    def __init__(self, schedule: ScheduleService, commissioning: CommissioningService) -> None:
        self.schedule = schedule
        self.commissioning = commissioning
        self.workflow = self._build_workflow()

    async def start(
        self, session: AsyncSession, project_id: uuid.UUID, request: ImpactChainStart
    ) -> ImpactChainResponse:
        chain_id = uuid.uuid4()
        state = await self.workflow.ainvoke(
            {
                "session": session,
                "project_id": project_id,
                "chain_id": chain_id,
                "request": request,
                "decision": None,
                "evidence_chain": [],
            }
        )
        response = _response(state)
        session.add(
            AuditEvent(
                id=chain_id,
                project_id=project_id,
                event_type="impact_chain_awaiting_human_decision",
                payload={"input": request.model_dump(mode="json"), "result": response.model_dump(mode="json")},
            )
        )
        await session.commit()
        return response

    async def decide(
        self,
        session: AsyncSession,
        project_id: uuid.UUID,
        chain_id: uuid.UUID,
        decision: ImpactDecision,
    ) -> ImpactChainResponse | None:
        chain = await session.scalar(
            select(AuditEvent).where(
                AuditEvent.id == chain_id,
                AuditEvent.project_id == project_id,
                AuditEvent.event_type == "impact_chain_awaiting_human_decision",
            )
        )
        if not chain:
            return None
        request = ImpactChainStart.model_validate(chain.payload["input"])
        state = await self.workflow.ainvoke(
            {
                "session": session,
                "project_id": project_id,
                "chain_id": chain_id,
                "request": request,
                "decision": decision,
                "evidence_chain": [],
            }
        )
        response = _response(state)
        session.add(
            AuditEvent(
                project_id=project_id,
                event_type="impact_chain_decided",
                payload={"chain_id": str(chain_id), "result": response.model_dump(mode="json")},
            )
        )
        await session.commit()
        return response

    def _build_workflow(self):
        async def compliance_finding_created(state: ImpactState):
            finding = await state["session"].scalar(
                select(ComplianceFinding).where(
                    ComplianceFinding.id == state["request"].compliance_finding_id,
                    ComplianceFinding.project_id == state["project_id"],
                )
            )
            if not finding or finding.status != "NON_COMPLIANT":
                raise IngestionError("invalid_impact_finding", "Select a project-scoped non-compliant finding")
            finding_events = (
                await state["session"].scalars(
                    select(AuditEvent).where(
                        AuditEvent.project_id == state["project_id"],
                        AuditEvent.event_type == "compliance_finding_created",
                    )
                )
            ).all()
            if not any(event.payload.get("finding_id") == str(finding.id) for event in finding_events):
                raise IngestionError("impact_trigger_missing", "Compliance finding creation event is missing")
            evidence = [
                {"stage": "compliance", "source": "specification", **finding.specification_citation},
                {"stage": "compliance", "source": "submittal", **(finding.submittal_citation or {})},
            ]
            return {"finding": finding, "evidence_chain": evidence}

        async def resolve_equipment(state: ImpactState):
            equipment = await state["session"].scalar(
                select(Equipment).where(
                    Equipment.project_id == state["project_id"],
                    Equipment.equipment_id == state["finding"].equipment_id,
                )
            )
            if not equipment:
                raise IngestionError("equipment_not_found", "Finding equipment is not registered", 404)
            return {
                "equipment_id": equipment.equipment_id,
                "evidence_chain": [
                    *state["evidence_chain"],
                    {"stage": "equipment", "equipment_id": equipment.equipment_id, "name": equipment.name},
                ],
            }

        async def analyse_procurement(state: ImpactState):
            risk = await shipment_risk(
                state["session"], state["project_id"], state["request"].shipment_id
            )
            if not risk or risk.equipment_id != state["equipment_id"]:
                raise IngestionError("shipment_not_found", "Select a shipment for the finding equipment", 404)
            procurement = ProcurementImpact(
                shipment_id=risk.shipment_id,
                shipment_reference=risk.reference,
                replacement_lead_time_days=state["request"].replacement_lead_time_days,
                current_forecast_delay_days=risk.forecast_delay_days,
                schedule_task_id=risk.schedule_task_id,
            )
            return {
                "procurement": procurement,
                "procurement_risk": risk,
                "evidence_chain": [
                    *state["evidence_chain"],
                    {
                        "stage": "procurement",
                        "shipment_id": str(risk.shipment_id),
                        "reference": risk.reference,
                        "replacement_lead_time_days": state["request"].replacement_lead_time_days,
                    },
                ],
            }

        async def calculate_schedule_impact(state: ImpactState):
            document = await state["session"].scalar(
                select(Document).where(
                    Document.id == state["request"].schedule_document_id,
                    Document.project_id == state["project_id"],
                )
            )
            if not document:
                raise IngestionError("schedule_not_found", "Schedule document not found", 404)
            task_id = state["procurement"].schedule_task_id
            analysis = await self.schedule.analyze(
                document,
                ScheduleScenario(
                    analysis_date=state["request"].analysis_date,
                    procurement={
                        task_id: ProcurementInput(
                            status="replacement_required",
                            lead_time_days=state["request"].replacement_lead_time_days,
                        )
                    },
                ),
            )
            risk = next((item for item in analysis.risks if item.affected_task == task_id), None)
            if not risk:
                raise IngestionError("schedule_impact_missing", "Replacement lead time produced no schedule impact")
            impact = ScheduleImpact(
                affected_task=risk.affected_task,
                available_float_days=risk.available_float_days,
                predicted_delay_days=risk.predicted_delay_days,
                critical_path_impact_days=max(0, risk.predicted_delay_days - risk.available_float_days),
                affected_completion_date=risk.affected_completion_date,
                severity=risk.severity,
                evidence=[item.model_dump(mode="json") for item in risk.evidence],
            )
            return {
                "schedule": impact,
                "evidence_chain": [
                    *state["evidence_chain"],
                    {
                        "stage": "schedule",
                        "task_id": impact.affected_task,
                        "available_float_days": impact.available_float_days,
                        "predicted_delay_days": impact.predicted_delay_days,
                        "citations": impact.evidence,
                    },
                ],
            }

        async def calculate_commissioning_readiness(state: ImpactState):
            readiness = await self.commissioning.readiness(
                state["session"], state["project_id"], state["equipment_id"]
            )
            if not readiness:
                raise IngestionError("readiness_unavailable", "Equipment readiness data is unavailable")
            return {
                "readiness": readiness,
                "evidence_chain": [
                    *state["evidence_chain"],
                    {
                        "stage": "commissioning_readiness",
                        "score": readiness.score,
                        "rules": [item.model_dump() for item in readiness.rules],
                    },
                ],
            }

        async def generate_mitigation_scenarios(state: ImpactState):
            delay = state["schedule"].predicted_delay_days
            lead = state["request"].replacement_lead_time_days
            cost = state["request"].replacement_cost
            definitions = (
                ("Expedite compliant equipment replacement", min(delay, math.ceil(lead * 0.25)), 0.20, 0.98, ["Supplier accepts synthetic expedite window."]),
                ("Install approved temporary compliant package", min(delay, math.ceil(lead * 0.50)), 0.35, 0.92, ["Temporary package passes project engineering review."]),
                ("Resequence off-site testing and downstream commissioning", min(delay, 10), 0.10, 0.88, ["Independent downstream work fronts remain available."]),
            )
            evidence = list(state["evidence_chain"])
            scenarios = []
            for index, (action, recovered, premium, confidence_factor, assumptions) in enumerate(definitions, 1):
                remaining = max(0, delay - recovered)
                values = {
                    "action": action,
                    "days_recovered": recovered,
                    "added_cost": round(cost * premium, 2),
                    "remaining_delay": remaining,
                    "remaining_risk": "on_track" if remaining == 0 else classify_risk(remaining, state["schedule"].available_float_days),
                    "assumptions": [*assumptions, "Costs use the currency of the supplied replacement_cost input."],
                    "confidence": round(state["finding"].confidence * confidence_factor, 3),
                    "evidence": evidence,
                }
                name = f"Impact {state['chain_id']} scenario {index}"
                stored = await state["session"].scalar(
                    select(MitigationScenario).where(
                        MitigationScenario.project_id == state["project_id"],
                        MitigationScenario.equipment_id == state["equipment_id"],
                        MitigationScenario.name == name,
                    )
                )
                if not stored:
                    stored = MitigationScenario(
                        project_id=state["project_id"],
                        equipment_id=state["equipment_id"],
                        name=name,
                        description=action,
                        impact={key: value for key, value in values.items() if key not in {"evidence", "assumptions"}},
                        evidence=evidence,
                        revision="impact-chain-v1",
                        approval_status="pending",
                    )
                    state["session"].add(stored)
                    await state["session"].flush()
                scenarios.append(ImpactMitigationScenario(id=stored.id, **values))
            return {"scenarios": scenarios}

        def await_human_decision(state: ImpactState):
            return {
                "status": "AWAITING_HUMAN_DECISION" if not state.get("decision") else "ACTION_CREATED",
                "approved_action": None,
            }

        async def create_approved_action(state: ImpactState):
            decision = state["decision"]
            scenario_ids = {item.id for item in state["scenarios"]}
            if decision.scenario_id and decision.scenario_id not in scenario_ids:
                raise IngestionError("invalid_mitigation_scenario", "Scenario does not belong to this impact chain")
            created_record_id = None
            if decision.action == "APPROVE":
                scenario = await state["session"].get(MitigationScenario, decision.scenario_id)
                scenario.status = scenario.approval_status = "approved"
                created_record_id = scenario.id
            elif decision.action in {"REJECT", "REQUEST_REVIEW"}:
                value = "rejected" if decision.action == "REJECT" else "needs_review"
                for item in state["scenarios"]:
                    scenario = await state["session"].get(MitigationScenario, item.id)
                    scenario.status = scenario.approval_status = value
            elif decision.action == "CREATE_RFI":
                finding = state["finding"]
                record = RFI(
                    project_id=state["project_id"],
                    equipment_id=state["equipment_id"],
                    document_id=finding.submittal_document_id,
                    rfi_number=f"IMPACT-{str(state['chain_id'])[:8]}",
                    status="open",
                    question=f"Confirm mitigation for {finding.requirement}: required {finding.required_value}, observed {finding.observed_value}.",
                    approval_status="pending",
                    citation=finding.submittal_citation or finding.specification_citation,
                )
                state["session"].add(record)
                await state["session"].flush()
                created_record_id = record.id
            elif decision.action == "CREATE_NCR":
                finding = state["finding"]
                record = NonConformance(
                    project_id=state["project_id"],
                    equipment_id=state["equipment_id"],
                    compliance_finding_id=finding.id,
                    step_index=0,
                    criterion=finding.requirement,
                    observation=finding.observed_value or "Missing value",
                    citation=finding.submittal_citation or finding.specification_citation,
                )
                state["session"].add(record)
                await state["session"].flush()
                created_record_id = record.id
            action_event = AuditEvent(
                project_id=state["project_id"],
                event_type="impact_action_created",
                payload={
                    "chain_id": str(state["chain_id"]),
                    "action": decision.action,
                    "scenario_id": str(decision.scenario_id) if decision.scenario_id else None,
                    "created_record_id": str(created_record_id) if created_record_id else None,
                    "note": decision.note,
                    "evidence_chain": state["evidence_chain"],
                },
            )
            state["session"].add(action_event)
            await state["session"].flush()
            return {
                "status": "ACTION_CREATED",
                "approved_action": ApprovedAction(
                    id=action_event.id,
                    action=decision.action,
                    scenario_id=decision.scenario_id,
                    status="created",
                    created_record_id=created_record_id,
                    note=decision.note,
                ),
            }

        graph = StateGraph(ImpactState)
        graph.add_node("compliance_finding_created", compliance_finding_created)
        graph.add_node("resolve_equipment", resolve_equipment)
        graph.add_node("analyse_procurement", analyse_procurement)
        graph.add_node("calculate_schedule_impact", calculate_schedule_impact)
        graph.add_node("calculate_commissioning_readiness", calculate_commissioning_readiness)
        graph.add_node("generate_mitigation_scenarios", generate_mitigation_scenarios)
        graph.add_node("await_human_decision", await_human_decision)
        graph.add_node("create_approved_action", create_approved_action)
        graph.add_edge(START, "compliance_finding_created")
        graph.add_edge("compliance_finding_created", "resolve_equipment")
        graph.add_edge("resolve_equipment", "analyse_procurement")
        graph.add_edge("analyse_procurement", "calculate_schedule_impact")
        graph.add_edge("calculate_schedule_impact", "calculate_commissioning_readiness")
        graph.add_edge("calculate_commissioning_readiness", "generate_mitigation_scenarios")
        graph.add_edge("generate_mitigation_scenarios", "await_human_decision")
        graph.add_conditional_edges(
            "await_human_decision",
            lambda state: "create" if state.get("decision") else "end",
            {"create": "create_approved_action", "end": END},
        )
        graph.add_edge("create_approved_action", END)
        return graph.compile()


def _response(state: ImpactState) -> ImpactChainResponse:
    return ImpactChainResponse(
        chain_id=state["chain_id"],
        project_id=state["project_id"],
        finding_id=state["finding"].id,
        equipment_id=state["equipment_id"],
        finding_parameter=state["finding"].requirement_key,
        finding_required_value=state["finding"].required_value,
        finding_observed_value=state["finding"].observed_value,
        procurement=state["procurement"],
        schedule=state["schedule"],
        commissioning_readiness=state["readiness"],
        mitigation_scenarios=state["scenarios"],
        status=state["status"],
        human_decision=state.get("decision"),
        approved_action=state.get("approved_action"),
        evidence_chain=state["evidence_chain"],
    )
