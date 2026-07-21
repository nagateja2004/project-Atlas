import csv
import io
import json
import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion import IngestionError
from app.models import AuditEvent, Equipment, ImpactEvent, ScheduleTask, Shipment, ShipmentEvent, Vendor

SYNTHETIC_DISCLAIMER = (
    "SYNTHETIC SIMULATION DATA — no live AIS, position, carrier, or external logistics feed is connected."
)


class ProcurementItemInput(BaseModel):
    equipment_tag: str = Field(min_length=1, max_length=100)
    vendor: str = Field(min_length=1, max_length=255)
    purchase_order_status: str = Field(min_length=1, max_length=50)
    planned_delivery: date
    forecast_delivery: date | None = None
    lead_time_days: int | None = Field(default=None, ge=0)


class ProcurementRiskCard(ProcurementItemInput):
    delay_days: int | None
    risk_level: Literal["on_track", "medium", "high", "needs_live_data"]
    data_source: str = "synthetic project-supplied demo input"
    live_tracking: bool = False


class IntegrationState(BaseModel):
    integration: str
    status: Literal["roadmap_unavailable"] = "roadmap_unavailable"
    message: str


class ProcurementDashboard(BaseModel):
    mode: Literal["demo_mock"] = "demo_mock"
    live_data_available: bool = False
    disclaimer: str = "No live AIS, geospatial, vendor, or carrier tracking data is connected. This is a dashboard-compatible mock response."
    cards: list[ProcurementRiskCard]
    integrations: list[IntegrationState]


class ProcurementRiskService:
    def dashboard(self, items: list[ProcurementItemInput]) -> ProcurementDashboard:
        return ProcurementDashboard(
            cards=[risk_card(item) for item in items],
            integrations=[
                IntegrationState(integration="AIS vessel tracking", message="Roadmap: ingest licensed live vessel positions and ETA feeds."),
                IntegrationState(integration="Geospatial route risk", message="Roadmap: evaluate live route, port, and weather disruption layers."),
                IntegrationState(integration="Vendor/carrier tracking", message="Roadmap: receive authenticated vendor and carrier milestone updates."),
            ],
        )


class SupplierTier(BaseModel):
    tier: int = Field(ge=1, le=3)
    supplier: str
    location: str


class ShipmentMilestone(BaseModel):
    name: str
    planned_date: date
    forecast_date: date
    status: str


class AlternativeOption(BaseModel):
    name: str
    option_type: Literal["supplier", "route"]
    recovery_days: int = Field(ge=0)
    assumptions: list[str]


class ShipmentView(BaseModel):
    shipment_id: uuid.UUID
    reference: str
    equipment_id: str
    status: str
    origin: str
    destination: str
    planned_arrival: date
    forecast_arrival: date
    supplier_tiers: list[SupplierTier]
    milestones: list[ShipmentMilestone]
    schedule_task_id: str
    schedule_float_days: int
    critical_path: bool
    alternatives: list[AlternativeOption]
    synthetic_simulation: Literal[True] = True
    live_tracking: Literal[False] = False
    live_position: None = None


class ShipmentListResponse(BaseModel):
    synthetic_simulation: Literal[True] = True
    disclaimer: str = SYNTHETIC_DISCLAIMER
    shipments: list[ShipmentView]


class SyntheticRiskEventInput(BaseModel):
    event_type: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=1_000)
    occurred_at: datetime
    alert_generated_at: datetime
    forecast_delay_days: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_timestamps(self):
        if _utc(self.alert_generated_at) < _utc(self.occurred_at):
            raise ValueError("alert_generated_at cannot precede occurred_at")
        return self


class SyntheticRiskEventResponse(SyntheticRiskEventInput):
    event_id: uuid.UUID
    shipment_id: uuid.UUID
    alert_latency_minutes: int
    synthetic_simulation: Literal[True] = True
    disclaimer: str = SYNTHETIC_DISCLAIMER


class ShipmentRiskResponse(BaseModel):
    shipment_id: uuid.UUID
    reference: str
    equipment_id: str
    schedule_task_id: str
    forecast_delay_days: int
    available_schedule_float_days: int
    schedule_float_consumed_days: int
    critical_path_impact_days: int
    severity: Literal["on_track", "medium", "high", "critical"]
    alert_latency_minutes: int | None
    alternative_option: AlternativeOption | None
    risk_events: list[SyntheticRiskEventResponse]
    synthetic_simulation: Literal[True] = True
    disclaimer: str = SYNTHETIC_DISCLAIMER
    live_position: None = None


class AlternativeImpact(BaseModel):
    option: AlternativeOption
    residual_delay_days: int
    critical_path_impact_days: int
    severity: Literal["on_track", "medium", "high", "critical"]


class AlternativeComparisonResponse(BaseModel):
    shipment_id: uuid.UUID
    baseline_delay_days: int
    options: list[AlternativeImpact]
    recommended_option: AlternativeOption | None
    synthetic_simulation: Literal[True] = True
    disclaimer: str = SYNTHETIC_DISCLAIMER


class ImportedShipmentAssessment(BaseModel):
    shipment_id: uuid.UUID
    equipment_id: str
    vendor: str
    planned_date: date
    current_eta: date
    required_on_site_date: date
    status: str
    location: str
    eta_variance_days: int
    available_float_days: int
    schedule_exposure_days: int
    severity: Literal["on_track", "medium", "high", "critical"]
    affected_task: str | None
    first_alert_at: datetime | None
    alert_lead_time_days: int | None
    impact_event_id: uuid.UUID | None = None
    data_source: Literal["project_supplied_csv"] = "project_supplied_csv"
    live_tracking: Literal[False] = False


class ShipmentImportResponse(BaseModel):
    filename: str
    imported: int
    assessments: list[ImportedShipmentAssessment]
    live_tracking: Literal[False] = False


class ShipmentTimelineEvent(BaseModel):
    id: uuid.UUID
    event_type: str
    status: str
    location: str | None
    event_at: datetime
    details: dict


class ShipmentTimelineResponse(BaseModel):
    shipment_id: uuid.UUID
    project_id: uuid.UUID
    equipment_id: str
    events: list[ShipmentTimelineEvent]


REQUIRED_IMPORT_COLUMNS = {
    "equipment_id", "vendor", "planned_date", "current_eta",
    "required_on_site_date", "status", "location",
}


async def import_shipment_csv(
    session: AsyncSession,
    project_id: uuid.UUID,
    filename: str,
    content: bytes,
    now: datetime | None = None,
) -> ShipmentImportResponse:
    try:
        rows = list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))
    except UnicodeDecodeError as exc:
        raise IngestionError("invalid_shipment_csv", "Shipment CSV must be UTF-8") from exc
    if not rows or not REQUIRED_IMPORT_COLUMNS <= set(rows[0]):
        missing = sorted(REQUIRED_IMPORT_COLUMNS - set(rows[0] if rows else []))
        raise IngestionError("invalid_shipment_csv", f"Shipment CSV is empty or missing columns: {', '.join(missing)}")
    if len(rows) > 1_000:
        raise IngestionError("shipment_import_too_large", "Shipment CSV may contain at most 1000 rows")
    imported, at = [], now or datetime.now(UTC)
    for row_number, row in enumerate(rows, start=2):
        try:
            planned = date.fromisoformat(row["planned_date"])
            eta = date.fromisoformat(row["current_eta"])
            required = date.fromisoformat(row["required_on_site_date"])
        except (KeyError, ValueError) as exc:
            raise IngestionError("invalid_shipment_csv", f"Invalid date in shipment CSV row {row_number}") from exc
        equipment = await session.scalar(
            select(Equipment).where(
                Equipment.project_id == project_id,
                Equipment.equipment_id == row["equipment_id"].strip(),
            )
        )
        if not equipment:
            raise IngestionError("shipment_equipment_not_found", f"Equipment not found in row {row_number}", 404)
        task = await _delivery_task(session, project_id, equipment.equipment_id)
        vendor_name = row["vendor"].strip()
        vendor = await session.scalar(
            select(Vendor).where(
                Vendor.project_id == project_id,
                Vendor.equipment_id == equipment.equipment_id,
                Vendor.name == vendor_name,
            )
        )
        if not vendor:
            vendor = Vendor(
                project_id=project_id,
                equipment_id=equipment.equipment_id,
                name=vendor_name,
                metadata_json={"source": "project_supplied_csv"},
            )
            session.add(vendor)
            await session.flush()
        reference = f"csv:{filename}:{row_number}"
        shipment = await session.scalar(
            select(Shipment).where(Shipment.project_id == project_id, Shipment.reference == reference)
        )
        if not shipment:
            shipment = Shipment(
                project_id=project_id,
                equipment_id=equipment.equipment_id,
                vendor_id=vendor.id,
                reference=reference,
                status=row["status"].strip(),
                evidence={"source": "project_supplied_csv", "filename": filename, "row": row_number},
            )
            session.add(shipment)
        shipment.vendor_id = vendor.id
        shipment.planned_delivery = planned
        shipment.forecast_delivery = eta
        shipment.required_on_site_date = required
        shipment.status = row["status"].strip()
        shipment.location = row["location"].strip()
        shipment.schedule_task_id = task.task_id if task else None
        shipment.available_float_days = task.available_float_days if task else 0
        await session.flush()
        assessment = await assess_persisted_shipment(session, project_id, shipment.id, at)
        session.add(
            ShipmentEvent(
                project_id=project_id,
                shipment_id=shipment.id,
                equipment_id=shipment.equipment_id,
                event_type="CSV_IMPORTED",
                status=shipment.status,
                location=shipment.location,
                event_at=at,
                details={
                    "filename": filename,
                    "row": row_number,
                    "eta_variance_days": assessment.eta_variance_days,
                    "schedule_exposure_days": assessment.schedule_exposure_days,
                },
            )
        )
        if assessment.severity != "on_track" and shipment.first_alert_at is None:
            shipment.first_alert_at = at
            session.add(
                ShipmentEvent(
                    project_id=project_id,
                    shipment_id=shipment.id,
                    equipment_id=shipment.equipment_id,
                    event_type="RISK_ALERT",
                    status=assessment.severity,
                    location=shipment.location,
                    event_at=at,
                    details=assessment.model_dump(mode="json"),
                )
            )
            assessment.first_alert_at = at
            assessment.alert_lead_time_days = max(0, (required - at.date()).days)
            assessment.impact_event_id = await _ensure_delivery_impact(
                session, project_id, shipment, assessment, filename, row_number, at
            )
        imported.append(assessment)
    await session.commit()
    return ShipmentImportResponse(filename=filename, imported=len(imported), assessments=imported)


async def assess_persisted_shipment(
    session: AsyncSession,
    project_id: uuid.UUID,
    shipment_id: uuid.UUID,
    now: datetime | None = None,
) -> ImportedShipmentAssessment | None:
    shipment = await session.scalar(
        select(Shipment).where(Shipment.id == shipment_id, Shipment.project_id == project_id)
    )
    if not shipment or not all((shipment.planned_delivery, shipment.forecast_delivery, shipment.required_on_site_date)):
        return None
    vendor = await session.get(Vendor, shipment.vendor_id) if shipment.vendor_id else None
    variance = (shipment.forecast_delivery - shipment.planned_delivery).days
    exposure = max(
        0,
        (shipment.forecast_delivery - shipment.required_on_site_date).days - shipment.available_float_days,
    )
    severity = schedule_exposure_severity(variance, exposure)
    alert_at = shipment.first_alert_at
    impact = await session.scalar(
        select(ImpactEvent).where(
            ImpactEvent.project_id == project_id,
            ImpactEvent.equipment_id == shipment.equipment_id,
            ImpactEvent.type == "DELIVERY_RISK",
            ImpactEvent.source_id == str(shipment.id),
        )
    )
    return ImportedShipmentAssessment(
        shipment_id=shipment.id,
        equipment_id=shipment.equipment_id,
        vendor=vendor.name if vendor else "Unknown",
        planned_date=shipment.planned_delivery,
        current_eta=shipment.forecast_delivery,
        required_on_site_date=shipment.required_on_site_date,
        status=shipment.status,
        location=shipment.location or "Unknown",
        eta_variance_days=variance,
        available_float_days=shipment.available_float_days,
        schedule_exposure_days=exposure,
        severity=severity,
        affected_task=shipment.schedule_task_id,
        first_alert_at=alert_at,
        alert_lead_time_days=max(0, (shipment.required_on_site_date - alert_at.date()).days) if alert_at else None,
        impact_event_id=impact.id if impact else None,
    )


async def imported_shipment_assessments(
    session: AsyncSession, project_id: uuid.UUID, alerts_only: bool = False
) -> list[ImportedShipmentAssessment]:
    shipments = list((await session.scalars(
        select(Shipment)
        .where(Shipment.project_id == project_id, Shipment.required_on_site_date.is_not(None))
        .order_by(Shipment.reference)
    )).all())
    results = [await assess_persisted_shipment(session, project_id, item.id) for item in shipments]
    return [item for item in results if item and (not alerts_only or item.severity != "on_track")]


async def shipment_timeline(
    session: AsyncSession, project_id: uuid.UUID, shipment_id: uuid.UUID
) -> ShipmentTimelineResponse | None:
    shipment = await session.scalar(
        select(Shipment).where(Shipment.id == shipment_id, Shipment.project_id == project_id)
    )
    if not shipment:
        return None
    events = list((await session.scalars(
        select(ShipmentEvent)
        .where(ShipmentEvent.project_id == project_id, ShipmentEvent.shipment_id == shipment_id)
        .order_by(ShipmentEvent.event_at)
    )).all())
    events.sort(key=lambda item: (item.event_at, 0 if item.event_type == "CSV_IMPORTED" else 1, str(item.id)))
    return ShipmentTimelineResponse(
        shipment_id=shipment.id,
        project_id=project_id,
        equipment_id=shipment.equipment_id,
        events=[ShipmentTimelineEvent.model_validate(item, from_attributes=True) for item in events],
    )


async def _delivery_task(session: AsyncSession, project_id: uuid.UUID, equipment_id: str) -> ScheduleTask | None:
    tasks = list((await session.scalars(
        select(ScheduleTask)
        .where(ScheduleTask.project_id == project_id, ScheduleTask.equipment_id == equipment_id)
        .order_by(ScheduleTask.task_id)
    )).all())
    return next((item for item in tasks if "deliver" in item.name.lower()), tasks[0] if tasks else None)


async def _ensure_delivery_impact(
    session, project_id, shipment, assessment, filename, row_number, at
) -> uuid.UUID:
    existing = await session.scalar(
        select(ImpactEvent).where(
            ImpactEvent.project_id == project_id,
            ImpactEvent.equipment_id == shipment.equipment_id,
            ImpactEvent.type == "DELIVERY_RISK",
            ImpactEvent.source_id == str(shipment.id),
        )
    )
    if existing:
        return existing.id
    from app.impact_chain import EvidenceRecordInput, ImpactEventCreate, PropagationAssumptions, propagate_event

    await propagate_event(
        session,
        project_id,
        shipment.equipment_id,
        ImpactEventCreate(
            type="DELIVERY_RISK",
            source_id=str(shipment.id),
            severity=assessment.severity,
            confidence=1,
            timestamp=at,
            assumptions=PropagationAssumptions(
                schedule_impact_days=assessment.schedule_exposure_days,
                commissioning_impact_days=0,
            ),
            evidence=[EvidenceRecordInput(
                claim=f"Shipment ETA creates {assessment.schedule_exposure_days} days of schedule exposure.",
                document=filename,
                page=row_number,
                clause="shipment CSV row",
                excerpt=(
                    f"equipment_id={shipment.equipment_id}; current_eta={assessment.current_eta}; "
                    f"required_on_site_date={assessment.required_on_site_date}; "
                    f"available_float_days={assessment.available_float_days}"
                ),
                model_version="deterministic-supply-chain-v1",
                verification_status="UNVERIFIED",
            )],
        ),
    )
    return (await session.scalar(
        select(ImpactEvent).where(
            ImpactEvent.project_id == project_id,
            ImpactEvent.equipment_id == shipment.equipment_id,
            ImpactEvent.type == "DELIVERY_RISK",
            ImpactEvent.source_id == str(shipment.id),
        )
    )).id


async def seed_synthetic_supply_chain(
    session: AsyncSession, project_id: uuid.UUID, source: Path
) -> ShipmentListResponse:
    data = json.loads(source.read_text())
    for item in data["shipments"]:
        if not await session.scalar(
            select(Equipment).where(
                Equipment.project_id == project_id,
                Equipment.equipment_id == item["equipment_id"],
            )
        ):
            session.add(
                Equipment(
                    project_id=project_id,
                    equipment_id=item["equipment_id"],
                    name=item["equipment_name"],
                    equipment_type=item["equipment_type"],
                    metadata_json={"synthetic_simulation": True},
                )
            )
        vendors = []
        for supplier in item["supplier_tiers"]:
            vendor = await session.scalar(
                select(Vendor).where(
                    Vendor.project_id == project_id,
                    Vendor.equipment_id == item["equipment_id"],
                    Vendor.name == supplier["supplier"],
                )
            )
            if not vendor:
                vendor = Vendor(
                    project_id=project_id,
                    equipment_id=item["equipment_id"],
                    name=supplier["supplier"],
                    approval_status="synthetic",
                    metadata_json={**supplier, "synthetic_simulation": True},
                )
                session.add(vendor)
                await session.flush()
            vendors.append(vendor)
        shipment = await session.scalar(
            select(Shipment).where(
                Shipment.project_id == project_id,
                Shipment.reference == item["reference"],
            )
        )
        evidence = {
            key: item[key]
            for key in (
                "origin", "destination", "supplier_tiers", "milestones", "schedule_task_id",
                "schedule_float_days", "critical_path", "alternatives",
            )
        }
        evidence.update(synthetic_simulation=True, live_tracking=False, live_position=None)
        if not shipment:
            shipment = Shipment(
                project_id=project_id,
                equipment_id=item["equipment_id"],
                vendor_id=vendors[0].id,
                reference=item["reference"],
                status=item["status"],
                evidence=evidence,
            )
            session.add(shipment)
        shipment.status = item["status"]
        shipment.planned_delivery = date.fromisoformat(item["planned_arrival"])
        shipment.forecast_delivery = date.fromisoformat(item["forecast_arrival"])
        shipment.evidence = evidence
        await session.flush()
        existing_events = {
            event.payload.get("event_reference")
            for event in (
                await session.scalars(
                    select(AuditEvent).where(
                        AuditEvent.project_id == project_id,
                        AuditEvent.event_type == "synthetic_shipment_risk_event",
                    )
                )
            ).all()
        }
        for event in item.get("risk_events", []):
            if event["event_reference"] not in existing_events:
                session.add(
                    AuditEvent(
                        project_id=project_id,
                        event_type="synthetic_shipment_risk_event",
                        payload={**event, "shipment_id": str(shipment.id), "synthetic_simulation": True},
                    )
                )
    await session.commit()
    return await list_shipments(session, project_id)


async def reset_synthetic_supply_chain(
    session: AsyncSession, project_id: uuid.UUID, source: Path
) -> ShipmentListResponse:
    """Restore synthetic shipment events without touching project documents or live records."""
    await session.execute(
        delete(AuditEvent).where(
            AuditEvent.project_id == project_id,
            AuditEvent.event_type == "synthetic_shipment_risk_event",
        )
    )
    await session.commit()
    return await seed_synthetic_supply_chain(session, project_id, source)


async def list_shipments(session: AsyncSession, project_id: uuid.UUID) -> ShipmentListResponse:
    shipments = (
        await session.scalars(
            select(Shipment).where(Shipment.project_id == project_id).order_by(Shipment.reference)
        )
    ).all()
    return ShipmentListResponse(
        shipments=[shipment_view(item) for item in shipments if (item.evidence or {}).get("synthetic_simulation")]
    )


async def inject_risk_event(
    session: AsyncSession,
    project_id: uuid.UUID,
    shipment_id: uuid.UUID,
    payload: SyntheticRiskEventInput,
) -> SyntheticRiskEventResponse | None:
    shipment = await _shipment(session, project_id, shipment_id)
    if not shipment:
        return None
    event = AuditEvent(
        project_id=project_id,
        event_type="synthetic_shipment_risk_event",
        payload={
            **payload.model_dump(mode="json"),
            "shipment_id": str(shipment.id),
            "synthetic_simulation": True,
        },
    )
    session.add(event)
    await session.commit()
    return risk_event_response(event)


async def shipment_risk(
    session: AsyncSession, project_id: uuid.UUID, shipment_id: uuid.UUID
) -> ShipmentRiskResponse | None:
    shipment = await _shipment(session, project_id, shipment_id)
    if not shipment:
        return None
    events = await _risk_events(session, project_id, shipment_id)
    view = shipment_view(shipment)
    base_delay = max(0, (view.forecast_arrival - view.planned_arrival).days)
    delay = max([base_delay, *(event.forecast_delay_days for event in events)])
    consumed = min(delay, view.schedule_float_days)
    impact = max(0, delay - view.schedule_float_days)
    alternatives = alternative_impacts(view, delay)
    return ShipmentRiskResponse(
        shipment_id=shipment.id,
        reference=shipment.reference,
        equipment_id=shipment.equipment_id,
        schedule_task_id=view.schedule_task_id,
        forecast_delay_days=delay,
        available_schedule_float_days=view.schedule_float_days,
        schedule_float_consumed_days=consumed,
        critical_path_impact_days=impact,
        severity=risk_severity(delay, impact),
        alert_latency_minutes=events[-1].alert_latency_minutes if events else None,
        alternative_option=alternatives[0].option if alternatives else None,
        risk_events=events,
    )


async def compare_alternatives(
    session: AsyncSession, project_id: uuid.UUID, shipment_id: uuid.UUID
) -> AlternativeComparisonResponse | None:
    shipment = await _shipment(session, project_id, shipment_id)
    risk = await shipment_risk(session, project_id, shipment_id) if shipment else None
    if not shipment or not risk:
        return None
    options = alternative_impacts(shipment_view(shipment), risk.forecast_delay_days)
    return AlternativeComparisonResponse(
        shipment_id=shipment.id,
        baseline_delay_days=risk.forecast_delay_days,
        options=options,
        recommended_option=options[0].option if options else None,
    )


def shipment_view(shipment: Shipment) -> ShipmentView:
    evidence = shipment.evidence or {}
    return ShipmentView(
        shipment_id=shipment.id,
        reference=shipment.reference,
        equipment_id=shipment.equipment_id,
        status=shipment.status,
        origin=evidence["origin"],
        destination=evidence["destination"],
        planned_arrival=shipment.planned_delivery,
        forecast_arrival=shipment.forecast_delivery,
        supplier_tiers=evidence["supplier_tiers"],
        milestones=evidence["milestones"],
        schedule_task_id=evidence["schedule_task_id"],
        schedule_float_days=evidence["schedule_float_days"],
        critical_path=evidence["critical_path"],
        alternatives=evidence.get("alternatives", []),
    )


def alternative_impacts(view: ShipmentView, delay: int) -> list[AlternativeImpact]:
    results = []
    for option in view.alternatives:
        residual = max(0, delay - option.recovery_days)
        impact = max(0, residual - view.schedule_float_days)
        results.append(
            AlternativeImpact(
                option=option,
                residual_delay_days=residual,
                critical_path_impact_days=impact,
                severity=risk_severity(residual, impact),
            )
        )
    return sorted(results, key=lambda item: (item.critical_path_impact_days, item.residual_delay_days, item.option.name))


def risk_severity(delay: int, critical_impact: int) -> Literal["on_track", "medium", "high", "critical"]:
    if delay <= 0:
        return "on_track"
    if critical_impact <= 0:
        return "medium"
    return "critical" if critical_impact > 14 else "high"


def schedule_exposure_severity(
    eta_variance_days: int, schedule_exposure_days: int
) -> Literal["on_track", "medium", "high", "critical"]:
    if schedule_exposure_days > 14:
        return "critical"
    if schedule_exposure_days > 0:
        return "high"
    return "medium" if eta_variance_days > 0 else "on_track"


async def _shipment(session: AsyncSession, project_id: uuid.UUID, shipment_id: uuid.UUID) -> Shipment | None:
    shipment = await session.scalar(
        select(Shipment).where(Shipment.id == shipment_id, Shipment.project_id == project_id)
    )
    return shipment if shipment and (shipment.evidence or {}).get("synthetic_simulation") else None


async def _risk_events(
    session: AsyncSession, project_id: uuid.UUID, shipment_id: uuid.UUID
) -> list[SyntheticRiskEventResponse]:
    events = (
        await session.scalars(
            select(AuditEvent)
            .where(AuditEvent.project_id == project_id, AuditEvent.event_type == "synthetic_shipment_risk_event")
            .order_by(AuditEvent.created_at, AuditEvent.id)
        )
    ).all()
    responses = [
        risk_event_response(event)
        for event in events
        if event.payload.get("shipment_id") == str(shipment_id)
    ]
    return sorted(responses, key=lambda event: _utc(event.occurred_at))


def risk_event_response(event: AuditEvent) -> SyntheticRiskEventResponse:
    payload = SyntheticRiskEventInput.model_validate(event.payload)
    return SyntheticRiskEventResponse(
        **payload.model_dump(),
        event_id=event.id,
        shipment_id=uuid.UUID(event.payload["shipment_id"]),
        alert_latency_minutes=int((_utc(payload.alert_generated_at) - _utc(payload.occurred_at)).total_seconds() // 60),
    )


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def risk_card(item: ProcurementItemInput) -> ProcurementRiskCard:
    if not item.forecast_delivery:
        return ProcurementRiskCard(**item.model_dump(), delay_days=None, risk_level="needs_live_data")
    delay_days = (item.forecast_delivery - item.planned_delivery).days
    risk_level: Literal["on_track", "medium", "high", "needs_live_data"] = "on_track" if delay_days <= 0 else "medium" if delay_days <= 14 else "high"
    return ProcurementRiskCard(**item.model_dump(), delay_days=delay_days, risk_level=risk_level)
