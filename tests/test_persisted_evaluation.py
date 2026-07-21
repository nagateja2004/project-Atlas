import asyncio
import uuid
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.evaluation import (
    LabelledCase,
    aggregate_compliance,
    aggregate_rag,
    load_fixture,
    score_compliance,
    score_rag,
)
from app.ingestion import Citation
from app.main import app
from app.models import Base
from app.workflow import AnswerCitation, AnswerClaim, SupportingSpan


def test_metric_calculations_use_actual_labelled_cases() -> None:
    compliance = score_compliance(
        [
            {"parameter": "voltage", "status": "NON_COMPLIANT", "clause": "2.2.1"},
            {"parameter": "clearance", "status": "COMPLIANT", "clause": "2.2.5"},
            {"parameter": "battery", "status": "NON_COMPLIANT", "clause": "2.2.4"},
        ],
        [
            {"parameter": "voltage", "status": "NON_COMPLIANT", "clause": "2.2.1"},
            {"parameter": "clearance", "status": "COMPLIANT", "clause": "wrong"},
            {"parameter": "unexpected", "status": "NON_COMPLIANT", "clause": "9.9"},
        ],
    )
    assert compliance["true_positive"] == 1
    assert compliance["true_negative"] == 1
    assert compliance["false_positive"] == 1
    assert compliance["false_negative"] == 1
    assert compliance["precision"] == compliance["recall"] == compliance["f1"] == 0.5
    assert compliance["clause_citation_accuracy"] == 0.3333

    case = LabelledCase(
        id="rag-1",
        category="rag",
        question="Required autonomy?",
        expected_references=[{"document": "UPS_Specification.md", "page": 2}],
    )
    citation = AnswerCitation(
        **Citation(document_id=uuid.uuid4(), filename="UPS_Specification.md", page=2, section="2.2.4").model_dump(),
        citation_id="C1",
        chunk_id=str(uuid.uuid4()),
        supporting_spans=[SupportingSpan(text="15 minutes", start=0, end=10)],
    )
    answer = SimpleNamespace(
        status="ANSWERED",
        citations=[citation],
        claims=[AnswerClaim(text="15 minutes", type="fact", citation_ids=["C1"])],
    )
    rag = score_rag(case, answer, [("UPS_Specification.md", 2)], 12.345)
    assert rag["recall_at_5"] == rag["citation_correctness"] == 1
    assert rag["grounded_answer"] is True
    assert rag["latency_ms"] == 12.35


def test_zero_division_and_json_csv_fixtures() -> None:
    assert aggregate_compliance([]) == {
        "true_positive": 0,
        "true_negative": 0,
        "false_positive": 0,
        "false_negative": 0,
        "clause_citation_correct": 0,
        "clause_citation_total": 0,
        "precision": 0.0,
        "recall": 0.0,
        "f1": 0.0,
        "clause_citation_accuracy": 0.0,
    }
    assert aggregate_rag([]) == {
        "recall_at_5": 0.0,
        "citation_correctness": 0.0,
        "grounded_answer_rate": 0.0,
        "insufficient_evidence_accuracy": 0.0,
        "average_latency_ms": 0.0,
    }
    assert [item.id for item in load_fixture("synthetic_small", "json").cases] == [
        item.id for item in load_fixture("synthetic_small", "csv").cases
    ]


def test_failed_cases_are_persisted_and_project_scoped(tmp_path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'evaluation-api.db'}")

    async def prepare() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(prepare())
    try:
        with TestClient(app) as client:
            app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
            project = client.post("/projects", json={"name": "Evaluation project"}).json()
            other = client.post("/projects", json={"name": "Other project"}).json()
            app.state.knowledge_service = SimpleNamespace(
                copilot=lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("evaluation provider unavailable"))
            )
            response = client.post(
                "/api/evaluation/run",
                json={"project_id": project["id"], "fixture_name": "synthetic_small", "fixture_format": "json"},
            )
            assert response.status_code == 201, response.text
            run = response.json()
            assert run["status"] == "COMPLETED_WITH_FAILURES"
            assert len(run["cases"]) == 3
            assert all(item["status"] == "ERROR" for item in run["cases"])
            assert run["metrics"]["compliance"]["precision"] == 0
            assert client.get(
                f"/api/evaluation/runs/{run['id']}?project_id={project['id']}"
            ).status_code == 200
            assert client.get(
                f"/api/evaluation/runs/{run['id']}?project_id={other['id']}"
            ).status_code == 404
    finally:
        asyncio.run(engine.dispose())
