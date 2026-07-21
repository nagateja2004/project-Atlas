# Project Atlas Synthetic EPC Demo Dataset

**SYNTHETIC EPC DEMO DATA — NOT AN OFFICIAL STANDARD OR REAL PROJECT RECORD**

All files in this directory are **synthetic training and demonstration data** for Project Atlas, project `atlas-demo-dc-01`. Names, companies, equipment, dates, clauses, test steps, and findings are fictional. The documents use EPC-style language only; no requirement in this dataset is represented as an official TIA-942, BICSI, Uptime Institute, UL, AHRI, or other standard requirement.

## Contents

- `specifications/`: owner design requirements for a UPS, CRAC unit, and low-voltage switchgear.
- `submittals/`: six vendor proposals, three conforming and three deliberately non-conforming.
- `rfis/`: twelve EPC RFIs, including two near-duplicate pairs.
- `meeting_minutes/` and `change_orders/`: project-context examples.
- `schedules/`: a dependency-based delivery and commissioning schedule with one critical switchgear delay.
- `commissioning/`: three procedural templates for UPS, CRAC, and switchgear.
- `metadata/`: project-scoped vendor and equipment records.
- `supply_chain/`: five critical-equipment shipment simulations with three supplier tiers, milestones, two timestamped risk events, schedule links, and alternatives. These contain no live positions.
- `ground_truth.json`: expected results for repeatable demonstrations and tests.

The answer truth set has fixed `development` and `test` labels. Retrieval parameters may be selected only on the development cases; the test cases are reserved for one final comparison. Two explicitly unanswerable questions measure insufficient-evidence behavior.

## Planted compliance cases

| Submittal | Expected finding | Spec reference |
| --- | --- | --- |
| `UPS-002` | 415/240 V input/output offered instead of 480/277 V | `UPS_Specification.md`, p. 2, clause 2.2.1 |
| `UPS-002` | 10-minute battery autonomy offered instead of 15 minutes | `UPS_Specification.md`, p. 2, clause 2.2.4 |
| `CRAC-002` | 105 kW sensible capacity offered instead of 120 kW | `CRAC_Specification.md`, p. 2, clause 2.3.1 |
| `CRAC-002` | 12-inch service clearance offered instead of 24 inches | `CRAC_Specification.md`, p. 2, clause 2.4.2 |
| `SWGR-002` | 50 kAIC interrupting rating offered instead of 65 kAIC | `Switchgear_Specification.md`, p. 2, clause 2.2.3 |
| `SWGR-002` | Type 1 enclosure offered instead of the project’s synthetic Type 2B arc-resistance requirement | `Switchgear_Specification.md`, p. 2, clause 2.3.4 |

The three `-001` submittals are intended to be clean controls. The compliance truth set contains exactly six findings and no expected findings for the clean controls.

## Planted RFI similarity cases

- `RFI-003` and `RFI-009` both request confirmation of UPS bypass-maintenance clearance at UPS-A.
- `RFI-005` and `RFI-011` both request confirmation of the switchgear delivery route and the removable louvre sequence.

The pairs differ in phrasing, authors, and dates; neither pair is an exact textual duplicate. Expected answers and source-page references are in `ground_truth.json`.

## Planted schedule case

`T-140`, the switchgear delivery milestone, is forecast 35 calendar days after its baseline finish. Its successors (`T-160`, `T-170`, and `T-180`) form the electrical energization critical path. The delay is intentionally linked in the meeting minutes and change order context, but no schedule assertion is based on a real supplier or real project.

## Idempotent vertical scenario

`POST /projects/{project_id}/demo/vertical-scenario` connects the planted `SWGR-002` 50 kAIC deviation to a vendor resubmission, the synthetic `SYN-SHP-001` ETA, `T-140` schedule float, SWGR-A commissioning readiness, and deterministic mitigation scenarios. Repeating the request reuses the same findings, five-stage impact chain, shipment event, and mitigation simulation.

## Use

Ingest each document with `project_id = atlas-demo-dc-01`; apply the same project ID to every Qdrant point. Page markers in Markdown (`## Page N`) are the citation anchors for this demo corpus.
