import hashlib
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.commissioning import CommissioningService, EngineerObservation
from app.config import Settings
from app.models import (
    Base,
    CommissioningStep,
    CommissioningTestRecord,
    Document,
    Equipment,
    NonConformance,
    Project,
    ScheduleTask,
    Shipment,
)

DATASET = Path(__file__).parents[1] / "data" / "synthetic_epc" / "commissioning"


def document(project_id: uuid.UUID, filename: str) -> Document:
    path = DATASET / filename
    return Document(
        id=uuid.uuid4(),
        project_id=project_id,
        equipment_id={
            "UPS_Procedure_Template.md": "UPS-A",
            "CRAC_Procedure_Template.md": "CRAC-1",
            "Switchgear_Procedure_Template.md": "SWGR-A",
        }[filename],
        filename=filename,
        storage_path=str(path),
        document_type="commissioning_record",
        status="completed",
        content_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        mime_type="text/markdown",
        size_bytes=path.stat().st_size,
        metadata_json={"approval_status": "approved"},
    )


def service(tmp_path: Path) -> CommissioningService:
    return CommissioningService(Settings(upload_dir=str(tmp_path), graph_dir=str(tmp_path)))


def test_stored_templates_generate_21_structured_steps(tmp_path: Path) -> None:
    project_id = uuid.uuid4()
    procedures = [
        service(tmp_path).procedure(document(project_id, filename))
        for filename in (
            "UPS_Procedure_Template.md",
            "CRAC_Procedure_Template.md",
            "Switchgear_Procedure_Template.md",
        )
    ]
    assert len(procedures) >= 2
    assert 20 <= sum(len(item.steps) for item in procedures) <= 30
    step = procedures[0].steps[0]
    assert step.equipment_id == "UPS-A"
    assert step.status == "READY"
    assert step.observation is None and step.reviewer_note is None
    assert step.instruction and step.acceptance_criterion and step.evidence
    assert procedures[0].steps[3].status == "BLOCKED"
    assert procedures[0].steps[3].prerequisite == ["All procedure preconditions are complete"]


@pytest.mark.asyncio
async def test_blocked_pass_fail_ncr_and_automation_coverage(tmp_path: Path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'commissioning-qa.db'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as session:
            project = Project(name="Commissioning QA")
            session.add(project)
            await session.flush()
            procedure_document = document(project.id, "UPS_Procedure_Template.md")
            session.add(procedure_document)
            await session.commit()
            procedure = service(tmp_path).procedure(procedure_document)
            battery = next(step for step in procedure.steps if "15-minute design autonomy" in step.instruction)
            result = await service(tmp_path).record(
                session,
                procedure_document,
                [
                    EngineerObservation(
                        step_index=1,
                        observation="Inspection attempted.",
                        prerequisites_met=False,
                        reviewer_note="Await approved calculation.",
                    ),
                    EngineerObservation(step_index=2, observation="Verified complete.", evidence=["Inspection IR-01"]),
                    EngineerObservation(step_index=battery.index, observation="Battery autonomy demonstrated for 10 minutes."),
                ],
            )
            assert result.status == "fail"
            assert result.steps[0].status == "BLOCKED"
            assert result.steps[1].status == "PASS"
            assert result.steps[battery.index - 1].status == "FAIL"
            assert result.steps[0].reviewer_note == "Await approved calculation."
            assert result.completed_steps == 3 and result.coverage_percent == 33.3
            assert result.automation_coverage_percent == 22.2
            assert len(result.non_conformances) == 1
            assert len((await session.scalars(select(NonConformance))).all()) == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_all_steps_pass_and_readiness_recalculates_for_open_ncr(tmp_path: Path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'readiness.db'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    commissioning = service(tmp_path)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as session:
            project = Project(name="Readiness")
            session.add(project)
            await session.flush()
            procedure_document = document(project.id, "UPS_Procedure_Template.md")
            session.add_all(
                [
                    Equipment(project_id=project.id, equipment_id="UPS-A", name="UPS-A", equipment_type="UPS"),
                    procedure_document,
                ]
            )
            await session.flush()
            procedure = commissioning.procedure(procedure_document)
            session.add(
                Shipment(
                    project_id=project.id,
                    equipment_id="UPS-A",
                    reference="READINESS-DELIVERY",
                    status="delivered",
                    evidence={"synthetic_simulation": True},
                )
            )
            session.add(
                ScheduleTask(
                    project_id=project.id,
                    equipment_id="UPS-A",
                    document_id=procedure_document.id,
                    task_id="INSTALL-UPS-A",
                    name="Install UPS-A",
                    status="complete",
                    dependencies=[],
                    citation={},
                )
            )
            for step in procedure.steps[:3]:
                session.add(
                    CommissioningStep(
                        project_id=project.id,
                        equipment_id="UPS-A",
                        procedure_document_id=procedure_document.id,
                        step_index=step.index,
                        prerequisite=step.prerequisite,
                        instruction=step.instruction,
                        acceptance_criterion=step.acceptance_criterion,
                        evidence=step.evidence,
                        status="PASS",
                        citation=step.citation.model_dump(mode="json"),
                    )
                )
            await session.commit()

            ready = await commissioning.readiness(session, project.id, "UPS-A")
            assert ready and ready.score == 100 and ready.status == "READY"
            assert sum(rule.weight for rule in ready.rules) == 100

            passed = await commissioning.record(
                session,
                procedure_document,
                [EngineerObservation(step_index=step.index, observation="Verified complete.") for step in procedure.steps],
            )
            assert passed.status == "pass" and passed.automation_coverage_percent == 100
            record = await session.get(CommissioningTestRecord, passed.id)
            ncr = NonConformance(
                project_id=project.id,
                equipment_id="UPS-A",
                test_record_id=record.id,
                procedure_document_id=procedure_document.id,
                step_index=1,
                criterion="Synthetic critical issue",
                observation="Open issue",
                citation={},
            )
            session.add(ncr)
            await session.commit()
            not_ready = await commissioning.readiness(session, project.id, "UPS-A")
            assert not_ready and not_ready.score == 80 and not_ready.status == "NEEDS_REVIEW"
            ncr.status = "closed"
            await session.commit()
            recalculated = await commissioning.readiness(session, project.id, "UPS-A")
            assert recalculated and recalculated.score == 100 and recalculated.status == "READY"
    finally:
        await engine.dispose()
