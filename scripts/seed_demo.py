"""
Seed an Atlas project through the live FastAPI upload endpoint.

    # local, authentication disabled
    python3 scripts/seed_demo.py --api-url http://localhost:8001

    # against a deployment with ATLAS_AUTH_ENABLED=true
    python3 scripts/seed_demo.py --api-url https://example.invalid \
        --email you@example.com            # password from ATLAS_API_PASSWORD, or prompted

    # or with a token you already hold
    ATLAS_API_TOKEN=... python3 scripts/seed_demo.py --api-url https://example.invalid

    # the extended corpus, into its own project
    python3 scripts/seed_demo.py --dataset data/synthetic_epc_extended \
        --project-name "Atlas Extended Corpus"

Two things this needed after the rest of the system moved on:

  - It sent no Authorization header, so turning authentication on broke seeding
    entirely: the first GET /projects returns 401 and nothing else runs.
  - The corpus path was hardcoded, so the extended dataset could not be loaded
    at all even though its directory layout is identical.
"""

import argparse
import getpass
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).parents[1]

# Directory name -> the document_type the API expects. Both corpora use this
# layout, so pointing --dataset at either one works without further argument.
LAYOUT: list[tuple[str, str, str]] = [
    ("specifications", "*.md", "specification"),
    ("submittals", "*.md", "submittal"),
    ("rfis", "*.md", "RFI"),
    ("meeting_minutes", "*.md", "meeting_minutes"),
    ("change_orders", "*.md", "change_order"),
    ("schedules", "*.csv", "schedule"),
    ("commissioning", "*.md", "commissioning_record"),
    # Seeded so the schedule analysis can be pointed at it. Weather and
    # workforce are read from this log's dated rows rather than supplied as
    # scenario numbers, and without the document in the project there is
    # nothing for a delay day to cite.
    ("site_conditions", "*.csv", "site_conditions"),
]


def sources(dataset: Path) -> list[tuple[str, Path]]:
    found: list[tuple[str, Path]] = []
    for directory, glob, document_type in LAYOUT:
        found.extend((document_type, path) for path in sorted((dataset / directory).glob(glob)))
    return found


def resolve_token(client: httpx.Client, email: str | None) -> str | None:
    """A token from the environment, or one obtained by signing in."""
    token = os.environ.get("ATLAS_API_TOKEN")
    if token:
        return token.strip()
    if not email:
        return None
    password = os.environ.get("ATLAS_API_PASSWORD") or getpass.getpass(f"Password for {email}: ")
    response = client.post("/auth/login", json={"email": email, "password": password})
    if response.status_code == 404:
        # An API that predates authentication. Nothing to send.
        return None
    response.raise_for_status()
    return response.json()["access_token"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload a synthetic Atlas corpus to a running API.")
    parser.add_argument("--api-url", default="http://localhost:8001")
    parser.add_argument("--project-name", default="Atlas Synthetic Demo")
    parser.add_argument(
        "--dataset",
        default="data/synthetic_epc",
        help="corpus directory, relative to the repository root",
    )
    parser.add_argument("--email", help="sign in as this account when authentication is enabled")
    args = parser.parse_args()

    dataset = (ROOT / args.dataset).resolve()
    if not dataset.is_dir():
        print(f"error: no dataset at {dataset}", file=sys.stderr)
        return

    with httpx.Client(base_url=args.api_url, timeout=60) as client:
        token = resolve_token(client, args.email)
        if token:
            client.headers["Authorization"] = f"Bearer {token}"

        projects = client.get("/projects")
        if projects.status_code == 401:
            print(
                "error: the API requires authentication. Pass --email, or set ATLAS_API_TOKEN.",
                file=sys.stderr,
            )
            return
        projects.raise_for_status()
        existing = next((item for item in projects.json() if item["name"] == args.project_name), None)
        if existing:
            project_id = existing["id"]
        else:
            project = client.post("/projects", json={"name": args.project_name})
            project.raise_for_status()
            project_id = project.json()["id"]
        existing_files = {item["filename"] for item in client.get(f"/projects/{project_id}/documents").json()}
        for document_type, path in sources(dataset):
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
