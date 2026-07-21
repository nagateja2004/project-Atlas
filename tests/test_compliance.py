import asyncio
import hashlib
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.compliance import (
    ComplianceService,
    ExtractedRecord,
    Rule,
    compare_records,
    evaluate_ground_truth,
    normalize_value,
    review_finding,
)
from app.config import Settings
from app.ingestion import Citation
from app.models import AuditEvent, Base, ComplianceFinding, Document, NonConformance, Project
from app.main import app

DATASET = Path(__file__).parents[1] / "data" / "synthetic_epc"


def config(tmp_path: Path) -> Settings:
    return Settings(upload_dir=str(tmp_path / "uploads"), graph_dir=str(tmp_path / "graphs"))


def document(project_id: uuid.UUID, path: Path, document_type: str) -> Document:
    return Document(
        id=uuid.uuid4(),
        project_id=project_id,
        filename=path.name,
        storage_path=str(path),
        document_type=document_type,
        status="completed",
        content_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        mime_type="text/markdown",
        size_bytes=path.stat().st_size,
        metadata_json={},
    )


@pytest.mark.asyncio
async def test_synthetic_compliance_matches_ground_truth(tmp_path: Path) -> None:
    service, project_id = ComplianceService(config(tmp_path)), uuid.uuid4()
    pairs = [
        ("UPS_Specification.md", "UPS-002_VoltEdge_UPS-A.md"),
        ("CRAC_Specification.md", "CRAC-002_ThermalCore_CRAC-1.md"),
        ("Switchgear_Specification.md", "SWGR-002_ArcLine_SWGR-A.md"),
        ("UPS_Specification.md", "UPS-001_ApexPower_UPS-A.md"),
        ("CRAC_Specification.md", "CRAC-001_PolarAir_CRAC-1.md"),
        ("Switchgear_Specification.md", "SWGR-001_GridPoint_SWGR-A.md"),
    ]
    findings = []
    for specification, submittal in pairs:
        findings.extend(
            await service.assess(
                document(project_id, DATASET / "specifications" / specification, "specification"),
                document(project_id, DATASET / "submittals" / submittal, "submittal"),
            )
        )

    metrics = evaluate_ground_truth(findings, DATASET / "ground_truth.json")
    assert metrics.true_positive == 6
    assert metrics.false_positive == metrics.false_negative == 0
    assert metrics.true_negative == 6
    assert metrics.precision == metrics.recall == metrics.f1 == 1
    voltage = next(
        finding for finding in findings
        if finding.requirement_key == "voltage" and finding.status == "NON_COMPLIANT"
    )
    assert voltage.status == "NON_COMPLIANT"
    assert voltage.equipment_id == "UPS-A" and voltage.parameter == "voltage"
    assert voltage.specification_citation.page == 2
    assert voltage.submittal_citation and voltage.submittal_citation.page == 1
    assert "415/240 V" in voltage.original_observed_text


@pytest.mark.asyncio
async def test_clean_submittals_are_compliant(tmp_path: Path) -> None:
    service, project_id = ComplianceService(config(tmp_path)), uuid.uuid4()
    pairs = [
        ("UPS_Specification.md", "UPS-001_ApexPower_UPS-A.md"),
        ("CRAC_Specification.md", "CRAC-001_PolarAir_CRAC-1.md"),
        ("Switchgear_Specification.md", "SWGR-001_GridPoint_SWGR-A.md"),
    ]
    findings = []
    for specification, submittal in pairs:
        findings.extend(
            await service.assess(
                document(project_id, DATASET / "specifications" / specification, "specification"),
                document(project_id, DATASET / "submittals" / submittal, "submittal"),
            )
        )
    assert {finding.status for finding in findings} == {"COMPLIANT"}


def test_numeric_text_missing_and_unit_conversion_rules() -> None:
    citation = Citation(document_id=uuid.uuid4(), filename="synthetic.md", page=1, section="General")
    clearance_rule = Rule("clearance", "Clearance", "minimum", "medium", "", "")
    required = ExtractedRecord("clearance", "24 inches", "Required 24 inches", 24.0, "inches", citation)
    converted_value, converted_unit = normalize_value("610 mm")
    converted = ExtractedRecord("clearance", "610 mm", "Observed 610 mm", converted_value, converted_unit, citation)
    assert compare_records(clearance_rule, required, converted).status == "COMPLIANT"
    assert compare_records(clearance_rule, required, None).status == "MISSING_INFORMATION"

    rating_rule = Rule("enclosure", "Enclosure", "exact", "high", "", "")
    required_text = ExtractedRecord("enclosure", "Type 2B", "Required Type 2B", "type2b", None, citation)
    observed_text = ExtractedRecord("enclosure", "Type 1", "Observed Type 1", "type1", None, citation)
    assert compare_records(rating_rule, required_text, observed_text).status == "NON_COMPLIANT"

    capacity_rule = Rule("capacity", "Capacity", "minimum", "high", "", "")
    capacity = ExtractedRecord("capacity", "120 kW", "Required 120 kW", 120.0, "kW", citation)
    observed_capacity = ExtractedRecord("capacity", "105 kW", "Observed 105 kW", 105.0, "kW", citation)
    assert compare_records(capacity_rule, capacity, observed_capacity).status == "NON_COMPLIANT"


@pytest.mark.asyncio
async def test_findings_are_deduplicated_and_reviewed_with_audit_events(tmp_path: Path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'compliance.db'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as session:
            project = Project(name="Compliance test")
            session.add(project)
            await session.flush()
            specification = document(project.id, DATASET / "specifications" / "UPS_Specification.md", "specification")
            submittal = document(project.id, DATASET / "submittals" / "UPS-002_VoltEdge_UPS-A.md", "submittal")
            session.add_all([specification, submittal])
            await session.commit()
            service = ComplianceService(config(tmp_path))

            first = await service.store(session, specification, submittal)
            second = await service.store(session, specification, submittal)
            assert len(first) == len(second) == 2
            assert len((await session.scalars(select(ComplianceFinding))).all()) == 2
            reviewed = await review_finding(session, first[0], "approved", None, "Accepted by reviewer.")
            assert reviewed.review_status == "approved"
            assert reviewed.reviewer_note == "Accepted by reviewer."
            await review_finding(session, first[0], "rejected", None, "Evidence is incomplete.")
            reviewed = await review_finding(session, first[0], "needs_review", None, "Escalate to lead engineer.")
            assert reviewed.review_status == "needs_review"
            assert len((await session.scalars(select(NonConformance))).all()) == 0
            audit_events = (await session.scalars(select(AuditEvent))).all()
            assert [event.event_type for event in audit_events].count("compliance_finding_created") == 2
            assert [event.event_type for event in audit_events].count("compliance_finding_reused") == 2
            assert [event.event_type for event in audit_events].count("compliance_check_completed") == 2
            assert [event.event_type for event in audit_events].count("compliance_finding_reviewed") == 3
            assert audit_events[-1].event_type == "compliance_finding_reviewed"
    finally:
        await engine.dispose()


def test_compliance_api_runs_review_and_reports_metrics(tmp_path: Path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'compliance-api.db'}")

    async def create_schema() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(create_schema())
    try:
        with TestClient(app) as client:
            app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
            app.state.compliance_service = ComplianceService(config(tmp_path))
            project = client.post("/projects", json={"name": "Compliance API test"}).json()
            project_id = uuid.UUID(project["id"])

            async def seed_documents() -> tuple[uuid.UUID, uuid.UUID]:
                async with app.state.session_factory() as session:
                    specification = document(project_id, DATASET / "specifications" / "UPS_Specification.md", "specification")
                    submittal = document(project_id, DATASET / "submittals" / "UPS-002_VoltEdge_UPS-A.md", "submittal")
                    session.add_all([specification, submittal])
                    await session.commit()
                    return specification.id, submittal.id

            specification_id, submittal_id = asyncio.run(seed_documents())
            response = client.post(
                f"/projects/{project['id']}/compliance/checks",
                json={"specification_document_id": str(specification_id), "submittal_document_id": str(submittal_id)},
            )
            assert response.status_code == 200
            findings = response.json()["findings"]
            assert {finding["status"] for finding in findings} == {"NON_COMPLIANT"}
            assert {finding["equipment_id"] for finding in findings} == {"UPS-A"}
            assert {finding["parameter"] for finding in findings} == {"voltage", "battery_autonomy"}
            review = client.patch(
                f"/projects/{project['id']}/compliance/findings/{findings[0]['id']}/review",
                json={"decision": "approved"},
            )
            assert review.status_code == 200
            assert review.json()["review_status"] == "approved"
            needs_review = client.patch(
                f"/projects/{project['id']}/compliance/findings/{findings[0]['id']}/review",
                json={"decision": "needs_review", "reviewer_note": "Confirm latest revision."},
            )
            assert needs_review.status_code == 200
            assert needs_review.json()["review_status"] == "needs_review"
            assert needs_review.json()["reviewer_note"] == "Confirm latest revision."
            metrics = client.get(f"/projects/{project['id']}/compliance/evaluation")
            assert metrics.status_code == 200
            assert metrics.json()["true_positive"] == 2
            assert {"true_negative", "f1"} <= metrics.json().keys()

            other = client.post("/projects", json={"name": "Other project"}).json()
            cross_project = client.post(
                f"/projects/{other['id']}/compliance/checks",
                json={"specification_document_id": str(specification_id), "submittal_document_id": str(submittal_id)},
            )
            assert cross_project.status_code == 404
    finally:
        asyncio.run(engine.dispose())


@pytest.mark.asyncio
async def test_selected_document_revisions_are_preserved_without_mixing(tmp_path: Path) -> None:
    project_id = uuid.uuid4()
    specification = document(project_id, DATASET / "specifications" / "UPS_Specification.md", "specification")
    submittal = document(project_id, DATASET / "submittals" / "UPS-002_VoltEdge_UPS-A.md", "submittal")
    specification.metadata_json = {"revision": "A", "approval_status": "approved"}
    submittal.metadata_json = {"revision": "B", "approval_status": "needs_review"}

    findings = await ComplianceService(config(tmp_path)).assess(specification, submittal)

    assert {finding.specification_revision for finding in findings} == {"A"}
    assert {finding.submittal_revision for finding in findings} == {"B"}
    assert {finding.specification_citation.document_id for finding in findings} == {specification.id}
    assert {finding.submittal_citation.document_id for finding in findings if finding.submittal_citation} == {submittal.id}
