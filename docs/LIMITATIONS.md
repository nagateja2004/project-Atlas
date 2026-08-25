# Limitations

## Security and tenancy

- Authentication and per-project roles exist and are **enabled on the live deployment** (`ATLAS_AUTH_ENABLED=true`). They ship **disabled by default**, so an unconfigured deployment is still open to anyone who can reach the URL. With it off, `project_id` remains data scoping rather than authorization.
- Tokens are signed and short-lived but cannot be revoked. Deactivating a user takes effect immediately because the account is re-read on every request; an issued token otherwise remains valid until it expires.
- `POST /auth/users` is gated on holding `admin` on any project, not on a platform-wide administrator flag. In a genuinely multi-tenant deployment that is too coarse: an admin of one project can create accounts.
- There is no password reset flow, no rate limiting on `/auth/login`, and no multi-factor support. Repeated login attempts are logged but not throttled.

- Tenant quotas, signed URLs, and production tenant isolation are not implemented. Nothing meters or bills a tenant, and object access is not signed.
- Prompt-injection checks and an untrusted-evidence boundary exist, but adversarial coverage and operational policy tuning are incomplete.
- Upload malware scanning, content disarm, encryption-key management, retention enforcement, and formal audit immutability are not implemented.

## Data and integrations

- All EPC documents, equipment, vendors, costs, dates, shipment events, and requirements are synthetic.
- There is no live AIS, vessel position, carrier, vendor, geospatial, weather, ERP, QMS, or P6 integration. Supply-chain responses are explicitly synthetic simulations.
- Computer-vision site evidence is roadmap only.
- Original documents use local filesystem storage, not production object storage.
- NetworkX/JSON is a lightweight prototype, not production graph storage or governed master data.

## AI and retrieval

- Groq requires a configured API key. Embeddings run in-process from a self-hosted `all-MiniLM-L6-v2` model, not a managed embedding service; first use downloads model weights.
- **Open RFIs in the retrieved set block the whole answer.** The evidence gate in
  `_evidence_sufficiency` rejects a context when *any* selected chunk has a
  non-approved status. `_approval_status` falls back to `rfi_status`, so a single
  **open** RFI yields `"open"`, which is absent from `APPROVED_EVIDENCE`, and the
  request returns `INSUFFICIENT_EVIDENCE` even when the answer is fully supported
  by an approved specification retrieved alongside it. This — not retrieval
  quality — is why advanced correct-document rate, correct-page rate and citation
  precision were `0.0` in an earlier evaluation. That is no longer the failure
  mode — on the current 16-case held-out split advanced scores `0.8462`
  correct-document, `0.6923` correct-page and `0.2432` citation precision — but
  the gate still fails a whole context rather than excluding the offending chunk.
  The conservative fix is to *exclude* non-current chunks and judge the remainder,
  as `context._revision_conflicts` already does for superseded revisions, rather
  than failing the entire context. Left unchanged pending a decision, because it
  makes the system answer where it currently refuses.

- **The copilot refuses a specific class of phrasing, and it is not root-caused.**
  Measured on the deployment, *"Is the ArcLine switchgear submittal compliant with
  the interrupting rating requirement?"* returns three supported cited claims and
  *"What battery autonomy is required for the UPS?"* answers on 3 of 3 attempts,
  but *"What interrupting rating does the switchgear specification require?"*
  refuses on 3 of 3, at 131–141 context tokens against 428 for the phrasing that
  works. Stable per phrasing, so structural rather than random. Rejected claims
  now log their citations, the terms absent from the evidence, and the term
  overlap, so this can be diagnosed rather than guessed at.

- The latest held-out comparison does not support claiming that advanced RAG is better overall. On **16 held-out questions** advanced wins ranking and cost — Recall@12 `1.0` vs `0.9231`, MRR `0.7521` vs `0.6269`, correct-document rate `0.8462` vs `0.6923`, and 2.6× fewer input tokens — but loses citation precision (`0.2432` vs `0.3226`) and completeness. The per-case data shows why: the correct page is often retrieved at rank six while the responder cites its top three. **This is a known open item, not a fixed one.**
- The earlier headline of `0.667` against a baseline `1.0` came from a **three-case** test split and is not comparable. Widening the split surfaced two harness defects, both since fixed: the parameter search broke ties on measured wall-clock latency, so consecutive runs of the same script selected different hyperparameters, and citation precision counted duplicate citations separately, rewarding a pipeline for citing one page three times.
- Synthetic evaluation and deterministic test doubles do not measure live Groq quality, latency, token billing, or production concurrency.
- Citations reduce unsupported answers but do not replace engineering review. Conflicting or insufficient evidence may still require manual investigation.

## Engineering workflows

- Compliance rules cover the planted schemas and unit conversions; they are not a certified code/standards checker.
- Schedule results are deterministic scenario analysis, not trained historical prediction. Prediction error is measured over **12 labelled cases** across 6 tasks and 2 analysis dates, every actual taken from a `delay_days` value in the schedule CSV: mean absolute error `1.5` days, max `3`, lead time `0`–`65` days. The spread shows a bias the mean hides — procurement cases are exact, and every downstream case is over-predicted by the same 3 days.
- Weather and workforce are derived from a dated site conditions log rather than supplied as scenario numbers, so each delay day cites the rows behind it. The log itself is synthetic, and availability is measured only over days not already lost to weather so a lost day is not charged twice. There is still **no live weather feed** — a real deployment would need a validated adapter with source evidence and fallback states.
- Commissioning pass/fail and readiness use visible project rules, not certification logic. Electronic signatures and offline/mobile execution are absent.
- Mitigation costs/days are calculated from supplied scenario inputs. They are not quotations, commitments, or approved change orders until a human records a decision.

## Operations and evidence

- Queue-backed ingestion, autoscaling, production observability, backups, disaster recovery, load tests, and SLOs are roadmap work.
- Uploaded originals (`ATLAS_UPLOAD_DIR`) and the graph export (`ATLAS_GRAPH_DIR`) are plain filesystem paths, not object storage. On the Render target they sit on an ephemeral container filesystem, so database rows and their citations outlive the files behind them across a deploy or restart; the single-instance AWS target mounts both on named volumes, which makes them durable per instance but still unreplicated and unbacked-up.
- The single-instance AWS target has no redundancy by construction: one instance hosts the API, dashboard, PostgreSQL, and Qdrant, so losing it loses the running deployment until it is rebuilt and re-seeded.
- Measured latencies are in-process evaluation-harness values, not deployment SLOs.
- Manual effort and hours saved are `NOT_MEASURED`. The brief asks for hours saved; we do not invent one, and measuring it is the first deliverable of a pilot.
- Supply-chain alerting timeliness is measured over **8 synthetic events** across 5 shipments (latency `20`–`420` minutes, median `75`, 6 of 8 inside two hours). These are simulated events with authored timestamps, not observed operational latencies.
- A root project license is missing and must be resolved before public-repository publication.
