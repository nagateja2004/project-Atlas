# Project Atlas — the complete guide


## How to use this document

| If you want to… | Read |
| --- | --- |
| Understand what we were asked to build | Part 1 |
| Understand the construction words (RFI, submittal, commissioning…) | Part 2 |
| Understand the AI words (RAG, embedding, reranking…) | Part 3 |
| Know exactly how our product works, module by module | Part 4 |
| Open the live deployment, or explain how it ships | Part 4.12 |
| Know what competitors built and how | Part 5 |
| Explain why we are different | Part 6 |
| Quote global market numbers | Part 7 |
| Quote India market numbers | Part 8 |
| Answer "does it scale?" | Part 9 |
| Answer "what have you NOT built?" | Part 10 |
| Grab a number fast, on stage | Part 11 |
| Check a source | Part 12 |

---
---

# PART 1 — The problem statement

## 1.1 What the hackathon asked for

**ET AI Hackathon 2026 · Problem Statement 04 — AI Intelligence Platform for Data Centre EPC Project Delivery**
Theme: Industrial Intelligence / Infrastructure Construction / Quality Management

### The context they gave us

India is in the middle of a data centre construction boom. National capacity is going from roughly 900 MW in 2024 to over 2,700 MW by 2027 — that is capital deployment of $15 billion or more.

A single hyperscale data centre facility involves:

- **15,000 to 40,000 equipment line items**
- **Up to 200 concurrent trade contractors**
- **Commissioning sequences spanning thousands of individual test procedures** across power, cooling, and IT infrastructure
- **Zero tolerance for errors** that would compromise the future uptime SLA

The hackathon brief states that a 2024 Turner & Townsend survey found **67% of data centre EPC projects in Asia-Pacific experienced schedule overruns exceeding 10%**, with procurement misalignment and commissioning failures as the leading causes. We could not find that figure in the source and do not assert it — see the note directly below, and use the verified figure instead.

> ⚠️ **Honesty note:** we tried to verify this 67% figure directly in the Turner & Townsend source and could not find it. What we *did* verify from their Data Centre Cost Index 2024 is that **~80% of respondents report delays to the manufacture or delivery of critical equipment**. We use the 80% figure in our pitch and flag the 67% as unverified. If a judge quotes the 67%, say it comes from the problem statement.

### The core diagnosis in the brief

> "The underlying problem is **information fragmentation**: specifications, vendor submittals, test records, RFI logs, and change orders exist in disconnected systems, and the intelligence to connect them never gets built."

That single sentence is the whole reason our product exists. Read it twice.

### The challenge statement

> "Build an AI-powered EPC Project Intelligence platform for data centre construction that unifies project documents, specifications, schedules, procurement data, and quality records into a **living intelligence layer** — enabling proactive schedule management, automated compliance and quality checking, and real-time commissioning support across the full project lifecycle."

### What they suggested we might build

The brief listed five example areas (explicitly "illustrative only"):

1. **Specification & Quality Compliance Agent** — ingests thousands of pages of specs and client requirements, automatically checks procurement orders, vendor submittals and shop drawings for deviations, flags non-conformances before they reach site.
2. **Predictive Schedule Risk Engine** — multi-agent system analysing schedules against procurement status, equipment lead times, workforce and weather; identifies critical path risks weeks in advance and generates mitigation options, not just alerts.
3. **Supply Chain Visibility & Risk Agent** — geospatial AI tracking critical equipment shipments (UPS systems, generators, cooling towers, switchgear) across multi-tier suppliers.
4. **Commissioning Quality Assurance Copilot** — AI trained on data centre commissioning standards (TIA-942, BICSI, Uptime Institute Tier specs) that guides engineers through integrated test sequences, auto-generates test records, flags non-conformances, builds the as-commissioned quality documentation package.
5. **Project Knowledge & RFI Intelligence Agent** — RAG-powered conversational layer over all project documents that answers technical and contractual queries in seconds, with citations, and identifies when similar RFIs have been resolved before.

### Expected deliverables

Working prototype · Architecture diagram · Presentation deck · Demo video

### How we are judged

| Criteria | Weight |
| --- | --- |
| Innovation | 25% |
| Business Impact | 25% |
| Technical Excellence | 20% |
| Scalability | 15% |
| User Experience | 15% |

**Evaluation focus** (their words): specification compliance detection accuracy on test cases, schedule risk prediction lead time versus actual delays, supply chain visibility depth and alerting timeliness, commissioning test automation coverage, and demonstrated reduction in manual coordination effort — **measured in hours, not percentages**.

> ⚠️ That last phrase matters enormously. They want *hours saved*. Our evaluation currently reports `manual_hours: NOT_MEASURED` because we have not run a real time study. **We do not fake this number.** See Part 10.

## 1.2 The problem in one paragraph, in plain English

When you build a data centre, you write a document saying "the switchgear must handle at least 65 kAIC of fault current." A vendor sends back an offer saying "here is our switchgear, it handles 50 kAIC." Someone has to notice that mismatch. Today that someone is a human being reading a PDF. If they miss it — and with 40,000 line items they will miss some — the wrong equipment gets ordered, arrives on site, fails its commissioning test months later, and the whole building opens late. A three-month delay on a 50 MW campus costs **$30–150 million**.

The information to catch it existed the whole time. It was just in five different places, and nothing connected them.

---
---

# PART 2 — Every construction word, explained simply

You do not need a construction background to present this. But you must not be caught out by a judge using a term you do not know.

## 2.1 The industry itself

**EPC — Engineering, Procurement, Construction**
A contract where one company does everything: designs it, buys the equipment, and builds it. Then hands over the keys. So an "EPC contractor" is the company actually delivering the building. *Examples in India: L&T Construction, Tata Projects, Sterling & Wilson.*

**PMC — Project Management Consultancy**
A firm the *owner* hires to supervise the EPC contractor on their behalf. They check the work. Think referee.

**Owner / Operator**
The company who will own and run the data centre. *Examples: NTT, STT GDC, Sify, CtrlS, Yotta, AdaniConneX.*

**Trade contractor / subcontractor**
A specialist company doing one part — electrical, cooling, fire suppression, cabling. A hyperscale build has **up to 200 working at the same time**.

**MEP — Mechanical, Electrical, Plumbing**
The systems inside a building that make it work. In a data centre, MEP *is* the building — power and cooling are the whole point.

**Hyperscale**
A very large data centre, typically built for a cloud provider (AWS, Azure, Google). Contrast with "colocation," where many customers rent space in one facility.

**MW (megawatt) as a unit of size**
Data centres are measured by how much electricity they can deliver to servers, not floor area. "A 50 MW campus" tells you its scale. India's total capacity is around 1,100–1,500 MW today.

## 2.2 The documents — this is the heart of it

**Specification (spec)**
The document that says what is *required*. Written by the designer or the client. Example line: *"Short-circuit interrupting rating: not less than 65 kAIC at 480 V."* Organised into numbered clauses like **2.2.3** so people can point at exactly one requirement.

**Submittal**
The vendor's reply: *"here is the actual product I propose to supply, with its specifications."* The whole review process is comparing the submittal against the spec, line by line, to see if it complies.
👉 **This is the single most important pair of words in the project.** Spec = what we asked for. Submittal = what they offered. Atlas compares them automatically.

**Shop drawing**
A detailed manufacturing/installation drawing from the vendor, submitted for approval alongside the submittal.

**RFI — Request For Information**
A formal written question from the contractor to the designer or client when a document is unclear or contradictory. *"The drawing shows 900 mm clearance but the spec says 1,000 mm — which applies?"*
It gets a written answer, and that answer becomes a contractual record.
- **Why it matters:** each RFI costs about **$1,080** to respond to, and there are roughly **9.9 RFIs per $1 million** of construction value — around **$860,000 on a typical project**.
- **Why it matters more:** the same question gets asked again by a different person six months later, because nobody can find the first answer. That is pure waste, and it is exactly what our RFI matching feature attacks.

**Change order (CO)**
A formal agreement to change the scope, price, or schedule after the contract is signed.

**Meeting minutes (MM)**
The written record of a project meeting. Often where a decision actually lives — which is why we ingest them.

**Revision / approval status**
Documents change. A spec might be at Revision C. Statuses you will see: *draft, for review, approved, superseded,* and **IFC — Issued For Construction** (the version you are actually allowed to build from).
👉 Atlas tracks this, because answering from a superseded revision is worse than not answering.

**Punch list / snag list**
The list of small unfinished items found near the end of a project.

## 2.3 Schedule words

**Primavera P6**
The industry-standard scheduling software for large construction. Big, expensive, and usually a silo — the schedule lives there and nowhere else.

**Task / activity**
One piece of work with a start, a finish and a duration. In our demo data they have IDs like **T-140**.

**Dependency / predecessor**
Task B cannot start until Task A finishes. *You cannot install the switchgear until it has been delivered.*

**CPM — Critical Path Method**
The standard maths for scheduling. You lay out every task and its dependencies, and calculate the longest chain from start to finish. That longest chain is the **critical path** — the sequence that determines the project's end date.
👉 **Key insight:** if a task on the critical path slips by one day, the whole project slips by one day.

**Float (also "slack")**
How many days a task can slip *before* it starts delaying the project. A task with 7 days of float can be 7 days late for free. On day 8, the project moves.
👉 **This is the number that makes our demo land.** A 35-day delay against 7 days of float = **28 days of real, unrecoverable exposure**.

**Lead time**
How long between ordering equipment and it arriving. Switchgear and UPS systems can be many months. This is why procurement misalignment kills data centre schedules.

**Milestone**
A zero-duration marker for something important. *"SWGR-A delivered."*

## 2.4 Quality and commissioning words

**Commissioning (Cx)**
The process at the end of construction where you *prove* everything works: energise it, test it, load it, fail it deliberately, and document all of it. In a data centre this is enormous — thousands of test procedures — because the facility has to hold a 99.99%+ uptime promise for years.

**Commissioning levels (L1–L5)**
Roughly: factory testing → delivery checks → pre-functional checks → functional testing → integrated systems testing (everything running together, including simulated power failure).

**IST — Integrated Systems Test**
The final, biggest test. Kill the utility power, watch the UPS carry the load, watch the generators start, watch cooling ride through. If this fails, you are not opening.

**Acceptance criterion**
The measurable rule that decides pass or fail for one test step. *"Battery must support full load for not less than 10 minutes."*

**NCR — Non-Conformance Report**
A formal record that something did not meet its requirement. It has to be tracked, resolved and closed out. NCRs are a legal and quality trail, not just a note.

**Readiness score**
Our own invention (not an industry standard): a 0–100 number saying how ready one piece of equipment is for commissioning. See Part 4.6 for exactly how it is calculated.

**Tier III / Tier IV (Uptime Institute)**
A certification for data centre resilience. Tier III = concurrently maintainable (you can service any component without shutting down). Tier IV = fault tolerant (any single failure, and it keeps running). **Certification requires documented evidence**, which is why an auditable trail is commercially valuable, not just nice.

**TIA-942, BICSI**
Other data centre infrastructure standards, covering cabling, layout and design.
> ⚠️ Our synthetic documents *use realistic language* but do **not** reproduce any real standard. Never claim we check compliance against TIA-942 or Uptime.

**As-built / as-commissioned documentation**
The final package describing what was actually built and tested — handed to the owner. Assembling it is a huge manual job.

## 2.5 Equipment words you will hear in our demo

**UPS — Uninterruptible Power Supply**
Battery system that carries the load in the seconds between utility power failing and generators starting.

**Switchgear (SWGR)**
The big electrical assembly that distributes and protects power. Contains breakers.

**kAIC — kilo-Amperes Interrupting Capacity**
How much fault current a breaker can safely interrupt without exploding. If a fault produces 65 kA and your breaker is rated for 50 kA, it fails catastrophically.
👉 **This is our demo's deviation.** Spec requires **not less than 65 kAIC**; the ArcLine submittal offers **50 kAIC**. That is a genuine safety non-conformance, not a paperwork nit.

**CRAC — Computer Room Air Conditioning**
The cooling units.

**Arc-resistant enclosure**
Switchgear built to contain an internal arc flash explosion. Our demo also has a planted enclosure-type deviation.

**Sensible cooling capacity**
The portion of a cooling unit's capacity that actually lowers air temperature (versus removing humidity). Measured in kW.

---
---

# PART 3 — Every AI word, explained simply

## 3.1 The core idea

**LLM — Large Language Model**
The thing behind ChatGPT. Give it text, it predicts good text back. Brilliant at language. **Cannot be trusted with arithmetic or facts it was not given**, because it will produce fluent, confident, wrong answers.

**Hallucination**
When an LLM invents something that sounds right and is not. In casual chat this is annoying. In a document telling an engineer what fault rating to install, it is a safety incident.
👉 Everything about Atlas's architecture is a response to this one word.

**RAG — Retrieval-Augmented Generation**
Instead of trusting the model's memory, you:
1. **Retrieve** the relevant pieces of the customer's own documents,
2. Paste them into the prompt,
3. Ask the model to answer **using only those pieces**.

Analogy: an open-book exam where you also hand the student the exact three pages, and require them to cite page numbers.

## 3.2 How documents become searchable

**Ingestion**
Reading a file and turning it into something searchable. For us: extract text → split into pieces → store with metadata → index.

**OCR — Optical Character Recognition**
Reading text out of an image. Needed when a PDF is a scan rather than real text. We fall back to OCR only when a page yields fewer than **80 characters** of real text.

**Chunk**
A small piece of a document (we use up to **1,200 characters**, with **160 characters of overlap** so a sentence is never cut in half at a boundary). You retrieve chunks, not whole documents, because a 200-page spec will not fit in a prompt.

**Parent chunk / parent expansion**
A trick: search over *small* chunks (precise), but when you find one, pull in its *larger* surrounding text (context). Best of both. We store `parent_text` at ingestion for exactly this.

**Contextual text vs original text**
We keep two versions of each chunk. The **original** is used for quoting and citations, so what we show the user is exactly what the document says. The **contextual** version — enriched with the document name, section and equipment tag — is what we embed and search, so a chunk that says only "not less than 65 kAIC" is still findable by a search for "switchgear rating."

**Embedding**
Turning text into a list of numbers (a vector) that captures its meaning. Texts with similar meaning get similar numbers. We use **`all-MiniLM-L6-v2`**, producing **384 numbers** per chunk.
👉 This is why searching "battery runtime" can find a document that says "autonomy" — different words, similar meaning, nearby vectors.

**Vector database**
A database built to answer "find me the vectors closest to this one," fast. We use **Qdrant**, collection `atlas_chunks`.

**Metadata / payload**
The labels stored alongside each vector: `project_id`, document name, page, section, equipment tag, revision, approval status. This is what makes citations and project isolation possible.

## 3.3 How search actually works in Atlas

**Dense retrieval (semantic search)**
Search by meaning, using embeddings. Good at synonyms. Bad at exact codes — it may not reliably nail "clause 2.2.3."

**Sparse / lexical retrieval — BM25**
Classic keyword search with clever weighting: rare words count more, and very long documents are penalised so they do not dominate. Excellent at exact identifiers like `SWGR-A` or `2.2.3`.

**Hybrid retrieval**
Run both. Dense catches meaning, BM25 catches exact terms. Neither alone is enough for engineering documents, which are full of both prose and part numbers.

**RRF — Reciprocal Rank Fusion**
How we merge two ranked lists into one. For each result, score = `1 / (60 + rank)` from each list, added together. A chunk ranked well by *both* methods rises to the top.
👉 The beauty of RRF: it only uses **rank position**, never raw scores. So you never have to make a dense similarity score of `0.82` comparable to a BM25 score of `14.3`. That comparison is meaningless, and RRF sidesteps it entirely.

**Reranking / cross-encoder**
The first search is fast and approximate. Reranking is slow and accurate: a second model reads the *question and each candidate chunk together* and scores real relevance. We rerank the top **12** candidates with **`ms-marco-MiniLM-L-6-v2`**.
- *Fast search* = skimming a library shelf by title.
- *Reranking* = actually opening the 12 books you pulled.

**Compression**
Trimming a retrieved chunk down to the sentences that actually answer the question, so the prompt stays inside its token budget (**4,000 tokens** for us).

**Diversity selection**
Avoid handing the model eight near-identical chunks. If two chunks are more than **82%** similar, we keep one and look for something that adds new information.

**Evidence gate** ⭐
Our most important component. Before generating anything, we check: *is what we retrieved actually enough to answer this?* If not, we return **`INSUFFICIENT_EVIDENCE`** instead of an answer.
👉 This is code, not a prompt instruction. It cannot be argued out of refusing.

**Corrective retrieval**
If the gate fails, we rewrite the query once and search again before giving up.

**Citation verification**
After the model writes an answer, we check each claim back against the evidence. Anything unsupported is stripped or the answer is refused. **The model does not get the last word.**

**LangGraph**
A library for building AI workflows as an explicit graph of steps, with conditional branches and loops — rather than one giant prompt. It makes the pipeline inspectable and testable. We use it for the Knowledge and RFI flows.

**Deterministic**
Same input → same output, every time, computed by ordinary code. The opposite of an LLM, which can give you a different answer on Tuesday.
👉 **Every number in Atlas is deterministic.** The LLM never produces a delay figure, a pass/fail, or a readiness score.

**Multi-provider gateway with failover**
We can route LLM calls across several OpenAI-compatible providers in a configured order (`groq,llm7` by default; OpenRouter, Gemini, NVIDIA, Mistral, Ollama and others are registered). If one is rate-limited or down, we try the next. **3 attempts per provider, 30-second timeout.** Judges care about this because it means the demo does not die when a free tier throttles.

**Prompt injection**
An attack where malicious text hidden inside a document tells the model to ignore its instructions. Real risk when you ingest customer files. We have basic guardrails and an untrusted-evidence boundary; adversarial hardening is roadmap.

---
---

# PART 4 — How we implement it (the full picture)

**Product name:** Project Atlas
**One line:** an evidence layer between the documents and the decision.

## 4.0 The architecture in one flow

```
Next.js dashboard  (frontend/src)
        │
        ▼
FastAPI service    (app/main.py, app/api.py)
        │
        ├── Ingestion       → PostgreSQL (metadata, audit) + Qdrant (vectors)
        ├── Knowledge / RFI → LangGraph workflow  (app/workflow.py)
        ├── Compliance      → deterministic rules (app/compliance.py)
        ├── Schedule        → CPM engine          (app/schedule.py)
        ├── Commissioning   → deterministic tests (app/commissioning.py)
        ├── Procurement     → synthetic shipments (app/procurement.py)
        └── Impact Chain    → ties them together  (app/impact_chain.py)
                                    │
                                    ▼
                          Human decision → audit trail
```

**The rule that governs everything:** the language model **rewrites queries, extracts values, and explains**. It never computes a number, never decides pass/fail, and never approves anything.

## 4.1 Ingestion — getting documents in
`app/ingestion.py`

1. **Validate the upload.** Type must be one of `specification, submittal, RFI, meeting_minutes, change_order, schedule, commissioning_record`. Max **50 MB**. We compute a content hash so re-uploading the same file is detected.
2. **Extract text.**
   - PDF → PyMuPDF, page by page.
   - If a page yields fewer than **80 characters**, fall back to **OCR** (Tesseract) — it is a scan.
   - CSV → parsed as a schedule.
   - Markdown / text → read directly.
3. **Find the entities.** A regex pulls out equipment tags — `UPS-[A-Z]…`, `CRAC-\d+`, `SWGR-[A-Z]…` — and specification clause numbers like `2.2.3`. This is what later lets us say "everything about SWGR-A."
4. **Chunk it.** Split into pieces of up to **1,200 characters** with **160 characters of overlap**, respecting section headings and table rows so we never cut a table row in half. Each chunk keeps its `parent_text`.
5. **Embed and index.** Each chunk becomes **384 numbers** via `all-MiniLM-L6-v2`, stored in Qdrant with a payload carrying `project_id`, document id, chunk id, page, section, revision and approval status.
6. **Record it.** Document metadata, page count and ingestion status go to PostgreSQL. Failures are recorded as failures, not silently swallowed.

> **Project isolation:** every vector payload and every database row carries `project_id`, and every query filters on it. There are explicit cross-project tests. This is application-level isolation — it is *not* an authorisation system (see Part 10).

## 4.2 Knowledge Copilot — the cited Q&A
`app/workflow.py` · a LangGraph graph

The exact node sequence, as built:

```
START
  → query_plan          rewrite the question, work out intent + filters
  → route_intent        decide which service this belongs to
  → hybrid_retrieve     dense (top 20) + BM25, project-filtered
  → rrf                 fuse the two rankings, keep top 12
  → rerank              cross-encoder scores the 12 properly
  → parent_expand       pull in surrounding context
  → compress            trim to what answers the question (≤ 4,000 tokens)
  → evidence_gate  ─────┬─ not enough? → corrective_retrieve → back to rrf (once)
                        └─ enough?     → generate
  → generate            LLM writes an answer using ONLY this evidence
  → verify_claims       check every claim against the evidence
  → finalize
END
```

**What each stage is really doing**

- **query_plan** turns "what about its battery?" into a standalone question using conversation history, and extracts filters (equipment tag, document type).
- **hybrid_retrieve** runs dense search (limit **20**) and BM25 over the same project-filtered candidate set.
- **rrf** merges them with `score = Σ 1/(60 + rank)`, keeping **12**.
- **rerank** re-scores those 12 with the cross-encoder; anything under **0.001** is dropped.
- **compress** selects between **5 and 8** chunks, rejecting any that is more than **82%** similar to one already chosen.
- **evidence_gate** checks the retrieved set actually supports an answer — including whether the question demands a specific value and whether we have one.
- **verify_claims** does deterministic support checking plus a semantic check, and strips or refuses on anything unsupported.

**Every answer carries** document, page, section, chunk id and the supporting span — the exact text the claim rests on.

> **A known defect we document rather than hide:** the gate treats a chunk as usable only if its approval status is in `{approved, answered, current, ifc, issued for bid, issued for construction}`. An **open** RFI in the retrieved set therefore fails the whole context, even when an approved specification alongside it fully answers the question. This is written up in `docs/LIMITATIONS.md` with the proposed fix. We left it in deliberately, because changing it makes the system answer where it currently refuses — and that is a decision, not a bug fix.

## 4.3 RFI Intelligence — "has someone already asked this?"
`app/workflow.py` · a second, smaller graph

```
START → retrieve_answered_rfis → rank_possible_matches → END
```

Paste a proposed RFI. We retrieve previously **answered** RFIs in the same project, rank them by similarity, and surface anything above a **0.75** threshold, showing the previous answer and its citation, plus shared equipment tags and shared specification references.

👉 **We never say "duplicate."** The wording is always *"possible previous match."* Declaring a duplicate is a contractual judgement, and that belongs to a human.

## 4.4 Specification & Quality Compliance
`app/compliance.py`

**Six deterministic rules**, each with a regex to find the required value in the spec and the offered value in the submittal:

| Rule | Requirement | Comparison | Severity |
| --- | --- | --- | --- |
| `voltage` | UPS nominal voltage | exact | high |
| `battery_autonomy` | UPS battery autonomy | minimum | high |
| `sensible_capacity` | CRAC net sensible capacity | minimum | high |
| `service_clearance` | Front service clearance | minimum | medium |
| `interrupting_rating` | Switchgear interrupting rating | minimum | high |
| `enclosure_type` | Switchgear enclosure type | exact | high |

**Unit normalisation** (`normalize_value`) is what makes the comparison trustworthy:
- `MW → kW` (×1,000), `mm → inches` (÷25.4), `min/mins/minute → minutes`, `in/inch → inches`
- Voltage pairs like `480/277 V` are parsed as a pair, not as a number
- Enclosure text like "Type 1 indoor" normalises to `type1`
- **An unrecognised unit returns "not normalizable" and the finding becomes `NEEDS_REVIEW`** — it never guesses and never crashes

**Outcomes:** `COMPLIANT`, `NON_COMPLIANT`, `NEEDS_REVIEW`, `MISSING_INFORMATION`.

Every finding carries a citation to the spec clause *and* the submittal line. The LLM's only job here is writing the human-readable explanation of a comparison the code already made — and if the LLM is unavailable, we fall back to a deterministic explanation and carry on.

**Human control:** a finding starts as `pending` — labelled in the UI as *"AI assessment — reviewer pending."* An engineer clicks Approve or Reject, and only then does it become an approved record, written to the audit trail.

**Measured:** TP/FP/FN/TN = **6/0/0/6**, precision/recall/F1 = **1.0/1.0/1.0** on 12 labelled synthetic cases.

## 4.5 Schedule Intelligence
`app/schedule.py`

1. **Load** the schedule from CSV into tasks with dependencies, durations and dates.
2. **Validate dependencies** — catch cycles and references to tasks that do not exist.
3. **Calculate CPM** — forward and backward pass giving early/late start and finish for every task.
4. **Compute total float** for each task.
5. **Propagate delays** — inject a procurement delay at one task and push it through the dependency graph to see what actually moves.
6. **Classify risk** by comparing delay against available float.
7. **Generate mitigations** with their inputs and stated assumptions.

**In our demo:** `T-140` (SWGR-A delivery) → `T-160` (install) → `T-170` (energise critical distribution) → `T-180` (integrated systems test). A 35-day delivery slip against 7 days of float produces **28 days of critical-path exposure**.

**Measured:** predicted delay 35 days, simulated delay 35 days, absolute error **0 days** — on **one** planted case. That is an engine correctness check, not a forecasting accuracy claim.

## 4.6 Commissioning Copilot
`app/commissioning.py`

**Procedure retrieval** — pull an ordered checklist of steps from a commissioning document, each with an instruction, an acceptance criterion, and a citation.

**Deterministic assessment** (`assess`) — given an engineer's typed observation:
1. No observation → `NEEDS_REVIEW`
2. Contains "fail", "does not", "not verified", "missing", "unable" → `FAIL`
3. Extract a number *and its unit* from both the criterion and the observation. **If the units do not match, refuse to compare** — this prevents a criterion in millimetres being checked against an observation in minutes. If they match and the criterion says "minimum / not less / maintain / supports", compare numerically.
4. Contains "pass", "verified", "confirmed", "complete", "meets" → `PASS`
5. Otherwise → `NEEDS_REVIEW`

**Test records and NCRs** — submitting observations creates a controlled test record; any `FAIL` automatically creates a **Non-Conformance Report**.

**Readiness score** — a visible weighted rule set totalling 100:

| Rule | Weight | Satisfied when |
| --- | --- | --- |
| `document_approval` | 15 | all required documents approved |
| `compliance` | 20 | no NON_COMPLIANT / NEEDS_REVIEW / MISSING_INFORMATION findings |
| `delivery` | 15 | all shipments complete, delivered or on track |
| `installation` | 20 | all installation tasks complete |
| `open_critical_issues` | 20 | no open NCRs and no critical non-conformances |
| `test_prerequisites` | 10 | first 3 procedure steps all PASS |

Status: **READY** at 100 · **NEEDS_REVIEW** at ≥70 · **NOT_READY** below 70.
Every rule shows its weight, its evidence and whether it was satisfied. **No LLM touches this score.**

**Measured:** 21/21 steps automatically evaluated, automation coverage **1.0**, expected/actual NCRs **1/1**.

## 4.7 Supply Chain & Procurement
`app/procurement.py`

Import a shipment CSV, or use the seeded synthetic scenario. For each shipment we compute **ETA variance**, look up the linked schedule task's **float**, and derive **schedule exposure** and a severity. Risk events can be injected to demonstrate alerting. Alternatives (expedite, alternate supplier, partial shipment) are generated with their impacts.

> ⚠️ **Say this out loud in the demo:** this is synthetic milestone data. There is **no live AIS, vessel tracking, carrier or geospatial integration.** The brief asked for geospatial supply chain AI; we built the schedule-impact half and are honest that the tracking half is roadmap.

**Measured:** 5/5 shipments represented, 15 supplier tiers, alternatives generated for all risky shipments. Alerting is measured over **8 events across all five shipments** — latency `20`–`420` minutes, median `75`, six of eight inside two hours, and the first alert lands `17`–`55` days before planned arrival.

The event set is built to be measurable rather than flattering: it includes a tier-3 copper allocation signal two weeks ahead of the tier-2 shortage the schedule eventually records, two events that resolved without any delay, and one deliberately slow seven-hour alert on a sub-tier signal nobody was watching. A timeliness figure computed only over fast alerts on things that went wrong is a selection, not a measurement.

## 4.8 Equipment Digital Thread
`app/equipment.py`

The spine. For one equipment tag, assemble: current specification, current submittal, all compliance findings, related RFIs, shipment, schedule tasks, commissioning steps and status, open NCRs, mitigation records, and every evidence link — all scoped to one project.

This is what turns a pile of documents into *"everything about SWGR-A, and how it all connects."*

## 4.9 The Impact Chain — our main innovation
`app/impact_chain.py`

A verified event propagates through five stages, and each hop keeps the evidence it came from:

```
specification deviation
    → vendor resubmission
        → delivery risk
            → schedule impact
                → commissioning impact
                    → human decision
```

**The seeded SWGR-A scenario, end to end:**

| Stage | What happens | Value |
| --- | --- | --- |
| 1 · Specification | ArcLine offers 50 kAIC against a required minimum of 65 kAIC at 480 V | `NON_COMPLIANT`, high severity, cited to `Switchgear_Specification.md` p.2 §2.2.3 and `SWGR-002_ArcLine_SWGR-A.md` p.1 |
| 2 · Procurement | Vendor resubmission required; shipment `SYN-SHP-001` slips | +35 days ETA variance |
| 3 · Schedule | 35-day delay against 7 days float on `T-140` | **28 days** critical-path exposure |
| 4 · Commissioning | SWGR-A readiness recalculated | **65 → 45** |
| 5 · Decision | Three deterministic mitigations offered | `AWAITING_HUMAN_DECISION` |

**The three mitigation scenarios**, generated from the schedule delay and the replacement lead time:

| Action | Days recovered | Remaining delay | Cost premium | Confidence |
| --- | --- | --- | --- | --- |
| Expedite compliant equipment replacement | 18 | 17 | +20% | 98% |
| Install approved temporary compliant package | 35 | 0 | +35% | 92% |
| Resequence off-site testing and downstream commissioning | 10 | 25 | +10% | 88% |

Selecting one recalculates a **counterfactual** chain — projected delay, exposure, commissioning date and readiness — **without mutating any real operational date**. Nothing becomes real until a human approves, and that approval is persisted with the evidence it was made on.

The whole scenario is **idempotent**: running it twice reuses the same findings, events and simulation rather than duplicating them. There is an integration test that verifies the full five-stage propagation, evidence separation, persistence and project isolation.

## 4.10 The frontend
`frontend/src/components/` — `story.tsx` (public narrative) · `dashboard.tsx` (workspace) · `viz.tsx` (charts) · `ui.tsx` (primitives) · `motion.tsx` + `lib/motion.ts` (animation)

Next.js + React + TypeScript + Tailwind. IBM Plex Sans and IBM Plex Mono — typefaces drafted for technical documentation, with a faint drafting-paper grid.

**Two surfaces.** A visitor who is not signed in gets the **story**: a scroll narrative of the six-link chain, the guardrails, and a way in. Signing in opens the **workspace**. That split is deliberate — someone opening the link for the first time should learn what the chain is before being asked for credentials they may not have.

Workspace destinations: Project overview · Knowledge / RFI · Equipment thread · Compliance findings · Impact Chain · Mitigation simulator · Commissioning · Supply chain · Evidence Dashboard · Evaluation · Documents.

**Four UI decisions worth pointing at:**
- AI output is always badged **"Suggestion · not approved"** or **"AI assessment — reviewer pending"**, visually separated from human-approved records.
- Synthetic data carries a **synthetic badge** everywhere it appears.
- **Colour is split by job.** One sequential hue encodes magnitude; the fixed status palette encodes state; brand navy and teal never encode data. The magnitude ramp was validated rather than chosen — monotone lightness, adjacent ΔL ≥ 0.06, single hue, light end 2.11:1 on white. It measures 1.95:1 on the page ground and fails the 2:1 floor there, which is why every chart sits on a white card.
- **A status never travels as colour alone.** Two of the four status steps are below 3:1 on a light surface by design, so every badge and meter carries a text label; the word carries the meaning and the colour only makes it fast.

**No animation library.** Scroll reveals, counters and progress use `IntersectionObserver` and `requestAnimationFrame`. Reduced motion is honoured by deriving the final state during render, so a reader who asks for no motion never sees the pre-animation state flash.

The landing narrative describes the chain **as a mechanism**. It used to narrate the seeded switchgear figures — 50 kAIC, 35 days, 28 days — which stated one example's numbers as though they were the product. The worked example lives in the workspace, where each figure is attached to the document it came from.

## 4.11 How we prove it works
`evaluation/run_all.py` · `scripts/evaluate_synthetic.py`

A labelled synthetic corpus with **planted** defects and a `ground_truth.json` — 3 specifications, 6 submittals (3 clean, 3 carrying six planted deviations), 12 RFIs (with two planted near-duplicate pairs), a schedule CSV with a planted 35-day delay propagating to five downstream tasks, a 46-record site conditions log supplying evidenced weather and workforce, 3 commissioning templates, 5 shipments carrying 8 alert events.

A **second corpus** (`data/synthetic_epc_extended/`, 41 files, generated by `scripts/generate_extended_corpus.py`) covers six further equipment items — generator, chiller, PDU, transformer, clean-agent fire suppression, BMS — with 12 planted deviations, 6 clean controls, one near-duplicate RFI pair and a 28-day schedule delay. One deviation is stated in different units from its specification (chiller capacity offered in BTU/hr against a kW requirement), so unit normalisation is exercised rather than assumed. It carries its own ground truth and is loaded into its own project, because `/compliance/evaluation` scores every finding in a project against the first corpus's ground truth.

Because we know the right answers in advance, we can compute real precision and recall instead of eyeballing outputs.

| Area | Result |
| --- | --- |
| Ingestion | 27/27 documents |
| Compliance | P/R/F1 = 1.0 / 1.0 / 1.0 (TP 6, FP 0, FN 0, TN 6) |
| RAG | Recall@5 1.0, Recall@12 1.0, MRR 1.0 |
| Citations | 17/17 correct |
| Schedule | 35-day prediction, 0-day error |
| Supply chain | 5/5 shipments, 55-minute mean alert latency |
| Commissioning | 21/21 steps, coverage 1.0, NCR 1/1 |
| **Advanced RAG citation precision** | **0.2432 vs baseline 0.3226 on 16 held-out questions — we lose, and we report it.** The old `0.667 vs 1.0` came from a three-case test split and a tuner that broke ties on wall-clock latency; both are fixed |
| Manual hours saved | `NOT_MEASURED` |
| Backend tests | **196 passing** |
| Frontend tests | **22 passing** |

## 4.12 Deployment, access and delivery

**Live:** <https://atlas-theproject.duckdns.org>

| | |
| --- | --- |
| Read-only account (share this) | `viewer@atlas.demo` / `ET-viewer-2026` |
| Administrator | `mahendraaravind13@gmail.com` / `ET-admin-2026` |

**What it runs on.** One `t3.micro` in `ap-south-1` (Mumbai), inside the AWS free tier. Docker Compose runs five containers on it: the FastAPI API, the Next.js dashboard, PostgreSQL, Qdrant, and Caddy terminating TLS with an automatically renewed Let's Encrypt certificate. Uploaded originals and the graph export sit on named volumes, so they survive a redeploy.

Measured, with both models loaded and a query served: api ~570 MB, qdrant ~60 MB, postgres ~40 MB, web ~80 MB, caddy ~20 MB — about **770 MB**, inside 1 GB with roughly two hundred megabytes of headroom. A 4 GB swapfile absorbs an OCR-heavy upload rather than letting the kernel kill the API.

**How a change ships.** `git push origin main` → CI (pytest, lint, typecheck, build) → both images built and pushed to ghcr.io → the instance pulls and restarts → the job polls `/ready` and fails with the API logs attached if the new version does not come up. Roughly eight minutes, hands-off. Images are built in CI rather than on the instance because the API image compiles wheels and bakes ~100 MB of model weights, which a 1 vCPU box cannot do reliably.

**Authentication is on.** `ATLAS_AUTH_ENABLED=true`. Passwords are hashed with scrypt and session tokens are HMAC-SHA256 signed, both from the standard library — no new dependency, deliberately, on a lockfile that has twice proved fragile. A user is global; `project_members` grants them **viewer**, **reviewer** or **admin** per project. Reading needs viewer, mutating needs reviewer, managing members needs admin. A non-member gets **404, not 403**, because a 403 would confirm the project exists.

**Say this if asked why the demo is reachable at all:** it is authenticated, the data is synthetic and labelled, and the read-only account cannot upload, approve, or reset anything.

---
---

# PART 5 — How everyone else implements this

Understand the field before claiming to beat it.

## 5.1 The systems of record

**Procore** — the market-leading construction management platform. Documents, RFIs, submittals, drawings, financials, in one system. Has added AI: a copilot for document retrieval and summarisation, agents for automating RFI and submittal workflows, and Insights. **Publishes a dedicated data-centre vertical page.**
*How it works:* a broad horizontal platform with an AI layer on top. Excellent as the place everything lives.
*Where it stops:* it will not take a spec deviation and compute the CPM consequence for your energisation date. The depth — unit-normalised engineering comparison, Tier commissioning logic — is not there, because building that for one vertical does not pay for a horizontal vendor.
*Price:* no public rate card. Reported at **0.1–0.2% of hard construction cost**; $15–30k/yr for small GCs, $30–80k/yr mid-size, plus **$50–150k implementation** and 10–15% renewal increases.

**Autodesk** — Construction Cloud, rebranded to **Autodesk Forma** in March 2026. Design-to-construction lifecycle, deep BIM integration. Same shape as Procore: horizontal, with AI added.

**Oracle Aconex + Primavera P6** — Aconex is the document-control and correspondence system of record on large infrastructure; P6 is the scheduling standard. Both are entrenched and both are excellent.
*Where it stops:* **they are two different products.** The documents live in one, the schedule in the other, and nothing automatically connects a submittal deviation to a critical path. That gap is where we live.

## 5.2 The AI submittal-review category (2026) — our nearest competitors

This category did not meaningfully exist two years ago. In 2026 the named players are **BuildSync, Part3 Submittal Assistant, Remy, SpecLens, iFieldSmart, InspectMind, Helonic, Pelles.ai**.

*How they work:* extract technical characteristics from a submittal, verify each against the project specification, return a compliance report with paragraph-level citations back to the source. Flag missing information, non-compliant values and unanswered requirements. Reported to cut review time by around 80%.

*Context they cite:* the industry has normalised a **35% submittal rejection rate**, and complex projects exceed **3,000 documents** requiring review before anything ships.

👉 **This is the closest thing to our Compliance module, and we must name them.** They do that job well.
👉 **And it is exactly one box in our chain.** They answer *"is this compliant?"* and stop. The deviation does not propagate into procurement, the critical path, or a readiness score.

## 5.3 The schedule specialists

**nPlan** — machine learning over millions of historical schedules to forecast which activities will slip.
*Where it stops:* it needs a large schedule history, it does not read your specifications, and it cannot tell you *why* — only that a pattern suggests risk.

**ALICE Technologies** — generative scheduling: explore thousands of ways to sequence a build and optimise. **$61.1M raised.** Customers report 17% shorter durations.
*Where it stops:* optimises the plan; does not connect to document compliance or commissioning.

## 5.4 The commissioning specialists

**CxAlloy, Facility Grid, CxPlanner, Bluerithm** — commissioning management: issue tracking, test checklists, equipment lists, functional test forms, handover packages. CxPlanner is explicitly data-centre focused. Pricing **$65–430/month**.
*Where it stops:* commissioning starts *after* the equipment has arrived. If the wrong switchgear was ordered nine months earlier, these tools first learn about it when it fails a test. They own the last box in our chain and have no visibility upstream.

## 5.5 The reality-capture layer

**OpenSpace, Doxel, Buildots, Disperse** — 360° cameras and computer vision walking the site, comparing what is built against the model, tracking progress automatically. OpenSpace has a data-centre offering.
*Where it stops:* they see the physical site. They do not read a specification clause.

## 5.6 Contracts and documents

**Document Crunch** — AI trained on construction contracts; flags unfavourable clauses and liability risk. **Acquired by Trimble in 2025.** A different document type to ours — contracts, not technical specs.

## 5.7 India

**Powerplay** — construction communication and collaboration SaaS for Indian professionals. **$15.6M raised** over 6 rounds (Accel, Sequoia Surge). Focused on SME site management: daily progress, material tracking, payments.
Indian construction-tech funding overall: **$35.1M in 2026 to date**; 157 construction-tech startups in Bengaluru alone.

👉 **We found no Indian entrant covering the specification → procurement → schedule → commissioning chain for data centres.** That is our opening, and it is worth saying plainly.

## 5.8 The competitive map, summarised

| Player | What they own | Where it stops |
| --- | --- | --- |
| Procore · Autodesk Forma | System of record + AI copilot | Horizontal; no engineering-depth propagation |
| Aconex + P6 | Document control; CPM | Two separate products, unconnected |
| BuildSync · Part3 · Remy · SpecLens | AI submittal compliance | Stops at the submittal |
| nPlan | Schedule risk from history | Needs history; ignores documents |
| ALICE | Schedule optimisation | Plan only |
| CxAlloy · Facility Grid · CxPlanner | Commissioning execution | Starts after equipment arrives |
| OpenSpace · Doxel · Buildots | Site reality capture | Does not read specs |
| Document Crunch (Trimble) | Contract clause risk | Contracts, not technical specs |
| Powerplay | India SME site management | Different segment entirely |
| **Project Atlas** | **The chain that connects all of it** | **Prototype; synthetic data; no auth** |

---
---

# PART 6 — Why we are better

Four claims. Each is defensible, and each has a limit we state.

### 1. We do not stop at the submittal
The 2026 submittal-AI cohort answers *"is this compliant?"*. Atlas answers *"…and what does that do to my energisation date?"*

A 50 kAIC deviation is not a document problem. It is a **28-day critical-path problem** and a **readiness score of 45**. Nobody else carries the deviation that far, because doing it requires the compliance engine, the CPM engine, the commissioning model and the evidence graph to be one system.

*Limit:* they are more mature at the submittal step itself and have real customers. We have neither yet.

### 2. Cited, or silent
If the project's own documents do not support an answer, we return `INSUFFICIENT_EVIDENCE`. This is enforced in **code** — retrieval, fusion and the sufficiency check run with no LLM involved — so it cannot be prompted away.

In EPC, a confident wrong answer is worse than no answer. This is the only behaviour a QA manager can sign a Tier III handover against.

*Limit:* our gate is currently *too* strict — a single open RFI in the retrieved set blocks an otherwise well-supported answer. Documented, with a fix designed.

### 3. The maths is not a prompt
CPM float, unit normalisation and readiness weights are Python. The LLM rewrites queries, extracts values and explains. It cannot produce a delay figure, a pass/fail, or a score.

This matters because an LLM that computes 28 days is guessing; code that computes 28 days can be audited, tested and defended in a claim.

*Limit:* our rule coverage is six parameters on planted schemas — nowhere near a certified standards checker.

### 4. Built for Indian delivery economics
India builds data centres at **$5.4–8M per MW**, among the lowest costs in the world. A US-priced product does not land here. Our pricing, our worked examples and our target buyers are Indian from the ground up — not a US general-contracting product retrofitted.

*Limit:* we have not sold to anyone, so this is a design intention, not proven product-market fit.

### And the meta-argument

We report that our advanced RAG path loses to the baseline on citation precision — **0.2432 against 0.3226**, on sixteen held-out questions. We could have hidden that. A system asking an engineer to trust its findings has no business hiding its own regressions — and a team that discloses one is a team you can believe about everything else.

What we did instead of hiding it was go and check the measurement. The earlier headline, `0.667 against 1.0`, was not wrong so much as meaningless: it came from a **three-case** test split, where one extra citation on one question moves the figure by a third. Expanding the labelled set to 16 test questions turned up two harness defects — a parameter search that broke ties on **measured wall-clock latency**, so the same script selected different parameters on consecutive runs, and a precision metric that counted duplicate citations separately, rewarding a pipeline for citing the same page three times. Both are fixed, three consecutive runs now agree exactly, and a test asserts the reproducibility. The regression survived all of that, which is the point: it is now a result rather than a coin toss, and the per-case data says where it comes from — advanced retrieval ranks the right evidence higher (MRR 0.7521 vs 0.6269) on 2.6× fewer input tokens, then cites its top three, which sometimes misses a correct page sitting at rank six.

---
---

# PART 7 — The global picture

## 7.1 The construction boom

| Metric | Value | Source |
| --- | --- | --- |
| Global data-centre construction market, 2025 | **~$261 B** | Grand View / TBRC |
| Global data-centre construction market, 2030 | **~$383 B** | Grand View / TBRC |
| Total data-centre capex by 2030 | **$1.6 T** | Omdia |
| Hyperscaler capex, 2026 | **~$697 B** | J.P. Morgan |
| US data-centre construction starts, 2025 | **$77.7 B**, +190% year on year | ConstructConnect |

## 7.2 The delivery problem, globally

> **Evidence grading.** ✅ = primary source verified directly · ⚠️ = widely cited, secondary sources only · ❌ = could not verify, do not lead with it. Every row is graded, because a number you cannot defend is worse than no number.

### A. How often do these projects actually run late?

| Finding | Value | Source | Grade |
| --- | --- | --- | --- |
| Large infrastructure projects that overrun schedule | **9 out of 10** | Oxford megaprojects research, via Dr Atif Ansar, 2026 | ✅ |
| 2025 data-centre capacity that **missed** its projected completion date | **over 25%** | Currence, 2026 | ✅ |
| Projects that quietly postponed their commercial operation date | **10%** | Currence | ✅ |
| 2026 large-scale capacity expected to be **delayed** | **30–50%** | Currence | ✅ |
| 2026 pipeline: scheduled vs actually building | **16 GW scheduled · ~5 GW building · ~11 GW announced only** | Currence | ✅ |
| Typical build timeline (so that 11 GW cannot make 2026) | **12–18 months** (18–24 for AI-density builds) | Currence · Ansar | ✅ |
| APAC data-centre EPC projects overrunning schedule by >10% | 67% | ET Hackathon brief, attributed to Turner & Townsend 2024 | ❌ **not in source — do not use** |

👉 **This is the strongest framing available, and it replaces the unverifiable 67%.** Nine in ten large infrastructure projects overrun. In data centres specifically, a quarter of 2025 capacity missed its date, and up to half of 2026's is expected to be late.

### B. Why are they late?

| Finding | Value | Source | Grade |
| --- | --- | --- | --- |
| Report delays to manufacture or delivery of **critical equipment** | **~80%** | Turner & Townsend, DCCI 2024 | ✅ *fetched directly* |
| Rank power availability above location when siting | **92%** | Turner & Townsend, DCCI 2024 | ✅ *fetched directly* |
| Equipment lead times (generators, chillers, transformers, switchgear) | **more than doubled since 2019**, in some cases **over 3 years** | McKinsey · CBRE · JLL | ✅ |
| Average grid connection wait | **over 4 years**, up to a decade in some markets | McKinsey · CBRE · JLL | ✅ |
| Cost of bad data to global construction, 2020 | **$1.85 T** | FMI + Autodesk, 3,900+ respondents | ✅ |
| — of which avoidable rework | **$88.69 B = 14% of all rework** | FMI + Autodesk | ✅ |
| Respondents saying more than half their project data is bad | **30%** | FMI + Autodesk | ✅ |
| Human-error outages caused by not following procedure | **58%**, up from 48% | Uptime Institute, 2025 | ✅ |
| Cost to respond to one RFI | **$1,080** (median response 9.7 days; 796 RFIs per project average) | Navigant, 2013 — 1,362 projects, >1M RFIs | ⚠️ *13 years old; secondary citations only* |
| RFIs per $1M of construction value | **9.9** | Autodesk, 1,300+ projects | ⚠️ *secondary only* |
| → typical project RFI cost | **~$860,000** | derived from the two above | ⚠️ |
| First-submission submittal rejection rate | **35%** (range quoted 30–40%) | 2026 submittal-review vendor reporting | ⚠️ **vendor-sourced — see note** |

> ⚠️ **The 35% submittal figure is the weakest number we use.** Every source we could find is an AI-submittal *vendor* blog — BuildSync, SpecLens, Customiser — citing one another. No primary study exists that we could locate. It is plausible and consistent across sources, but if a judge presses, say: *"That is vendor-reported industry data, not an independent study."* Do not build an argument on it.

👉 **Note how well section B lines up with our product.** The single most-verified cause of data-centre delay is *critical equipment delivery* — which is exactly stage 2 of our Impact Chain. Point that out; it is not a coincidence to be shy about.

## 7.3 What a delay costs

**Per month, for a 60 MW facility — $14.2 million:**

| Component | Value |
| --- | --- |
| Lost revenue | $10.8 M |
| Labour and overhead | $2.2 M |
| SLA penalties | $1.2 M |
| **Total per month of delay** | **$14.2 M** |

*Source: Dr Atif Ansar (Oxford megaprojects researcher), citing STL Partners and Foresight research, 2026.* ✅

**On project returns**, same source: IRR falls from **17.1% on time → 12.6% at three months → 8.8% at six months.** A six-month slip roughly halves the return. ✅

**For a 50 MW campus, a three-month slip is put at $30–150M** — stranded capital $15–40M, lost revenue $10–60M, contractual penalties $5–30M *(Exto, 2025 — vendor analysis)* ⚠️.

> **Do the two agree?** Yes, and that matters. $14.2M/month × 3 months = **$42.6M**, which sits comfortably inside the $30–150M range. Two independently produced estimates landing in the same place is far stronger than either alone. **Lead with $14.2M/month** — better provenance, easier to defend.

Commissioning specifically involves **15–25 contractors** across mechanical, electrical, controls and life safety, typically with no unified platform *(Exto)* ⚠️.

## 7.4 The software market

| Metric | Value |
| --- | --- |
| Global construction-management software, 2025 | **$10.6–10.8 B** |
| Same, 2031 | **~$17.8 B** (≈9% CAGR) |
| Construction SaaS specifically, 2025 → 2036 | $16.3 B → $50.4 B |
| Cloud share of the market, 2025 | 63.8% |

---
---

# PART 8 — The India picture

## 8.1 Capacity and the pipeline

| Metric | Value | Source |
| --- | --- | --- |
| Operational capacity, 2020 | ~375 MW | industry |
| IT-load inventory, H1 2025 | **1,123 MW** | JLL |
| Operational, April 2025 | ~1,263 MW | Arizton |
| Projected end-2027 | **2,073 MW (+85%)** | JLL |
| Projected 2030 | **4,500+ MW** | Arizton |
| **Total development pipeline** | **8.33 GW (8,326.6 MW)** | Knight Frank India, 2026 |
| — under construction | **322.4 MW** | Knight Frank |
| — committed stage | **2,920.2 MW** | Knight Frank |
| Large projects announced Mar 2025 – Apr 2026 | **~30, adding ~3.5 GW** | industry |

## 8.2 Money and market

| Metric | Value |
| --- | --- |
| India data-centre market, 2025 | **$9.79 B** |
| Same, 2031 | **$21.03 B** (13.59% CAGR) |
| Investment 2020 – Apr 2025 | ~$14.7 B |
| Fresh investment expected to 2030 | **$20–25 B** |
| JLL's estimate for the 2027 expansion | ~10.7M sq ft, ~$6.3 B capex |

## 8.3 Build cost — the number that shapes our pricing

| Metric | Value |
| --- | --- |
| Capex per MW, India | **₹465 M ≈ $5.4–5.5 M** — among the lowest in the world (China: $6.8M) |
| Tier III colocation turnkey | **$6–8 M/MW** |
| Tier IV mission-critical | **₹70–90 crore/MW** |
| AI-ready high-density (20–50+ kW/rack, liquid cooled) | ₹70–95 crore/MW |

👉 **This is why our worked example is in rupees.** A 50 MW Tier III campus in Chennai is roughly **₹2,900 crore / $350M** — not the $500M a US example would suggest.

## 8.4 Who is building

| Operator | Share |
| --- | --- |
| NTT GDC | 20% |
| ST Telemedia (STT GDC) | 19% |
| Sify Technologies | 19% |
| CtrlS | 15% |
| Yotta | 5% |
| AdaniConneX, Nxtra | growing entrants |

Together they hold over 1 GW installed and have announced more than 4.5 GW. STT GDC alone committed **$3.2 B for 550 MW** over five to six years (Sept 2024). CtrlS opened its Kolkata campus in Aug 2025 and a 72 MW Chennai park in Ambattur.

**Geography:** Mumbai holds **41%** of live capacity, Chennai **23%** — nearly two-thirds between them. Other hubs: Hyderabad, Bengaluru, Noida, Vizag.

**The EPC contractors — our actual buyers:** L&T Construction, Tata Projects, **Sterling & Wilson Data Center** (28 data-centre projects across India, Africa and the Middle East since 2015).

## 8.5 Policy tailwind

**Draft National Data Centre Policy 2025** proposes: up to **20 years** of conditional tax exemption, **100%** electricity-duty exemption, input tax credits on HVAC and electrical equipment, single-window clearances, and dedicated **Data Centre Economic Zones**.

State policies already running:
- **Maharashtra** — subsidised power tariffs, discounted stamp duty, single-window clearance; first state to add incentives for green integrated data centre parks
- **Tamil Nadu** — 2021 Data Centre Policy: building-norm exemptions, renewable access, infrastructure subsidies
- **Uttar Pradesh** — concessional land, capital subsidies, stamp-duty exemption

## 8.6 The delivery problem, in India

### Indian infrastructure generally — government data, the strongest evidence we have

| Finding | Value | Source | Grade |
| --- | --- | --- | --- |
| Monitored infrastructure projects delayed | **764 of 1,902** (~40%) | MoSPI, Feb 2024 | ✅ *government data* |
| Cumulative cost overrun | **₹5.42 lakh crore** across 1,392 projects | MoSPI, Dec 2025 | ✅ |
| Delay distribution | 194 projects 1–12 months · 187 for 13–24 · 284 for 25–60 · **115 for over 60 months** | MoSPI | ✅ |

👉 **MoSPI is the single most defensible number in the whole pitch** — official Government of India statistics, published monthly, not a vendor blog or a consultancy estimate. If you keep only one Indian figure, keep this one.

### Indian data centres specifically

| Finding | Value | Source | Grade |
| --- | --- | --- | --- |
| Commissioning delay when power tie-up is deferred to late-stage execution | **6–18 months** | India data-centre execution reporting, 2026 | ✅ |
| Named example: Sify AI-Hub, Lucknow, Phase 1 | Targeted operational **June 2025** — still under construction | industry reporting | ✅ |
| India data-centre pipeline facing delays and cancellations | **through 2027** | Construction World, 2026 | ✅ |
| Capacity reality check | ~1.3 GW operational by end-2025 against an 8.33 GW announced pipeline | Knight Frank · industry | ✅ |

👉 **India's delay driver is different from the global one.** Globally the binding constraint is equipment lead times and grid-connection queues. In India it is **power tie-up timing** — sponsors who leave the utility connection to late-stage execution routinely lose 6–18 months at commissioning.

Say this on stage: it shows we understand the local market rather than importing a Western analysis. It is also an honest limit on our product — Atlas tracks equipment and schedule, **not** utility interconnection. We are a partial answer to India's biggest single delay cause, and we should say so rather than overclaim.

## 8.7 How we size the opportunity

Shown as arithmetic, because the method is what earns the number:

| Layer | Calculation | Value |
| --- | --- | --- |
| **TAM** | Global construction-management software, 2025 | **$10.8 B** |
| **SAM** | $261 B global DC construction × 0.15% software intensity | **~$390 M/yr** |
| **SOM** | 8.33 GW pipeline × $7 M/MW = $58 B construction spend × 0.05% Atlas rate | **~$29 M** |
| — near-term | 3.24 GW committed/under construction ≈ $22.7 B × 0.05% | **~$11 M** |

> The **0.15% software intensity** is our own multiplier, derived from Procore's reported 0.1–0.2% of hard cost. It is an assumption, not a published figure. Say so.

## 8.8 Business model

| Tier | Price | Buyer |
| --- | --- | --- |
| **Project licence** | ₹50 L – 1.25 crore ($60–150k) per active project-year · 0.03–0.06% of hard cost | EPC delivery team, one campus |
| **Enterprise portfolio** | ₹3.3 crore+ ($400k+)/yr · multi-project, RBAC, audit pack | Owner or contractor head office |
| **Commissioning module** | per MW | Sold alongside the Cx agent |

**The worked example:**
A 50 MW Tier III campus in Chennai ≈ **₹2,900 crore**. Atlas across the whole build = **₹1.5–2 crore**.
Three months of stranded capital alone on that build = ₹2,900 cr × 10% × ¼ year = **₹72 crore**.
→ **The licence costs 2–3% of the financing charge alone**, before lost revenue or liquidated damages.

**Status: prototype. No revenue, no pilots, no letters of intent.** Say this before anyone asks.

---
---

# PART 9 — Scalability: is it scaled?

**Short answer: no. It is built in a shape that can scale, but it is not scaled, and one component would fail hard on the first real project.**

Scalability is **15% of the judging score**, and "it scales fine" is the answer most likely to get you taken apart in Q&A. This is the honest version, with file references and numbers.

## 9.1 What is already right

Good decisions that mean scaling is a matter of work, not a rewrite:

| Decision | Evidence | Why it matters |
| --- | --- | --- |
| Async all the way down | FastAPI + `create_async_engine` + `AsyncQdrantClient` | One process serves many concurrent requests |
| Models loaded once, not per call | `@lru_cache(maxsize=2)` on `_sentence_transformer` and `_cross_encoder` | Without it, every query reloads ~90 MB of weights from disk |
| CPU work off the event loop | `asyncio.to_thread` around parsing, OCR, embedding, reranking | A big PDF parse does not freeze every other request |
| Pathological files bounded | `asyncio.wait_for(..., timeout=300s)` in `run_ingestion` | A corrupt scan fails cleanly instead of hanging a connection |
| Stateless API | All state in PostgreSQL and Qdrant | You can run N replicas behind a load balancer today |
| Multi-tenant data model | `project_id` on every row and vector payload, with cross-project tests | Tenancy is designed in, not bolted on |
| Job table already exists | `IngestionJob` with status, attempt count, error | The queue refactor needs an execution change, not a schema change |
| Real migrations | Alembic, `auto_create_schema=False` by default | Production schema changes already handled |
| Provider failover | `ATLAS_LLM_PROVIDERS`, 3 attempts each, 30 s timeout | Generation has no single point of failure |
| Orchestrator probes | `/health` liveness, `/ready` dependency readiness | Kubernetes or Render can actually manage it |

## 9.2 What breaks first — ranked

### 🔴 1. BM25 runs in Python over the entire project, on every query

This is the one that fails, and it fails first.

`retrieve_chunks()` calls `_filtered_payloads()`, which pages through Qdrant in batches of 256 and pulls **every matching payload for the project into Python memory**. `_bm25_rank()` then tokenises all of them and computes BM25 in a pure-Python loop.

Cost is **O(all chunks in the project), per query**.

| Scale | Chunks | What happens |
| --- | --- | --- |
| Our demo | 27 documents, a few hundred chunks | ~1 scroll call — invisible |
| One real project | ~5,000 documents ≈ **200,000 chunks** | **~780 sequential scroll round-trips**, hundreds of MB transferred, BM25 over 200,000 documents in Python — tens of seconds per query |

Worse: `vector_payload()` stores the chunk text **twice** — `original_text` and `text` hold the identical value — plus `contextual_text`. Every scroll moves roughly 2.5× the text it needs.

**Fix:** Qdrant supports **native sparse vectors** (BM25/SPLADE). Move lexical search into the engine, where it is an index lookup rather than a full scan. Well-trodden, documented — not research. Also drop the duplicate `text` field.

> Highest-leverage change in the codebase. It is also a *known algorithmic* bottleneck, not a speculative one — you do not need to load-test an O(n)-per-query scan to know it will not hold.

### 🟠 2. Ingestion runs inside the HTTP request

`upload_document` does `await run_ingestion(...)` in the request handler. Parsing is threaded and timeout-bounded — good — but the client holds the connection for the whole parse → embed → index cycle, up to 300 seconds.

No retry, no backpressure, a browser or proxy timeout loses the job, and 50 concurrent uploads means 50 held connections and 50 threads fighting for the same cores.

Related: `index_chunks()` embeds **every chunk of a document in one call** — a 500-page spec could be thousands of chunks in a single batch. And `upsert(..., wait=True)` blocks until Qdrant confirms.

**Fix:** queue workers (arq / Celery / RQ with Redis, or a Supabase queue). Upload returns `202` with a job id; workers do the work; the UI polls the `IngestionJob` row that already exists. Batch embeddings.

### 🟠 3. Embedding and reranking run inside the API process

MiniLM and the cross-encoder load into the API's memory and compete for its CPU:

- Every API replica carries the weights, so horizontal scaling is expensive
- A heavy ingestion starves query latency — both go through the same thread pool on the same cores

**Fix:** move inference behind a dedicated embedding/rerank service or a managed API. Then the API tier scales on I/O and inference scales on GPU, independently.

### 🟡 4. One Qdrant collection for every tenant

Everything lives in `atlas_chunks`, separated by a `project_id` filter. Correct and tested today. At scale a filtered search still traverses a shared HNSW index, so a heavy tenant degrades a light one, with no per-tenant capacity control.

**Fix:** Qdrant's documented multitenancy pattern — a tenant-optimised payload index on `project_id`, moving to collection-per-large-tenant when a customer justifies it.

### 🟡 5. Local filesystem storage

`upload_path.write_bytes(content)` writes to a local directory, so a second replica cannot see the first's files. The whole file is also held in memory — 50 MB per concurrent upload.

**Fix:** S3 or Supabase Storage with signed URLs, and streaming uploads.

### 🟡 6. No cache, no quotas, no observability

- **No caching anywhere.** Two engineers asking the same question re-run retrieval, reranking and the LLM call. Redis keyed on `(project_id, query_hash, index_version)` is cheap and high-leverage.
- **No rate limiting or quotas.** One tenant can exhaust the shared LLM budget.
- **No metrics or tracing.** You cannot scale what you cannot measure — and the evaluation harness's latency numbers are in-process, not production SLOs.

## 9.3 The staged plan

**Stage 0 — today.** One project, a few hundred chunks, single container. Works.

**Stage 1 — first design partner (1 live project, ~200k chunks)**
1. Qdrant native sparse vectors, replacing Python BM25 *(highest leverage)*
2. Queue-backed ingestion — `202` plus a worker pool
3. Object storage for originals
4. Auth and RBAC *(also the security blocker — see Part 10)*
5. Redis response cache
→ Target: p95 knowledge query under 2 s at 200k chunks.

**Stage 2 — 5 to 10 projects**
6. Inference split into its own service
7. Tenant-optimised Qdrant payload index
8. PgBouncer and read replicas
9. Per-tenant rate limits and quotas
10. Metrics, tracing, structured logging

**Stage 3 — portfolio scale**
11. Collection-per-large-tenant sharding
12. Autoscaling on queue depth
13. Backups, disaster recovery, load tests, published SLOs

## 9.4 What to say on stage

The README's discipline is *"split services only after measured bottlenecks."* Right instinct, worth saying — premature microservices kill more projects than monoliths do.

But pair it with the specific: **BM25 in Python over the full project is a known algorithmic bottleneck**, first in the queue regardless of what a load test says.

If a judge asks "does it scale?":

> "Not yet — and I can tell you exactly what breaks first. Our lexical search pulls every chunk in the project into Python on every query. At demo scale that's milliseconds; at 200,000 chunks it's tens of seconds. The fix is Qdrant's native sparse vectors, and it's first on our list. What we did get right is the shape: the API is stateless, everything is async, tenancy is in the data model, and the ingestion job table is already there waiting for workers. So it's a work problem, not a rewrite."

That demonstrates you have read your own code. "It scales fine" demonstrates the opposite.

---
---

# PART 10 — What we have NOT built

Know this list better than the feature list. Every honest answer here is worth more than a claim.

> **Changed since this list was first written.** Authentication and per-project roles are now built and switched on, so the entry that used to head this list has moved down to *Built but limited*. Everything else here still stands.

## Not implemented at all
- **Tenant quotas, signed URLs, SSO.** Nothing meters or bills a tenant, and object access is not signed.
- **Live AIS, vessel position, carrier, vendor, geospatial or weather integration.** Supply-chain output is explicitly synthetic simulation.
- **ERP, Primavera P6 or QMS integrations.**
- **Computer vision on drawings.** The brief mentioned it; we did not build it.
- **Production object storage** — originals sit on a container volume. Durable per instance, but unreplicated and unbacked-up, and a second API instance could not share them.
- **Queued ingestion, autoscaling, observability, backups, disaster recovery, load tests, SLOs.** Ingestion is synchronous today.
- **Upload malware scanning, encryption-key management, retention enforcement, audit immutability.**

## Built but limited
- **Authentication and per-project roles are real, and their limits are specific.** Tokens are signed and short-lived but **cannot be revoked** — deactivating a user takes effect immediately because the account is re-read on every request, but an issued token otherwise stands until it expires. There is **no password reset flow** and **no rate limiting on `/auth/login`**; repeated attempts are logged, not throttled. `POST /auth/users` is gated on holding admin on *any* project, which is too coarse for a genuinely multi-tenant deployment.
- **The Knowledge Copilot answers most questions and refuses a specific class of them.** Measured on the deployment: *"Is the ArcLine switchgear submittal compliant with the interrupting rating requirement?"* returns three supported, cited claims; *"What battery autonomy is required for the UPS?"* answers on 3 of 3 attempts. *"What interrupting rating does the switchgear specification require?"* refuses on 3 of 3, at 131–141 context tokens against 428 for the question that works. The outcome is stable per phrasing, so it is structural rather than random, and it is **not yet root-caused**. Every rejected claim now logs its citations, the exact terms absent from the evidence and the term overlap, so the next person can diagnose it instead of guessing. **Demo the compliance-framed question** — it is the stronger demonstration anyway, because it shows the comparison rather than a lookup.
- **Compliance rules** cover six parameters on planted schemas. Not a certified code or standards checker.
- **Schedule results** are deterministic scenario analysis, not trained historical forecasting. Our error figure covers **one** planted case.
- **Commissioning pass/fail** uses visible project rules, not certification logic. No electronic signatures, no mobile or offline execution.
- **The evidence gate is too strict** — an open RFI in the retrieved set blocks the whole answer. Documented in `docs/LIMITATIONS.md` with a designed fix.
- **Advanced RAG does not beat baseline overall** — citation precision 0.2432 vs 0.3226 on 16 held-out questions. It wins on ranking (MRR 0.7521 vs 0.6269) and cost (2.6× fewer input tokens), and loses on final citation selection.
- **Prompt-injection handling** exists but has had no adversarial evaluation.

## Never measured
- **Manual effort and hours saved: `NOT_MEASURED`.** The brief explicitly asks for hours. We refuse to invent one. Measuring it is the first deliverable of a pilot.
- **Live LLM quality, latency and token cost.** Our evaluation uses deterministic test doubles.
- **Any real project data.** Every document, vendor, cost, date and shipment is synthetic and fictional.

## Never claim
- Compliance with TIA-942, BICSI, Uptime Institute, UL or AHRI. Our corpus uses realistic language; it reproduces no real standard.
- Historical prediction accuracy, live tracking, production scalability, hours saved, or business ROI.

---
---

# PART 11 — Numbers cheat sheet

**Know these six cold, without the slide:**
`8.33 GW` · `$30–150M` · `65 vs 50 kAIC` · `28 days exposure` · `₹1.5–2 crore` · `0.2432 vs 0.3226 on 16 cases`

### The problem — lead with these four
- **9 out of 10** large infrastructure projects overrun (Oxford megaprojects)
- **25%+** of 2025 data-centre capacity missed its completion date; **30–50%** of 2026's expected late (Currence)
- **~80%** report critical equipment delivery delays (T&T 2024)
- **764 of 1,902** Indian projects delayed; **₹5.42 lakh crore** overrun (MoSPI — government data)

### The problem — supporting
- Equipment lead times more than doubled since 2019, some over 3 years
- Grid connection waits now exceed 4 years
- $88.69B rework from bad data = 14% of all rework
- India: power tie-up deferral → **6–18 month** commissioning delays
- $1,080 per RFI × 9.9 per $1M ≈ $860k per project ⚠️ *secondary sources*
- 35% submittal rejection rate ⚠️ *vendor-sourced — do not build on it*

### The cost of delay
- **$14.2M per month** for a 60 MW facility ($10.8M revenue + $2.2M labour + $1.2M SLA) — Ansar/Oxford
- IRR **17.1% → 12.6%** at 3 months **→ 8.8%** at 6 months
- 50 MW, 3-month slip = **$30–150M** ⚠️ *vendor analysis — but it agrees with the $14.2M/month figure*

### The market
- India: 1,123 MW (H1 2025) → 2,073 MW (2027) → 4,500+ MW (2030)
- India pipeline **8.33 GW**; 322 MW under construction, 2,920 MW committed
- India build cost **$5.4–8M/MW**
- Global DC construction $261B (2025) → $383B (2030)
- TAM $10.8B · SAM ~$390M/yr · SOM ~$29M

### Our product
- 27/27 documents ingested
- Compliance P/R/F1 = **1.0** on 12 labelled cases
- Citations **17/17**
- Recall@5 / @12 / MRR = **1.0**
- Schedule: 35-day prediction, **0-day error**, one case
- Commissioning: **21/21** steps, coverage 1.0, NCR 1/1
- **220 backend tests, 22 frontend tests**
- Advanced citation precision **0.2432 vs baseline 0.3226**, on a 16-case held-out split that replaced a 3-case one
- Manual hours: **NOT_MEASURED**

### The demo
- **Live:** <https://atlas-theproject.duckdns.org> · judges sign in as `viewer@atlas.demo` / `ET-viewer-2026`
- **Ask the copilot:** *"Is the ArcLine switchgear submittal compliant with the interrupting rating requirement?"* — returns three cited, supported claims. Avoid *"what does the specification require"* phrasings; see Part 10.
- Required ≥65 kAIC @ 480 V · offered 50 kAIC · clause 2.2.3 · vendor ArcLine
- Shipment `SYN-SHP-001`, +35 days
- `T-140` → `T-160` → `T-170` → `T-180`
- 35 days delay − 7 days float = **28 days exposure**
- Readiness **65 → 45**
- Expedite: 18 recovered, 17 remaining, +20% cost, 98% confidence

---
---

# PART 12 — Sources

**India market** — JLL India Data Centre Market Dynamics H1 2025 · Knight Frank India 2026 (8.33 GW pipeline) · Arizton India Data Center Market · SBI Sector Report April 2026 · operator disclosures
**India build cost** — Blackridge Research · JM Financial Data Centre 101 · IMARC Engineering
**India policy** — Draft National Data Centre Policy 2025 · Maharashtra IT-ITES Policy 2023 · Tamil Nadu Data Centre Policy 2021 · UP Data Centre Policy 2021/2022
**India delays** — MoSPI project monitoring reports, Feb 2024 and Dec 2025
**Global market** — Grand View Research · The Business Research Company · Omdia · J.P. Morgan · Mordor Intelligence
**Delivery problem — verified ✅** — Turner & Townsend Data Centre Cost Index 2024 (80% equipment delays, 92% power-over-location; *fetched directly*) · Currence via Network World, 2026 (25%+ of 2025 capacity missed its date, 30–50% of 2026 at risk, 16 GW scheduled / ~5 GW building / ~11 GW announced-only, 10% quietly postponed COD) · Dr Atif Ansar, 2026, citing STL Partners and Foresight ($14.2M per month for 60 MW; IRR 17.1 → 12.6 → 8.8%; Oxford megaprojects "9 in 10 overrun") · McKinsey, CBRE, JLL (equipment lead times more than doubled since 2019, some over 3 years; grid connection waits over 4 years) · FMI + Autodesk, *Harnessing the Data Advantage in Construction* · Uptime Institute Annual Outage Analysis 2025 · MoSPI project monitoring reports
**Delivery problem — weaker, labelled in-text ⚠️** — Navigant Consulting 2013 RFI study and Autodesk RFI analysis (secondary citations only, 13 years old) · Exto 2025 ($30–150M range; vendor analysis) · BuildSync / SpecLens / Customiser (35% submittal rejection; vendor blogs citing one another, no primary study located)
**Not verified — do not use ❌** — the brief's "67% of APAC data-centre EPC projects overran schedule by >10%," attributed there to Turner & Townsend 2024; absent from the source
**Competitors** — Procore, Autodesk, Oracle, OpenSpace, CxAlloy, Facility Grid, CxPlanner, Bluerithm product documentation · Tracxn (ALICE $61.1M, Powerplay $15.6M) · 2026 submittal-review comparisons (BuildSync, Part3, Remy, SpecLens)
**Our own numbers** — `evaluation/latest.md`, `evaluation/latest.json`, `reports/rag_evaluation.md`, `docs/DATA_PROVENANCE.md`, `docs/LIMITATIONS.md`, and the test suites, all re-run 23 August 2026

**Related documents in this repo**
- [`README.md`](../README.md) — technical overview
- [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) — architecture and diagram
- [`docs/LIMITATIONS.md`](LIMITATIONS.md) — the full honest limitations list
- [`docs/DATA_PROVENANCE.md`](DATA_PROVENANCE.md) — where every piece of data came from
- [`docs/DEMO_SCRIPT.md`](DEMO_SCRIPT.md) — the timed product walkthrough
- [`docs/PITCH_SPEAKER_NOTES.md`](PITCH_SPEAKER_NOTES.md) — the verbatim 8-minute pitch script and Q&A bank
- [`docs/pitch-deck.html`](pitch-deck.html) — the interactive deck

> ⚠️ **`FINAL_STATUS.md` records a QA freeze dated 2026-07-21.** Substantial work shipped after it — authentication, the frontend rebuild, the expanded evaluation sets. Its header now says so and its measured snapshot is current, but its frontend and clean-seed rows were last verified at the freeze date and are marked accordingly.
>
> ⚠️ **`README.md` and `docs/LIMITATIONS.md` were updated** when the deployment went live; if you quote either, quote the current version.
