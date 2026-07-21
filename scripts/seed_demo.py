"""Seed a fresh Atlas project through the live FastAPI upload endpoint."""

import argparse
from pathlib import Path

import httpx

ROOT = Path(__file__).parents[1]
DATASET = ROOT / "data" / "synthetic_epc"


def sources() -> list[tuple[str, Path]]:
    return [
        *(("specification", path) for path in sorted((DATASET / "specifications").glob("*.md"))),
        *(("submittal", path) for path in sorted((DATASET / "submittals").glob("*.md"))),
        *(("RFI", path) for path in sorted((DATASET / "rfis").glob("*.md"))),
        ("meeting_minutes", DATASET / "meeting_minutes" / "MM-014_delivery_risk_review.md"),
        ("change_order", DATASET / "change_orders" / "CO-001_switchgear_recovery.md"),
        ("schedule", DATASET / "schedules" / "atlas_demo_schedule.csv"),
        *(("commissioning_record", path) for path in sorted((DATASET / "commissioning").glob("*.md"))),
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload the synthetic Atlas demo corpus to a running API.")
    parser.add_argument("--api-url", default="http://localhost:8001")
    parser.add_argument("--project-name", default="Atlas Synthetic Demo")
    args = parser.parse_args()
    with httpx.Client(base_url=args.api_url, timeout=60) as client:
        projects = client.get("/projects")
        projects.raise_for_status()
        existing = next((item for item in projects.json() if item["name"] == args.project_name), None)
        if existing:
            project_id = existing["id"]
        else:
            project = client.post("/projects", json={"name": args.project_name})
            project.raise_for_status()
            project_id = project.json()["id"]
        existing_files = {item["filename"] for item in client.get(f"/projects/{project_id}/documents").json()}
        for document_type, path in sources():
            if path.name in existing_files:
                continue
            content_type = "text/csv" if path.suffix == ".csv" else "text/markdown"
            response = client.post(
                f"/projects/{project_id}/documents",
                data={"document_type": document_type},
                files={"file": (path.name, path.read_bytes(), content_type)},
            )
            response.raise_for_status()
            payload = response.json()
            if payload["ingestion"]["status"] != "completed":
                raise RuntimeError(f"Ingestion did not complete for {path.name}")
        supply_chain = client.post(f"/projects/{project_id}/supply-chain/seed")
        supply_chain.raise_for_status()
        scenario = client.post(f"/projects/{project_id}/demo/vertical-scenario")
        scenario.raise_for_status()
    print(
        f"Seeded project {project_id} with {len(sources())} synthetic documents and "
        f"{len(supply_chain.json()['shipments'])} synthetic shipments and the SWGR-A vertical scenario."
    )


if __name__ == "__main__":
    main()
