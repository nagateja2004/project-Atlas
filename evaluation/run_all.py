"""Run the complete deterministic Project Atlas evaluation suite."""

import asyncio
import hashlib
import json
import tempfile
import uuid
from pathlib import Path
from statistics import fmean
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.commissioning import CommissioningService, EngineerObservation
from app.compliance import ComplianceService, evaluate_ground_truth
from app.config import Settings
from app.models import Base, Document, Project
from app.procurement import compare_alternatives, seed_synthetic_supply_chain, shipment_risk
from app.schedule import ScheduleScenario, ScheduleService, load_schedule
from scripts.evaluate_rag import evaluate as evaluate_rag

ROOT = Path(__file__).parents[1]
DATASET = ROOT / "data" / "synthetic_epc"
GROUND_TRUTH = DATASET / "ground_truth.json"
SUPPLY_CHAIN_DATA = DATASET / "supply_chain" / "shipments.json"
MANUAL_TIME_STUDY = Path(__file__).with_name("manual_time_study.json")


class EvaluationInputError(RuntimeError):
    pass


def _required_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise EvaluationInputError(f"Required evaluation input is missing: {path}")
    try:
        value = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise EvaluationInputError(f"Required evaluation input is invalid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise EvaluationInputError(f"Required evaluation input must be a JSON object: {path}")
    return value


def _require(mapping: dict[str, Any], key: str, source: Path) -> Any:
    if key not in mapping or mapping[key] is None:
        raise EvaluationInputError(f"Required ground-truth field is missing: {source}:{key}")
    return mapping[key]


def _document(project_id: uuid.UUID, path: Path, document_type: str) -> Document:
    if not path.is_file():
        raise EvaluationInputError(f"Required evaluation document is missing: {path}")
    return Document(
        id=uuid.uuid4(),
        project_id=project_id,
        filename=path.name,
        storage_path=str(path),
        document_type=document_type,
        status="completed",
        content_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        mime_type="text/csv" if path.suffix == ".csv" else "text/markdown",
        size_bytes=path.stat().st_size,
        metadata_json={},
    )


def _rag_metrics(report: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "recall_at_5",
        "recall_at_12",
        "mrr",
        "correct_document_rate",
        "correct_page_rate",
        "citation_precision",
        "unsupported_claim_rate",
        "average_input_tokens",
        "average_output_tokens",
        "average_latency_ms",
    )
    return {
        mode: {field: report["test"][mode]["metrics"][field] for field in fields}
        for mode in ("baseline", "advanced")
    }


async def _compliance_metrics(truth: dict[str, Any], settings: Settings) -> dict[str, Any]:
    _require(truth, "expected_compliance_findings", GROUND_TRUTH)
    _require(truth, "expected_clean_submittals", GROUND_TRUTH)
    project_id = uuid.uuid4()
    pairs = {
        "UPS_Specification.md": ("UPS-001_ApexPower_UPS-A.md", "UPS-002_VoltEdge_UPS-A.md"),
        "CRAC_Specification.md": ("CRAC-001_PolarAir_CRAC-1.md", "CRAC-002_ThermalCore_CRAC-1.md"),
        "Switchgear_Specification.md": ("SWGR-001_GridPoint_SWGR-A.md", "SWGR-002_ArcLine_SWGR-A.md"),
    }
    findings = []
    service = ComplianceService(settings)
    for specification, submittals in pairs.items():
        for submittal in submittals:
            findings.extend(
                await service.assess(
                    _document(project_id, DATASET / "specifications" / specification, "specification"),
                    _document(project_id, DATASET / "submittals" / submittal, "submittal"),
                )
            )
    return evaluate_ground_truth(findings, GROUND_TRUTH).model_dump()


async def _schedule_metrics(truth: dict[str, Any], settings: Settings) -> dict[str, Any]:
    expected = _require(truth, "expected_schedule_risks", GROUND_TRUTH)
    if not expected:
        raise EvaluationInputError("Required schedule ground truth is empty")
    project_id = uuid.uuid4()
    path = DATASET / "schedules" / "atlas_demo_schedule.csv"
    document = _document(project_id, path, "schedule")
    tasks = load_schedule(path)
    cases = []
    for item in expected:
        for field in ("task_id", "analysis_date", "forecast_delay_days"):
            _require(item, field, GROUND_TRUTH)
        analysis = await ScheduleService(settings).analyze(
            document, ScheduleScenario(analysis_date=item["analysis_date"])
        )
        risk = next((risk for risk in analysis.risks if risk.affected_task == item["task_id"]), None)
        if not risk or item["task_id"] not in tasks:
            raise EvaluationInputError(f"Expected schedule risk was not produced: {item['task_id']}")
        actual = int(item["forecast_delay_days"])
        cases.append(
            {
                "task_id": item["task_id"],
                "lead_time_days": risk.lead_time_days,
                "predicted_delay_days": risk.predicted_delay_days,
                "actual_or_simulated_delay_days": actual,
                "schedule_csv_reported_delay_days": tasks[item["task_id"]].reported_delay_days,
                "prediction_error_days": risk.predicted_delay_days - actual,
                "absolute_prediction_error_days": abs(risk.predicted_delay_days - actual),
            }
        )
    return {
        "mean_lead_time_days": round(fmean(item["lead_time_days"] for item in cases), 2),
        "mean_predicted_delay_days": round(fmean(item["predicted_delay_days"] for item in cases), 2),
        "mean_actual_or_simulated_delay_days": round(
            fmean(item["actual_or_simulated_delay_days"] for item in cases), 2
        ),
        "mean_prediction_error_days": round(fmean(item["prediction_error_days"] for item in cases), 2),
        "mean_absolute_prediction_error_days": round(
            fmean(item["absolute_prediction_error_days"] for item in cases), 2
        ),
        "cases": cases,
    }


async def _supply_chain_metrics(source: dict[str, Any], workspace: Path) -> dict[str, Any]:
    expected_shipments = _require(source, "shipments", SUPPLY_CHAIN_DATA)
    if not expected_shipments:
        raise EvaluationInputError("Required supply-chain ground truth is empty")
    engine = create_async_engine(f"sqlite+aiosqlite:///{workspace / 'supply-chain.db'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as session:
            project = Project(name="Supply-chain evaluation")
            session.add(project)
            await session.flush()
            result = await seed_synthetic_supply_chain(session, project.id, SUPPLY_CHAIN_DATA)
            event_latencies, risky, alternatives = [], 0, 0
            for shipment in result.shipments:
                risk = await shipment_risk(session, project.id, shipment.shipment_id)
                if not risk:
                    raise EvaluationInputError(f"Shipment risk was not produced: {shipment.reference}")
                event_latencies.extend(event.alert_latency_minutes for event in risk.risk_events)
                if risk.forecast_delay_days > 0:
                    risky += 1
                    comparison = await compare_alternatives(session, project.id, shipment.shipment_id)
                    alternatives += bool(comparison and comparison.options)
            tiers = [len(item.supplier_tiers) for item in result.shipments]
            return {
                "shipments_represented": len(result.shipments),
                "expected_shipments": len(expected_shipments),
                "representation_rate": len(result.shipments) / len(expected_shipments),
                "supplier_tiers_total": sum(tiers),
                "mean_supplier_tiers_per_shipment": round(fmean(tiers), 2),
                "risk_events_with_alert_latency": len(event_latencies),
                "mean_alert_latency_minutes": round(fmean(event_latencies), 2) if event_latencies else None,
                "risky_shipments": risky,
                "alternatives_generated": alternatives,
                "alternative_generation_success": alternatives / risky if risky else None,
            }
    finally:
        await engine.dispose()


async def _commissioning_metrics(
    truth: dict[str, Any], settings: Settings, workspace: Path
) -> dict[str, Any]:
    expected = _require(truth, "expected_commissioning_evaluation", GROUND_TRUTH)
    procedure_paths = _require(expected, "procedure_documents", GROUND_TRUTH)
    failure = _require(expected, "failure_case", GROUND_TRUTH)
    if len(procedure_paths) < 2:
        raise EvaluationInputError("At least two commissioning procedures are required")
    engine = create_async_engine(f"sqlite+aiosqlite:///{workspace / 'commissioning.db'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    service = CommissioningService(settings)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as session:
            project = Project(name="Commissioning evaluation")
            session.add(project)
            await session.flush()
            documents = [
                _document(project.id, DATASET / relative, "commissioning_record")
                for relative in procedure_paths
            ]
            session.add_all(documents)
            await session.commit()
            total_steps = automatically_evaluated = completed = total = actual_ncrs = expected_ncrs = 0
            ncr_correct = True
            failure_found = False
            for document in documents:
                procedure = service.procedure(document)
                total_steps += len(procedure.steps)
                observations = []
                expected_failed_index = None
                for step in procedure.steps:
                    observation = "Verified complete."
                    if document.filename == Path(failure["procedure_document"]).name and failure["step_text"] in step.instruction:
                        observation = failure["observation"]
                        expected_failed_index = step.index
                        failure_found = True
                    observations.append(EngineerObservation(step_index=step.index, observation=observation))
                record = await service.record(session, document, observations)
                automatically_evaluated += sum(step.status in {"PASS", "FAIL"} for step in record.steps)
                completed += record.completed_steps
                total += record.total_steps
                actual_ncrs += len(record.non_conformances)
                if expected_failed_index is not None:
                    expected_ncrs += int(failure["expected_ncr_count"])
                    ncr_correct &= (
                        next(step for step in record.steps if step.index == expected_failed_index).status
                        == failure["expected_status"]
                        and len(record.non_conformances) == failure["expected_ncr_count"]
                        and all(item.step_index == expected_failed_index for item in record.non_conformances)
                    )
            if not failure_found:
                raise EvaluationInputError("Commissioning failure ground truth did not match a procedure step")
            return {
                "total_steps": total_steps,
                "automatically_evaluated_steps": automatically_evaluated,
                "automation_coverage": automatically_evaluated / total_steps,
                "completion_coverage": completed / total,
                "expected_ncrs": expected_ncrs,
                "actual_ncrs": actual_ncrs,
                "ncr_correctness": bool(ncr_correct and actual_ncrs == expected_ncrs),
            }
    finally:
        await engine.dispose()


def _manual_effort(path: Path) -> dict[str, Any]:
    source = _required_json(path)
    measurements = _require(source, "measurements", path)
    if not isinstance(measurements, list):
        raise EvaluationInputError("manual_time_study.json:measurements must be a list")
    if not measurements:
        return {
            "status": "NOT_MEASURED",
            "measurement_count": 0,
            "manual_hours": None,
            "atlas_hours": None,
            "hours_saved": None,
            "note": source.get("note", "No manual measurements supplied."),
        }
    rows = []
    for index, item in enumerate(measurements):
        if not isinstance(item, dict):
            raise EvaluationInputError(f"manual_time_study.json measurement {index} must be an object")
        for field in ("workflow", "manual_hours", "atlas_hours", "sample_count"):
            _require(item, field, path)
        if not all(isinstance(item[field], (int, float)) and item[field] >= 0 for field in ("manual_hours", "atlas_hours")):
            raise EvaluationInputError(f"manual_time_study.json measurement {index} has invalid hours")
        if not isinstance(item["sample_count"], int) or item["sample_count"] <= 0:
            raise EvaluationInputError(f"manual_time_study.json measurement {index} has invalid sample_count")
        rows.append(item)
    manual = sum(item["manual_hours"] * item["sample_count"] for item in rows)
    atlas = sum(item["atlas_hours"] * item["sample_count"] for item in rows)
    return {
        "status": "MEASURED",
        "measurement_count": len(rows),
        "sample_count": sum(item["sample_count"] for item in rows),
        "manual_hours": round(manual, 3),
        "atlas_hours": round(atlas, 3),
        "hours_saved": round(manual - atlas, 3),
        "measurements": rows,
    }


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Project Atlas Evaluation",
        "",
        "All metrics are deterministic or directly measured by this command. Synthetic scenarios are not historical predictions.",
    ]
    for section, values in report.items():
        lines.extend(["", f"## {section.replace('_', ' ').title()}", ""])
        if section == "rag":
            lines.extend(["| Metric | Baseline | Advanced |", "| --- | ---: | ---: |"])
            for key in values["baseline"]:
                lines.append(f"| {key.replace('_', ' ')} | {values['baseline'][key]} | {values['advanced'][key]} |")
        else:
            lines.extend(["| Metric | Value |", "| --- | ---: |"])
            for key, value in values.items():
                if not isinstance(value, (dict, list)):
                    lines.append(f"| {key.replace('_', ' ')} | {value if value is not None else 'NOT MEASURED'} |")
    return "\n".join(lines) + "\n"


async def evaluate_all(
    output_dir: Path = Path(__file__).parent,
    ground_truth_path: Path = GROUND_TRUTH,
    manual_time_path: Path = MANUAL_TIME_STUDY,
) -> dict[str, Any]:
    truth = _required_json(ground_truth_path)
    for key in (
        "expected_answers",
        "expected_insufficient_answers",
        "expected_compliance_findings",
        "expected_clean_submittals",
        "expected_schedule_risks",
        "expected_commissioning_evaluation",
    ):
        _require(truth, key, ground_truth_path)
    supply_source = _required_json(SUPPLY_CHAIN_DATA)
    manual = _manual_effort(manual_time_path)
    settings = Settings(gemini_api_key=None)
    with tempfile.TemporaryDirectory(prefix="atlas-all-eval-") as directory:
        workspace = Path(directory)
        rag_report = await evaluate_rag(workspace / "rag")
        report = {
            "rag": _rag_metrics(rag_report),
            "compliance": await _compliance_metrics(truth, settings),
            "schedule": await _schedule_metrics(truth, settings),
            "supply_chain": await _supply_chain_metrics(supply_source, workspace),
            "commissioning": await _commissioning_metrics(truth, settings, workspace),
            "manual_effort": manual,
        }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "latest.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    (output_dir / "latest.md").write_text(_markdown(report))
    return report


def main() -> None:
    report = asyncio.run(evaluate_all())
    print(json.dumps(report, indent=2, sort_keys=True))
    print(f"Wrote {Path(__file__).parent / 'latest.json'}")
    print(f"Wrote {Path(__file__).parent / 'latest.md'}")


if __name__ == "__main__":
    main()
