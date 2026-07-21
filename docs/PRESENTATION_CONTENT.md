# Nine-slide presentation content

## 1. Project Atlas — evidence-led EPC delivery intelligence

- Problem: project evidence is spread across specifications, vendor submittals, RFIs, schedules, and commissioning procedures.
- Solution: a project-scoped workspace that returns evidence, flags deterministic comparisons, and records reviewer decisions.
- Label: product statement; no external performance statistic claimed.

## 2. What is built

- Knowledge Copilot, RFI Intelligence, Compliance, Schedule Intelligence, Commissioning Copilot, knowledge graph, and dashboard.
- Procurement is dashboard-compatible demo/roadmap depth only.
- Source: implemented system and architecture diagram.

## 3. Architecture

- Next.js dashboard → FastAPI monolith → PostgreSQL, Qdrant, NetworkX JSON.
- PyMuPDF/CSV extraction, conditional OCR fallback, local deterministic embeddings, Gemini for optional generation, LangGraph for Knowledge/RFI.
- Source: `docs/ARCHITECTURE.mermaid`.

## 4. Evidence in, citations out

- 27/27 synthetic documents uploaded and ingested in the evaluation.
- Every vector and retrieval is project-scoped; Knowledge answers include document/page/section citations.
- Measured: 17/17 citation checks correct in the synthetic evaluation.

## 5. Compliance with human control

- Deterministic normalized comparison catches planted deviations; optional LLM use is limited to evidence-backed explanation.
- Reviewer approve/reject actions are persisted in the audit trail.
- Measured: TP 6, FP 0, FN 0; precision 1.0, recall 1.0 on planted synthetic cases.

## 6. Schedule and RFI intelligence

- T-140 switchgear delivery scenario propagates through T-160, T-170, and T-180.
- Measured: 35-day synthetic risk lead time; both planted RFI pairs rank 1, Recall@5 1.0.
- Label schedule output as scenario-based, not historical prediction.

## 7. Commissioning and traceability

- Ordered procedures accept engineer observations, calculate coverage, create test records, and create non-conformances for failures.
- Measured: 100% step coverage in the seeded UPS procedure evaluation.

## 8. Built versus roadmap

- Built: document intelligence, cited retrieval, deterministic compliance/schedule analysis, review/test records, graph export, UI.
- Roadmap: live AIS/geospatial/vendor tracking, production auth/RBAC, migrations, real-world model validation.
- Source: `docs/ROADMAP.md`.

## 9. Close: measured prototype, honest roadmap

- “Atlas turns a synthetic EPC corpus into cited, project-scoped engineering workflows.”
- Show the metric panel: 27/27 ingestion, 6/0/0 compliance, 17/17 citations, Recall@5 1.0, 35-day scenario lead time, 100% commissioning coverage.
- All values are measured locally by the evaluation suite; no cost, time-saving, or live-tracking claim is made.
