# Demo recording checklist

## Before recording

- [ ] Run `python3 scripts/evaluate_synthetic.py`; keep its JSON output with the recording assets.
- [ ] Run `./scripts/start_demo.sh` and wait for the seed confirmation (27 freshly ingested documents).
- [ ] Open `http://localhost:3000` at 1920×1080 and select the newly seeded project.
- [ ] Confirm `/ready` shows API, database, and Qdrant as `ok`.
- [ ] Confirm the dashboard labels procurement as roadmap/mock and marks AI assessment versus reviewer-approved records.
- [ ] Ensure the browser, terminal, and recording contain no Gemini key or `.env` content.

## Capture order

- [ ] Dashboard and document ingestion status.
- [ ] Knowledge answer with inline UPS citation.
- [ ] UPS compliance deviation and reviewer approval.
- [ ] T-140 schedule risk and T-120→T-180 chain.
- [ ] RFI-009 matched to RFI-003 at rank 1.
- [ ] UPS procedure completed and test record coverage shown.
- [ ] Knowledge graph, procurement roadmap, and architecture slide.

## Backup and handoff

- [ ] Save a 1920×1080 screenshot after each capture step using the filenames in `docs/BACKUP_SCREENSHOTS.md`.
- [ ] Save the screen recording and the evaluator JSON together.
- [ ] If live Gemini calls fail, show the recorded video and evaluator JSON; do not describe a cached response as a live result.
- [ ] State that all documents and requirements are synthetic and not official external standards.
