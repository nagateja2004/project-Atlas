# API reference

The running service serves interactive OpenAPI documentation at `/docs` and the
raw schema at `/openapi.json`; those are authoritative. The table below is
generated from that schema so it cannot drift out of date.

Every project resource is scoped by the path `project_id`.

**When `ATLAS_AUTH_ENABLED=true`** (as on the live deployment), requests carry a
bearer token from `POST /auth/login`. Passwords are hashed with `hashlib.scrypt` and session tokens are HMAC-SHA256 signed, both from the standard library. A user is global; `project_members` grants **viewer**, **reviewer** or **admin** per project. Reading needs viewer, mutating needs reviewer, managing members needs admin. A non-member receives **404, not 403**, because a 403 would confirm the project exists. Read operations require viewer, mutating operations require reviewer, and
member management requires admin.

**When it is disabled** — the default — `project_id` filtering is data scoping,
**not** authorization: any caller that can reach the service can read any
project. Keep such a deployment behind an authenticated gateway.

49 operations across 14 areas.

### Health

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Health |
| `GET` | `/ready` | Ready |

### Projects

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/projects` | List Projects |
| `POST` | `/projects` | Create Project |

### Documents & ingestion

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/projects/{project_id}/documents` | List Documents |
| `POST` | `/projects/{project_id}/documents` | Upload Document |
| `POST` | `/projects/{project_id}/documents/{document_id}/ingest` | Ingest Document |
| `GET` | `/projects/{project_id}/documents/{document_id}/ingestion` | Ingestion Status |

### Retrieval & knowledge

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/projects/{project_id}/context` | Build Context |
| `POST` | `/projects/{project_id}/copilot` | Project Copilot |
| `GET` | `/projects/{project_id}/graph` | Project Graph |
| `POST` | `/projects/{project_id}/query-plan` | Query Plan |
| `POST` | `/projects/{project_id}/retrieve` | Retrieve |
| `POST` | `/projects/{project_id}/rfis/matches` | Rfi Matches |

### Compliance

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/projects/{project_id}/compliance/checks` | Run Compliance Check |
| `GET` | `/projects/{project_id}/compliance/evaluation` | Compliance Evaluation |
| `GET` | `/projects/{project_id}/compliance/findings` | List Compliance Findings |
| `PATCH` | `/projects/{project_id}/compliance/findings/{finding_id}/review` | Review Compliance Finding |

### Schedule

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/projects/{project_id}/schedule/analysis` | Analyze Schedule |
| `GET` | `/projects/{project_id}/schedule/snapshots` | Schedule Snapshots |

### Commissioning

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/projects/{project_id}/commissioning/procedures/{procedure_document_id}` | Commissioning Procedure |
| `GET` | `/projects/{project_id}/commissioning/readiness/{equipment_id}` | Commissioning Readiness |
| `POST` | `/projects/{project_id}/commissioning/records` | Record Commissioning Test |
| `GET` | `/projects/{project_id}/commissioning/records/{record_id}` | Commissioning Test Record |

### Equipment digital thread

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/projects/{project_id}/equipment/{equipment_id}/digital-thread` | Get Equipment Digital Thread |
| `GET` | `/projects/{project_id}/equipment/{equipment_id}/impact-chain` | Get Equipment Impact Chain |
| `POST` | `/projects/{project_id}/equipment/{equipment_id}/impact-chain/events` | Create Equipment Impact Event |

### Supply chain & procurement

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/projects/{project_id}/procurement/dashboard` | Procurement Dashboard |
| `GET` | `/projects/{project_id}/supply-chain/alerts` | Supply Chain Alerts |
| `GET` | `/projects/{project_id}/supply-chain/assessments` | Supply Chain Assessments |
| `POST` | `/projects/{project_id}/supply-chain/import` | Import Supply Chain Csv |
| `POST` | `/projects/{project_id}/supply-chain/seed` | Seed Supply Chain |
| `GET` | `/projects/{project_id}/supply-chain/shipments` | Supply Chain Shipments |
| `GET` | `/projects/{project_id}/supply-chain/shipments/{shipment_id}/alternatives` | Get Supply Chain Alternatives |
| `POST` | `/projects/{project_id}/supply-chain/shipments/{shipment_id}/assessment` | Assess Supply Chain Shipment |
| `GET` | `/projects/{project_id}/supply-chain/shipments/{shipment_id}/risk` | Get Supply Chain Risk |
| `POST` | `/projects/{project_id}/supply-chain/shipments/{shipment_id}/risk-events` | Add Supply Chain Risk Event |
| `GET` | `/projects/{project_id}/supply-chain/shipments/{shipment_id}/timeline` | Supply Chain Timeline |

### Impact chain

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/projects/{project_id}/impact-chains` | Create Impact Chain |
| `POST` | `/projects/{project_id}/impact-chains/{chain_id}/decision` | Decide Impact Chain |

### Mitigations

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/mitigations/simulate` | Simulate Counterfactual Mitigations |
| `POST` | `/api/mitigations/{simulation_id}/select` | Select Counterfactual Mitigation |

### Evaluation

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/evaluation/run` | Create Evaluation Run |
| `GET` | `/api/evaluation/runs/{run_id}` | Read Evaluation Run |

### Benchmarks

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/benchmarks` | Create Workflow Benchmark |
| `GET` | `/api/benchmarks/summary` | Read Workflow Benchmark Summary |

### Demo scenario

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/projects/{project_id}/demo/reset` | Reset Demo |
| `POST` | `/projects/{project_id}/demo/vertical-scenario` | Create Vertical Demo Scenario |
| `GET` | `/projects/{project_id}/executive-summary` | Get Executive Summary |

## Conventions

**Errors** use one envelope: `{ "error": { "code", "message", "details"? } }`.
Notable codes: `validation_error` (422), `prompt_injection_detected` (422),
`generation_unavailable` (503, no `GROQ_API_KEY`), `model_gateway_error` (502,
provider failure), `embedding_unavailable` (503, embedding model unloadable),
`embedding_dimension_mismatch` (409, collection width disagrees with the
configured embedder), `ingestion_timeout` (504), `invalid_file_size` (413).

**Uploads** are multipart with fields `document_type` and `file`. Accepted
extensions are `.pdf`, `.csv`, `.md`, `.txt`; schedules must be `.csv` and
non-schedules must not be. Duplicate content in the same project returns 409 on a
SHA-256 match. Ingestion runs synchronously inside the request and is bounded by
`ATLAS_INGESTION_TIMEOUT_SECONDS`.

**Copilot routing.** `POST /projects/{project_id}/query-plan` returns the
classified intent plus the `service` and `endpoint` a client could dispatch to.
`POST /projects/{project_id}/copilot` always answers from knowledge retrieval
regardless of that intent — it does not delegate to the compliance, schedule,
commissioning, or procurement services. Call those endpoints directly.

**Evidence.** Copilot answers carry per-claim support status, citation IDs with
exact supporting spans, revision conflicts, and a content-safe `trace` (stage
latency, candidate and selected chunk IDs, context tokens, retry count, status).
Unsupported claims are dropped; if none survive the answer becomes
`INSUFFICIENT_EVIDENCE` rather than being returned unverified.
