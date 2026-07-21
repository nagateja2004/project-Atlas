import asyncio
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.main import app
from app.models import (
    Base,
    CommissioningStep,
    CommissioningTestRecord,
    ComplianceFinding,
    Document,
    Equipment,
    EvidenceLink,
    MitigationScenario,
    NonConformance,
    Project,
    RFI,
    Requirement,
    ScheduleTask,
    Shipment,
    Vendor,
)


def test_equipment_digital_thread_returns_all_entities_without_crossing_projects(tmp_path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'equipment-thread.db'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def seed() -> tuple[uuid.UUID, uuid.UUID]:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as session:
            first, second = Project(name="First"), Project(name="Second")
            session.add_all([first, second])
            await session.flush()
            for project, marker in ((first, "first"), (second, "second")):
                equipment = Equipment(project_id=project.id, equipment_id="UPS-A", name=f"UPS-A {marker}", equipment_type="UPS", metadata_json={})
                specification = _document(project.id, "UPS-A", f"{marker}-spec.md", "specification", "A", "approved")
                submittal = _document(project.id, "UPS-A", f"{marker}-submittal.md", "submittal", "B", "approved")
                procedure = _document(project.id, "UPS-A", f"{marker}-procedure.md", "commissioning_record", "1", "approved")
                session.add_all([equipment, specification, submittal, procedure])
                await session.flush()
                citation = {"document_id": str(specification.id), "filename": specification.filename, "page": 2, "section": "Battery"}
                vendor = Vendor(project_id=project.id, equipment_id="UPS-A", name=f"{marker} vendor", approval_status="approved", metadata_json={})
                session.add(vendor)
                await session.flush()
                record = CommissioningTestRecord(project_id=project.id, equipment_id="UPS-A", procedure_document_id=procedure.id, status="fail", completed_steps=1, total_steps=1, coverage_percent=100, steps=[])
                session.add(record)
                await session.flush()
                session.add_all(
                    [
                        Requirement(project_id=project.id, equipment_id="UPS-A", document_id=specification.id, parameter="2.2.4", required_value="15 minutes", normalized_unit="minutes", revision="A", approval_status="approved", citation=citation),
                        ComplianceFinding(project_id=project.id, equipment_id="UPS-A", specification_document_id=specification.id, submittal_document_id=submittal.id, requirement_key="battery_autonomy", requirement="UPS battery autonomy", required_value="15 minutes", observed_value="10 minutes", normalized_unit="minutes", status="NON_COMPLIANT", severity="high", explanation="Does not meet requirement.", original_requirement_text="15 minutes", original_observed_text="10 minutes", specification_citation=citation, submittal_citation={**citation, "document_id": str(submittal.id), "filename": submittal.filename, "page": 1}, confidence=0.99),
                        RFI(project_id=project.id, equipment_id="UPS-A", document_id=submittal.id, rfi_number=f"RFI-{marker}", status="answered", question="Clearance?", answer="900 mm.", revision="1", approval_status="answered", citation=citation),
                        Shipment(project_id=project.id, equipment_id="UPS-A", vendor_id=vendor.id, reference=f"SHIP-{marker}", status="in_transit", revision="1", approval_status="current", evidence=citation),
                        ScheduleTask(project_id=project.id, equipment_id="UPS-A", document_id=specification.id, task_id=f"TASK-{marker}", name="UPS-A delivery", status="delayed", dependencies=[], revision="1", approval_status="current", citation=citation),
                        CommissioningStep(project_id=project.id, equipment_id="UPS-A", procedure_document_id=procedure.id, test_record_id=record.id, step_index=1, instruction="Test battery", acceptance_criterion="15 minutes", observation="10 minutes", status="fail", revision="1", approval_status="approved", citation=citation),
                        NonConformance(project_id=project.id, equipment_id="UPS-A", test_record_id=record.id, procedure_document_id=procedure.id, step_index=1, criterion="15 minutes", observation="10 minutes", citation=citation),
                        MitigationScenario(project_id=project.id, equipment_id="UPS-A", name=f"{marker} mitigation", description="Expedite replacement.", impact={"days": 5}, revision="1", approval_status="proposed", evidence=[citation]),
                        EvidenceLink(project_id=project.id, equipment_id="UPS-A", source_type="Document", source_id=str(specification.id), document_id=specification.id, relation="documents", revision="A", approval_status="approved", citation=citation),
                        EvidenceLink(project_id=project.id, equipment_id="UPS-A", source_type="Document", source_id=str(submittal.id), document_id=submittal.id, relation="documents", revision="B", approval_status="approved", citation={**citation, "document_id": str(submittal.id), "filename": submittal.filename, "page": 1}),
                    ]
                )
            await session.commit()
            return first.id, second.id

    def _document(project_id, equipment_id, filename, document_type, revision, approval):
        return Document(
            project_id=project_id,
            equipment_id=equipment_id,
            filename=filename,
            storage_path=filename,
            document_type=document_type,
            status="completed",
            content_sha256=uuid.uuid4().hex * 2,
            mime_type="text/markdown",
            size_bytes=1,
            metadata_json={"revision": revision, "approval_status": approval},
        )

    try:
        first_id, second_id = asyncio.run(seed())
        with TestClient(app) as client:
            app.state.session_factory = sessions
            response = client.get(f"/projects/{first_id}/equipment/UPS-A/digital-thread")
            assert response.status_code == 200
            thread = response.json()
            assert thread["equipment"]["name"] == "UPS-A first"
            assert thread["current_specification"]["revision"] == "A"
            assert thread["current_submittal"]["approval_status"] == "approved"
            for field in (
                "requirements", "compliance_findings", "rfis", "vendor", "shipments", "schedule_tasks",
                "commissioning_status", "open_ncrs", "mitigation_scenarios", "evidence_links",
            ):
                assert thread[field]
                assert "second" not in str(thread[field]).lower()
            assert client.get(f"/projects/{second_id}/equipment/MISSING/digital-thread").status_code == 404
    finally:
        asyncio.run(engine.dispose())
