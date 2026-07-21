# Built versus roadmap

| Capability | Built now | Roadmap / limitation |
| --- | --- | --- |
| FastAPI API and Next.js dashboard | Yes; one monolith and one typed dashboard client. | Deployment hardening and observability. |
| Project data isolation | Yes; project ID filters documents, vectors, findings, records, and graphs. | Authentication/RBAC enforcement is not implemented. |
| Document ingestion | Yes; PDF text, CSV schedules, Markdown/text, conditional OCR, Qdrant indexing, failure status. | Production object storage, queueing, malware scanning, and migrations. |
| Knowledge/RFI | Yes; LangGraph workflows, project-filtered retrieval, citations, possible-match wording. | Production evals with real embeddings/LLM latency and feedback loops. |
| Compliance | Yes; deterministic comparison, audit trail, reviewer approval/rejection. | Broader schemas, formal rule governance, and real project validation. |
| Schedule | Yes; dependency validation, CPM/float, propagation, scenario risk evidence. | Calendar/resource constraints and calibrated historical forecasting. |
| Commissioning | Yes; procedure retrieval, observations, coverage, records, non-conformances. | Full workflow approvals, signatures, and mobile/offline use. |
| Procurement | Demo mock only; no live tracking claim. | Licensed AIS, geospatial, vendor, and carrier integrations. |

## Known limitations

- The synthetic corpus is fictional and not an official TIA-942, BICSI, Uptime Institute, or other third-party standard.
- Local demo mode has no authentication; do not expose it publicly.
- Production database migrations are not provisioned; local schema creation is enabled for Compose.
- Knowledge-answer generation and optional narrative enrichment require `ATLAS_GEMINI_API_KEY`; embeddings are local and deterministic.
- The evaluation’s latency is an isolated in-process API measurement, not a production latency SLA.
- No cached answer is presented as a live response. The live demo seeds and calls the active API; the isolated evaluator explicitly uses deterministic test doubles.
- Prompt-injection checks and untrusted-evidence instructions are implemented; production needs adversarial evaluation, monitoring, and policy tuning.

## Metric provenance

| Claim | Value | Provenance |
| --- | --- | --- |
| Synthetic ingestion | 27/27 completed | Measured: `scripts/evaluate_synthetic.py`. |
| Compliance | TP/FP/FN/TN 6/0/0/6; precision/recall/F1 1.0/1.0/1.0 | Measured: synthetic ground truth evaluation. |
| RFI | Recall@5 1.0; both expected pairs rank 1 | Measured: synthetic ground truth evaluation. |
| Citation correctness | 17/17 | Measured: synthetic evaluation citation checks. |
| Schedule | 35-day lead time | Measured: synthetic scenario; not historical prediction. |
| Commissioning | 100% coverage | Measured: seeded UPS procedure evaluation. |
| Live procurement tracking | None | Implemented roadmap/mock limitation. |
