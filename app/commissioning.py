import re
import uuid
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.equipment import document_equipment_id
from app.ingestion import Citation, IngestionError, extract_document
from app.models import (
    AuditEvent,
    CommissioningStep,
    CommissioningTestRecord,
    ComplianceFinding,
    Document,
    Equipment,
    NonConformance,
    ScheduleTask,
    Shipment,
)

TestStatus = Literal["pass", "fail", "needs_review"]
StepStatus = Literal["NOT_STARTED", "READY", "BLOCKED", "PASS", "FAIL", "NEEDS_REVIEW"]


class ProcedureStep(BaseModel):
    index: int
    equipment_id: str
    prerequisite: list[str]
    instruction: str
    acceptance_criterion: str
    observation: str | None = None
    evidence: list[str]
    status: StepStatus
    reviewer_note: str | None = None
    citation: Citation


class CommissioningProcedure(BaseModel):
    document_id: uuid.UUID
    filename: str
    equipment_id: str
    steps: list[ProcedureStep]


class EngineerObservation(BaseModel):
    step_index: int = Field(ge=1)
    observation: str = Field(min_length=1, max_length=4_000)
    evidence: list[str] = Field(default_factory=list, max_length=20)
    reviewer_note: str | None = Field(default=None, max_length=2_000)
    prerequisites_met: bool = True


class StepAssessment(ProcedureStep):
    pass


class NonConformanceResponse(BaseModel):
    id: uuid.UUID
    step_index: int
    criterion: str
    observation: str
    citation: Citation
    status: str


class TestRecordResponse(BaseModel):
    id: uuid.UUID
    procedure_document_id: uuid.UUID
    status: TestStatus
    completed_steps: int
    total_steps: int
    coverage_percent: float
    automation_coverage_percent: float
    steps: list[StepAssessment]
    non_conformances: list[NonConformanceResponse]


class ReadinessRule(BaseModel):
    rule: str
    weight: int
    satisfied: bool
    score: int
    evidence: str


class EquipmentReadiness(BaseModel):
    project_id: uuid.UUID
    equipment_id: str
    score: int
    status: Literal["READY", "NEEDS_REVIEW", "NOT_READY"]
    rules: list[ReadinessRule]


class CommissioningService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def procedure(self, document: Document) -> CommissioningProcedure:
        if document.document_type != "commissioning_record":
            raise IngestionError("invalid_procedure_document", "Select a commissioning procedure document")
        steps, section, index = [], "General", 0
        pages = extract_document(Path(document.storage_path), self.settings).pages
        equipment_id = document_equipment_id(document) or _equipment_id(
            f"{document.filename}\n" + "\n".join(page.text for page in pages)
        )
        if not equipment_id:
            raise IngestionError("missing_equipment", "Commissioning procedure requires an equipment_id")
        for page in pages:
            for line in page.text.splitlines():
                if re.match(r"^#{1,6}\s+", line):
                    section = line.lstrip("# ").strip()
                elif match := re.match(r"^\s*\d+\.\s+(.+)", line):
                    index += 1
                    instruction = match.group(1).strip()
                    citation = Citation(document_id=document.id, filename=document.filename, page=page.page, section=section)
                    precondition = "precondition" in section.lower()
                    steps.append(
                        ProcedureStep(
                            index=index,
                            equipment_id=equipment_id,
                            prerequisite=[] if precondition else ["All procedure preconditions are complete"],
                            instruction=instruction,
                            acceptance_criterion=instruction,
                            evidence=[f"{document.filename}, page {page.page}, {section}"],
                            status="READY" if precondition else "BLOCKED",
                            citation=citation,
                        )
                    )
        if not steps:
            raise IngestionError("invalid_procedure", "Commissioning procedure contains no numbered steps")
        return CommissioningProcedure(
            document_id=document.id, filename=document.filename, equipment_id=equipment_id, steps=steps
        )

    async def record(
        self, session: AsyncSession, document: Document, observations: list[EngineerObservation]
    ) -> TestRecordResponse:
        procedure = self.procedure(document)
        observation_map = {item.step_index: item for item in observations}
        if len(observation_map) != len(observations) or any(index > len(procedure.steps) for index in observation_map):
            raise IngestionError("invalid_observation", "Each observation must reference one unique procedure step")
        steps = []
        for step in procedure.steps:
            observation = observation_map.get(step.index)
            if not observation:
                steps.append(StepAssessment(**step.model_dump()))
                continue
            status: StepStatus = "BLOCKED" if not observation.prerequisites_met else assess(step, observation.observation)
            steps.append(
                StepAssessment(
                    **step.model_dump(exclude={"observation", "evidence", "status", "reviewer_note"}),
                    observation=observation.observation,
                    evidence=[*step.evidence, *observation.evidence],
                    status=status,
                    reviewer_note=observation.reviewer_note,
                )
            )
        completed = len(observation_map)
        status: TestStatus = (
            "fail" if any(step.status == "FAIL" for step in steps)
            else "pass" if all(step.status == "PASS" for step in steps)
            else "needs_review"
        )
        record = CommissioningTestRecord(
            project_id=document.project_id,
            equipment_id=procedure.equipment_id,
            procedure_document_id=document.id,
            status=status,
            completed_steps=completed,
            total_steps=len(steps),
            coverage_percent=round(100 * completed / len(steps), 1),
            steps=[step.model_dump(mode="json") for step in steps],
        )
        session.add(record)
        await session.flush()
        non_conformances = [
            NonConformance(
                project_id=document.project_id,
                equipment_id=procedure.equipment_id,
                test_record_id=record.id,
                procedure_document_id=document.id,
                step_index=step.index,
                criterion=step.acceptance_criterion,
                observation=step.observation or "",
                citation=step.citation.model_dump(mode="json"),
            )
            for step in steps
            if step.status == "FAIL"
        ]
        session.add_all(non_conformances)
        stored_steps = (
            await session.scalars(
                select(CommissioningStep).where(
                    CommissioningStep.project_id == document.project_id,
                    CommissioningStep.procedure_document_id == document.id,
                )
            )
        ).all()
        assessments = {step.index: step for step in steps}
        for stored_step in stored_steps:
            assessment = assessments.get(stored_step.step_index)
            if assessment:
                stored_step.test_record_id = record.id
                stored_step.observation = assessment.observation
                stored_step.status = assessment.status
                stored_step.evidence = assessment.evidence
                stored_step.reviewer_note = assessment.reviewer_note
        session.add(
            AuditEvent(
                project_id=document.project_id,
                event_type="commissioning_test_recorded",
                payload={"test_record_id": str(record.id), "status": status, "coverage_percent": record.coverage_percent},
            )
        )
        await session.commit()
        return test_record_response(record, non_conformances)

    async def readiness(
        self, session: AsyncSession, project_id: uuid.UUID, equipment_id: str
    ) -> EquipmentReadiness | None:
        equipment = await session.scalar(
            select(Equipment).where(Equipment.project_id == project_id, Equipment.equipment_id == equipment_id)
        )
        if not equipment:
            return None
        documents = list((await session.scalars(
            select(Document).where(Document.project_id == project_id, Document.equipment_id == equipment_id)
        )).all())
        approval_documents = [
            item for item in documents
            if item.document_type in {"specification", "submittal", "commissioning_record"}
        ]
        findings = list((await session.scalars(
            select(ComplianceFinding).where(
                ComplianceFinding.project_id == project_id, ComplianceFinding.equipment_id == equipment_id
            )
        )).all())
        shipments = list((await session.scalars(
            select(Shipment).where(Shipment.project_id == project_id, Shipment.equipment_id == equipment_id)
        )).all())
        installation = list((await session.scalars(
            select(ScheduleTask).where(
                ScheduleTask.project_id == project_id,
                ScheduleTask.equipment_id == equipment_id,
                ScheduleTask.name.ilike("%install%"),
            )
        )).all())
        ncrs = list((await session.scalars(
            select(NonConformance).where(
                NonConformance.project_id == project_id,
                NonConformance.equipment_id == equipment_id,
                NonConformance.status == "open",
            )
        )).all())
        steps = list((await session.scalars(
            select(CommissioningStep).where(
                CommissioningStep.project_id == project_id,
                CommissioningStep.equipment_id == equipment_id,
            )
        )).all())
        prerequisite_steps = [item for item in steps if item.step_index <= 3]
        values = [
            ("document_approval", 15, bool(approval_documents) and all(_approved(item) for item in approval_documents), f"{sum(_approved(item) for item in approval_documents)}/{len(approval_documents)} required documents approved"),
            ("compliance", 20, not any(item.status in {"NON_COMPLIANT", "NEEDS_REVIEW", "MISSING_INFORMATION"} for item in findings), f"{len(findings)} compliance findings checked"),
            ("delivery", 15, bool(shipments) and all(item.status.lower() in {"complete", "delivered", "on_track"} for item in shipments), f"{sum(item.status.lower() in {'complete', 'delivered', 'on_track'} for item in shipments)}/{len(shipments)} shipments complete"),
            ("installation", 20, bool(installation) and all(item.status.lower() == "complete" for item in installation), f"{sum(item.status.lower() == 'complete' for item in installation)}/{len(installation)} installation tasks complete"),
            ("open_critical_issues", 20, not ncrs and not any(item.status == "NON_COMPLIANT" and item.severity.lower() == "critical" for item in findings), f"{len(ncrs)} open NCRs"),
            ("test_prerequisites", 10, len(prerequisite_steps) >= 3 and all(item.status.upper() == "PASS" for item in prerequisite_steps), f"{sum(item.status.upper() == 'PASS' for item in prerequisite_steps)}/3 prerequisite steps passed"),
        ]
        rules = [ReadinessRule(rule=name, weight=weight, satisfied=passed, score=weight if passed else 0, evidence=evidence) for name, weight, passed, evidence in values]
        score = sum(item.score for item in rules)
        return EquipmentReadiness(
            project_id=project_id,
            equipment_id=equipment_id,
            score=score,
            status="READY" if score == 100 else "NEEDS_REVIEW" if score >= 70 else "NOT_READY",
            rules=rules,
        )


def assess(step: ProcedureStep, observation: str | None) -> StepStatus:
    if not observation:
        return "NEEDS_REVIEW"
    text = observation.lower()
    if any(token in text for token in ("fail", "does not", "not verified", "missing", "unable")):
        return "FAIL"
    expected, observed = _measurement(step.acceptance_criterion), _measurement(observation)
    criterion = step.acceptance_criterion.lower()
    if expected and observed and any(token in criterion for token in ("minimum", "not less", "maintain", "supports")):
        return "PASS" if observed >= expected else "FAIL"
    if any(token in text for token in ("pass", "verified", "confirmed", "complete", "meets")):
        return "PASS"
    return "NEEDS_REVIEW"


def _measurement(text: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:-|\s)(?:minutes?|mins?|mm)\b", text, re.IGNORECASE)
    if not match:
        return None
    value, unit = float(match.group(1)), match.group(0).lower()
    return value if "mm" in unit else value


def test_record_response(record: CommissioningTestRecord, non_conformances: list[NonConformance]) -> TestRecordResponse:
    return TestRecordResponse(
        id=record.id,
        procedure_document_id=record.procedure_document_id,
        status=record.status,
        completed_steps=record.completed_steps,
        total_steps=record.total_steps,
        coverage_percent=record.coverage_percent,
        automation_coverage_percent=round(
            100 * sum(step["status"] in {"PASS", "FAIL"} for step in record.steps) / max(record.total_steps, 1), 1
        ),
        steps=[StepAssessment.model_validate(step) for step in record.steps],
        non_conformances=[
            NonConformanceResponse(
                id=item.id,
                step_index=item.step_index,
                criterion=item.criterion,
                observation=item.observation,
                citation=Citation.model_validate(item.citation),
                status=item.status,
            )
            for item in non_conformances
        ],
    )


async def stored_test_record(session: AsyncSession, project_id: uuid.UUID, record_id: uuid.UUID) -> TestRecordResponse | None:
    record = await session.scalar(
        select(CommissioningTestRecord).where(CommissioningTestRecord.id == record_id, CommissioningTestRecord.project_id == project_id)
    )
    if not record:
        return None
    findings = (await session.scalars(select(NonConformance).where(NonConformance.test_record_id == record.id))).all()
    return test_record_response(record, findings)


def _approved(document: Document) -> bool:
    metadata = document.metadata_json or {}
    return str(metadata.get("approval_status") or metadata.get("revision_status") or "").lower() in {
        "approved", "current"
    }


def _equipment_id(filename: str) -> str | None:
    match = re.search(r"\b(?:UPS-[A-Z][A-Z0-9]*|CRAC-\d+|SWGR-[A-Z][A-Z0-9]*)\b", filename, re.IGNORECASE)
    return match.group(0).upper() if match else None
