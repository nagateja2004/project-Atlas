import csv
import json
import re
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Document, EvaluationCase, EvaluationRun

FIXTURE_DIR = Path(__file__).parents[1] / "data" / "synthetic_epc" / "evaluation"


class ExpectedFinding(BaseModel):
    parameter: str
    status: str
    clause: str | None = None


class ExpectedReference(BaseModel):
    document: str
    page: int = Field(ge=1)


class LabelledCase(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    category: Literal["compliance", "rag"]
    specification: str | None = None
    submittal: str | None = None
    expected_findings: list[ExpectedFinding] = Field(default_factory=list)
    question: str | None = None
    expected_references: list[ExpectedReference] = Field(default_factory=list)
    expect_insufficient: bool = False

    @model_validator(mode="after")
    def required_fields(self):
        if self.category == "compliance" and not (self.specification and self.submittal and self.expected_findings):
            raise ValueError("Compliance cases require specification, submittal, and expected_findings")
        if self.category == "rag" and not self.question:
            raise ValueError("RAG cases require a question")
        if self.category == "rag" and not self.expect_insufficient and not self.expected_references:
            raise ValueError("Answerable RAG cases require expected_references")
        return self


class EvaluationFixture(BaseModel):
    name: str
    data_classification: str
    synthetic_data: Literal[True]
    cases: list[LabelledCase] = Field(min_length=1)


class EvaluationRunRequest(BaseModel):
    project_id: uuid.UUID
    fixture_name: Literal["synthetic_small"] = "synthetic_small"
    fixture_format: Literal["json", "csv"] = "json"


class EvaluationCaseResponse(BaseModel):
    id: uuid.UUID
    case_key: str
    category: str
    status: str
    expected: dict
    actual: dict
    metrics: dict
    error: str | None


class EvaluationRunResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    fixture_name: str
    fixture_format: str
    synthetic_data: bool
    status: str
    metrics: dict
    error: str | None
    started_at: datetime
    completed_at: datetime | None
    cases: list[EvaluationCaseResponse]


def _ratio(numerator: int | float, denominator: int | float) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def score_compliance(expected: list[dict], actual: list[dict]) -> dict:
    expected_by_key = {item["parameter"]: item for item in expected}
    actual_by_key = {item["parameter"]: item for item in actual}
    tp = tn = fp = fn = clause_correct = clause_total = 0
    for parameter in sorted(set(expected_by_key) | set(actual_by_key)):
        wanted, observed = expected_by_key.get(parameter), actual_by_key.get(parameter)
        expected_positive = bool(wanted and wanted["status"] == "NON_COMPLIANT")
        actual_positive = bool(observed and observed["status"] == "NON_COMPLIANT")
        if wanted:
            if expected_positive and actual_positive:
                tp += 1
            elif expected_positive:
                fn += 1
            elif actual_positive:
                fp += 1
            else:
                tn += 1
            if wanted.get("clause"):
                clause_total += 1
                clause_correct += bool(observed and _clause(observed.get("clause")) == _clause(wanted["clause"]))
        elif actual_positive:
            fp += 1
    precision, recall = _ratio(tp, tp + fp), _ratio(tp, tp + fn)
    return {
        "true_positive": tp,
        "true_negative": tn,
        "false_positive": fp,
        "false_negative": fn,
        "precision": precision,
        "recall": recall,
        "f1": _ratio(2 * precision * recall, precision + recall),
        "clause_citation_correct": clause_correct,
        "clause_citation_total": clause_total,
        "clause_citation_accuracy": _ratio(clause_correct, clause_total),
    }


def aggregate_compliance(rows: list[dict]) -> dict:
    totals = {
        key: sum(row.get(key, 0) for row in rows)
        for key in (
            "true_positive", "true_negative", "false_positive", "false_negative",
            "clause_citation_correct", "clause_citation_total",
        )
    }
    totals["precision"] = _ratio(totals["true_positive"], totals["true_positive"] + totals["false_positive"])
    totals["recall"] = _ratio(totals["true_positive"], totals["true_positive"] + totals["false_negative"])
    totals["f1"] = _ratio(2 * totals["precision"] * totals["recall"], totals["precision"] + totals["recall"])
    totals["clause_citation_accuracy"] = _ratio(totals["clause_citation_correct"], totals["clause_citation_total"])
    return totals


def score_rag(case: LabelledCase, answer, ranking: list[tuple[str, int]], latency_ms: float) -> dict:
    expected = {(Path(item.document).name, item.page) for item in case.expected_references}
    cited = [(Path(item.filename).name, item.page) for item in answer.citations]
    correct_citations = sum(item in expected for item in cited)
    retrieved = set(ranking[:5])
    recall = _ratio(len(retrieved & expected), len(expected)) if expected else 0.0
    grounded = (
        answer.status != "INSUFFICIENT_EVIDENCE"
        and bool(answer.claims)
        and all(claim.support_status != "UNSUPPORTED" and claim.citation_ids for claim in answer.claims)
    )
    insufficient_correct = (answer.status == "INSUFFICIENT_EVIDENCE") == case.expect_insufficient
    return {
        "recall_at_5": recall,
        "correct_citations": correct_citations,
        "citation_count": len(cited),
        "citation_correctness": _ratio(correct_citations, len(cited)),
        "grounded_answer": bool(grounded),
        "answerable": not case.expect_insufficient,
        "insufficient_evidence_correct": insufficient_correct,
        "latency_ms": round(latency_ms, 2),
    }


def aggregate_rag(rows: list[dict]) -> dict:
    answerable = [row for row in rows if row.get("answerable")]
    citations = sum(row.get("citation_count", 0) for row in rows)
    return {
        "recall_at_5": round(sum(row.get("recall_at_5", 0) for row in answerable) / len(answerable), 4) if answerable else 0.0,
        "citation_correctness": _ratio(sum(row.get("correct_citations", 0) for row in rows), citations),
        "grounded_answer_rate": _ratio(sum(bool(row.get("grounded_answer")) for row in answerable), len(answerable)),
        "insufficient_evidence_accuracy": _ratio(sum(bool(row.get("insufficient_evidence_correct")) for row in rows), len(rows)),
        "average_latency_ms": round(sum(row.get("latency_ms", 0) for row in rows) / len(rows), 2) if rows else 0.0,
    }


def load_fixture(name: str, fixture_format: str) -> EvaluationFixture:
    path = FIXTURE_DIR / f"{name}.{fixture_format}"
    if fixture_format == "json":
        return EvaluationFixture.model_validate_json(path.read_text())
    rows = list(csv.DictReader(path.open(newline="")))
    return EvaluationFixture(
        name=name,
        data_classification="SYNTHETIC EPC EVALUATION DATA",
        synthetic_data=True,
        cases=[
            LabelledCase(
                id=row["id"],
                category=row["category"],
                specification=row.get("specification") or None,
                submittal=row.get("submittal") or None,
                expected_findings=json.loads(row.get("expected_findings") or "[]"),
                question=row.get("question") or None,
                expected_references=json.loads(row.get("expected_references") or "[]"),
                expect_insufficient=(row.get("expect_insufficient") or "false").lower() == "true",
            )
            for row in rows
        ],
    )


async def run_evaluation(
    session: AsyncSession,
    request: EvaluationRunRequest,
    compliance_service,
    knowledge_service,
    qdrant,
    settings,
) -> EvaluationRunResponse:
    run = EvaluationRun(
        project_id=request.project_id,
        fixture_name=request.fixture_name,
        fixture_format=request.fixture_format,
        status="RUNNING",
    )
    session.add(run)
    await session.commit()
    try:
        fixture = load_fixture(request.fixture_name, request.fixture_format)
        compliance_rows, rag_rows = [], []
        for labelled in fixture.cases:
            stored = EvaluationCase(
                evaluation_run_id=run.id,
                project_id=request.project_id,
                case_key=labelled.id,
                category=labelled.category,
                status="RUNNING",
                expected=labelled.model_dump(mode="json"),
            )
            session.add(stored)
            await session.flush()
            try:
                if labelled.category == "compliance":
                    actual = await _run_compliance_case(session, request.project_id, labelled, compliance_service)
                    metrics = score_compliance(
                        [item.model_dump() for item in labelled.expected_findings], actual
                    )
                    compliance_rows.append(metrics)
                    passed = metrics["false_positive"] == metrics["false_negative"] == 0 and metrics["clause_citation_accuracy"] == 1
                else:
                    started = time.perf_counter()
                    answer = await knowledge_service.copilot(request.project_id, labelled.question, [])
                    ranking = await _candidate_references(qdrant, settings, answer.trace.candidate_chunk_ids[:5])
                    metrics = score_rag(labelled, answer, ranking, (time.perf_counter() - started) * 1000)
                    rag_rows.append(metrics)
                    actual = answer.model_dump(mode="json")
                    passed = (
                        metrics["insufficient_evidence_correct"]
                        and (labelled.expect_insufficient or (
                            metrics["recall_at_5"] == 1
                            and metrics["citation_correctness"] == 1
                            and metrics["grounded_answer"]
                        ))
                    )
                stored.actual = {"findings": actual} if labelled.category == "compliance" else actual
                stored.metrics = metrics
                stored.status = "PASS" if passed else "FAIL"
            except Exception as exc:  # persist case failures without hiding the rest of the run
                stored.status, stored.error = "ERROR", f"{type(exc).__name__}: {exc}"
        await session.flush()
        case_rows = list((await session.scalars(
            select(EvaluationCase).where(EvaluationCase.evaluation_run_id == run.id)
        )).all())
        run.metrics = {
            "compliance": aggregate_compliance(compliance_rows),
            "rag": aggregate_rag(rag_rows),
        }
        run.status = "COMPLETED_WITH_FAILURES" if any(item.status != "PASS" for item in case_rows) else "COMPLETED"
    except Exception as exc:
        run.status, run.error = "FAILED", f"{type(exc).__name__}: {exc}"
    run.completed_at = datetime.now(UTC)
    await session.commit()
    return await get_evaluation_run(session, request.project_id, run.id)


async def get_evaluation_run(
    session: AsyncSession, project_id: uuid.UUID, run_id: uuid.UUID
) -> EvaluationRunResponse | None:
    run = await session.scalar(
        select(EvaluationRun).where(EvaluationRun.id == run_id, EvaluationRun.project_id == project_id)
    )
    if not run:
        return None
    cases = list((await session.scalars(
        select(EvaluationCase)
        .where(EvaluationCase.evaluation_run_id == run.id, EvaluationCase.project_id == project_id)
        .order_by(EvaluationCase.case_key)
    )).all())
    return EvaluationRunResponse(
        **{key: getattr(run, key) for key in (
            "id", "project_id", "fixture_name", "fixture_format", "synthetic_data", "status",
            "metrics", "error", "started_at", "completed_at",
        )},
        cases=[EvaluationCaseResponse.model_validate(item, from_attributes=True) for item in cases],
    )


async def _run_compliance_case(session, project_id, case, service) -> list[dict]:
    documents = list((await session.scalars(
        select(Document).where(
            Document.project_id == project_id,
            Document.filename.in_([case.specification, case.submittal]),
        )
    )).all())
    by_name = {item.filename: item for item in documents}
    if case.specification not in by_name or case.submittal not in by_name:
        raise ValueError("Required project-scoped compliance documents are missing")
    findings = await service.assess(by_name[case.specification], by_name[case.submittal])
    return [
        {
            "parameter": item.parameter,
            "status": item.status,
            "clause": _citation_clause(item.original_requirement_text, item.specification_citation.section),
        }
        for item in findings
    ]


async def _candidate_references(qdrant, settings, chunk_ids: list[str]) -> list[tuple[str, int]]:
    if not chunk_ids:
        return []
    points = await qdrant.retrieve(
        collection_name=settings.qdrant_collection,
        ids=chunk_ids,
        with_payload=True,
    )
    payloads = {str(point.id): point.payload or {} for point in points}
    return [
        (Path(str(payloads[value]["filename"])).name, int(payloads[value]["page"]))
        for value in chunk_ids
        if value in payloads and payloads[value].get("filename") and payloads[value].get("page")
    ]


def _citation_clause(text: str, fallback: str) -> str:
    match = re.search(r"\b\d+\.\d+(?:\.\d+)?\b", text)
    return match.group(0) if match else fallback


def _clause(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip().lower()
