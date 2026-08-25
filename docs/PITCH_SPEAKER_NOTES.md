# Project Atlas — pitch speaker notes

**Format:** 8-minute business pitch · 13 presented sheets + 2 appendix
**Deck:** [`docs/pitch-deck.html`](pitch-deck.html) — press `T` to start the clock, `N` for in-deck cues
**Script length:** ~1,050 spoken words ≈ 130 words/minute
**Last verified:** 23 August 2026

---

## 1. Verification — is the research right, and does it fit the format?

### Format mapping

Every section of the required brief is honoured, in order, on time.

| Required section | Window | Sheets | Deck cue |
| --- | --- | --- | --- |
| — (cover) | 0:00–0:12 | 00 | T+0:00 |
| 1. Problem | 0:12–1:00 | 01, 02 | T+0:30, T+1:00 |
| 2. Solution | 1:00–1:45 | 03, 04 | T+1:25, T+1:45 |
| 3. Demo | 1:45–4:15 | 05, 06, 07 | T+2:05, T+3:20, T+4:15 |
| 4. Who needs it | 4:15–5:00 | 08 | T+5:00 |
| 5. How it makes money | 5:00–5:40 | 09 | T+5:40 |
| 6. Why it is better | 5:40–6:30 | 10 | T+6:30 |
| 7. Future plan | 6:30–7:15 | 11 | T+7:15 |
| 8. Closing | 7:15–8:00 | 12 | T+8:00 |
| Q&A backup | — | A1, A2 | not timed |

### Global and India coverage, per section

| Section | Global evidence | India evidence |
| --- | --- | --- |
| Problem | Turner & Townsend DCCI 2024 (80% equipment-delivery delays); FMI+Autodesk ($88.7 B rework, 14% of all rework); Navigant ($1,080/RFI); Exto ($30–150 M per 3-month slip); Uptime 2025 (58%) | JLL (1,123 → 2,073 MW); Knight Frank 2026 (8.33 GW pipeline); MoSPI (764/1,902 delayed, ₹5.42 lakh crore) |
| Market | Global DC construction $261 B → $383 B; construction-mgmt software $10.8 B → $17.8 B | 8.33 GW pipeline; ~30 large projects Mar 2025–Apr 2026; operator shares; Draft National DC Policy 2025 |
| Money | Procore benchmark 0.1–0.2% of hard cost; CxPlanner $65–430/mo | India capex $5.4–8 M/MW; worked example in ₹ crore |
| Competition | BuildSync, Part3, Remy, SpecLens, Procore, Autodesk Forma, OpenSpace, nPlan, ALICE, CxAlloy, Facility Grid, Trimble | Powerplay ($15.6 M); Indian construction-tech $35.1 M in 2026; no Indian entrant covering the full chain |
| Future | Middle East expansion | India-first design partner |

### Product claims — re-verified against the running code, 23 Aug 2026

| Claim | Status |
| --- | --- |
| Backend test suite | **135 passed** in 80.9 s — `python -m pytest -q`. (`FINAL_STATUS.md` says 88; that document is stale.) |
| Frontend test suite | **9 passed**, 2 files — Vitest |
| Compliance 6/0/0/6, P/R/F1 1.0 | Current in `evaluation/latest.md` |
| RAG Recall@5 / @12 / MRR = 1.0 | Current |
| Advanced citation precision 0.2432 vs baseline 0.3226, on 16 held-out questions | Current — the regression we disclose. If asked about the older `0.667 vs 1.0`: that ran on three test questions, and the tuner broke ties on wall-clock latency, so it moved between runs. Both fixed; the regression survived the fix |
| Schedule 35 d predicted, 0 d error | Current |
| Commissioning 21/21, coverage 1.0, NCR 1/1 | Current |
| Manual hours | `NOT_MEASURED` — do not claim a figure |
| SWGR-A demo values (65 kAIC required, 50 offered, clause 2.2.3, ArcLine, SYN-SHP-001, T-140→T-180, readiness 65→45) | Verified against `data/synthetic_epc/` |

### Known soft spots — say "I'll check" rather than bluff

- **0.15% software intensity** in the SAM is our own multiplier derived from Procore's reported 0.1–0.2%. It is an assumption, not a published figure.
- **Competitor plot positions** are our reading of published product scope as of Aug 2026, not a benchmark.
- **The brief's 67% APAC overrun stat** could not be located in the Turner & Townsend source. We use their verified 80% equipment-delay figure instead. If a judge quotes the 67%, say it comes from the problem statement and we could not verify it upstream.
- **Zero primary research.** We have not interviewed a working EPC delivery manager. That is the first gap the design partner closes.

---

## 2. The script

Read the **bold quoted text** as written. Bracketed lines are stage directions, not speech.

---

### Sheet 00 · Cover — 0:00–0:12

> **"Project Atlas. Evidence-led delivery intelligence for data-centre EPC.**
>
> **In a data-centre build, the specification and the site stop agreeing — and nobody finds out until commissioning. That is what we fix."**

*[Press `T` before the first word. Do not read the sheet aloud — they can see it.]*

---

### Sheet 01 · The build-out — 0:12–0:36

> **"India is building the compute faster than it can control the build.**
>
> **Eleven hundred megawatts today. Two thousand by 2027. An eight-point-three gigawatt pipeline behind that — a third of it already committed or under construction.**
>
> **But one hyperscale project is forty thousand equipment line items and two hundred trade contractors working at once. And eighty per cent of data-centre clients already report delays to the delivery of critical equipment."**

*[The 80% is your bridge into the problem. Land it and move.]*

---

### Sheet 02 · The fracture — 0:36–1:00

> **"So how does a deviation actually get caught today? A PDF on a shared drive. A submittal in email. An RFI spreadsheet. P6 in its own silo. And a senior engineer who remembers.**
>
> **The industry has normalised a thirty-five per cent submittal rejection rate.**
>
> **And a three-month commissioning slip on a fifty megawatt campus costs thirty to a hundred and fifty million dollars."**

*[**Pause two full seconds** after that number. It buys you the rest of the pitch. Do not fill the silence.]*

---

### Sheet 03 · What Atlas is — 1:00–1:25

> **"Atlas is the evidence layer between the documents and the decision.**
>
> **Three things. The Digital Thread — one project-scoped line from specification to commissioning, for every equipment tag. The Impact Chain — a verified deviation propagates deterministically into procurement, schedule and readiness. And the evidence gate — if the project's documents don't support an answer, Atlas refuses rather than guessing.**
>
> **Ask once. Get the chain. With the page number."**

---

### Sheet 04 · How it works — 1:25–1:45

> **"One rule makes this usable on a real project: the model explains, it never decides.**
>
> **The language model rewrites queries, extracts values, and writes the cited answer. Pass-fail, delay days, float and readiness are deterministic Python. And it approves nothing — a human does."**

*[Point at the two-column card. This is the slide that wins over anyone who has worked in EPC.]*

---

### Sheet 05 · Demo, the situation — 1:45–2:05

> **"Here's a delivery manager on a forty-eight megawatt campus. ArcLine has just submitted switchgear for approval.**
>
> **Their question is simple: does this meet clause 2.2.3 — and if it doesn't, what does it do to my energisation date?**
>
> **Today that's six tools, four people, two to three days. And no auditable answer at the end."**

---

### Sheet 06 · The Impact Chain — 2:05–3:20 · **LIVE PRODUCT**

*[Switch to the running app. If it is unavailable, stay on this sheet — it is the labelled backup and the numbers are identical. Say so out loud: "I'm using our labelled backup."]*

*[Click **Run connected flow**. Narrate each stage as it lands — roughly four seconds apart.]*

> **"One question. Watch it propagate.**
>
> **Specification — the offer is fifty kilo-amps against a required sixty-five. Non-compliant, cited to clause 2.2.3 and page one of the submittal.**
>
> **Procurement — that means a vendor resubmission. Thirty-five days of ETA variance on the shipment.**
>
> **Schedule — thirty-five days against seven days of float on T-140. Twenty-eight days of critical-path exposure, propagated through install, energisation and integrated systems test.**
>
> **Commissioning — readiness drops from sixty-five to forty-five. The energisation date is no longer supportable.**
>
> **Decision — three costed mitigations. Nothing is applied until a human approves."**

*[Click a mitigation card.]*

> **"Expedite recovers eighteen days at a twenty per cent premium, and the residual exposure recalculates live.**
>
> **Six clicks. Under ninety seconds. Every number traceable to a page.**
>
> **And to be clear — this is our synthetic corpus. It is not a production forecast."**

*[Say the word **synthetic** at least once. Judges mark honesty, and it is in your own demo protocol.]*

---

### Sheet 07 · Cited, or silent — 3:20–4:15

> **"Two questions, side by side.**
>
> **On the left, UPS battery autonomy — answered only from project evidence, with a citation carried on the claim itself.**
>
> **On the right, chiller seismic qualification — nothing in this project's documents supports an answer, so Atlas returns INSUFFICIENT_EVIDENCE and declines.**
>
> **That refusal is the feature. And it isn't a prompt instruction — retrieval, fusion and the sufficiency check all run without a language model, so it cannot be talked out of refusing.**
>
> **In EPC, a confident wrong answer is worse than no answer. This is the only behaviour a QA manager can sign a Tier Three handover against."**

---

### Sheet 08 · Who needs it — 4:15–5:00

> **"Our first users are Indian data-centre EPC delivery teams — L&T Construction, Tata Projects, Sterling and Wilson, who alone have delivered twenty-eight data-centre projects since 2015. The co-signer is the owner: NTT, STT, Sify, CtrlS, Yotta, AdaniConneX.**
>
> **Sizing, as arithmetic. Global construction-management software is a ten-point-eight billion dollar market. Data-centre construction software specifically, at Procore's own software intensity, is about three hundred and ninety million a year.**
>
> **And India: an eight-point-three gigawatt pipeline, at seven million dollars a megawatt, is fifty-eight billion of construction spend. At our rate that's twenty-nine million of licence value — eleven million of it already committed or under construction."**

*[Say every multiplier out loud. The method is what earns the number.]*

---

### Sheet 09 · How it makes money — 5:00–5:40

> **"We haven't sold this. Prototype, no revenue, no pilots, no letters of intent. I'd rather say that than have you ask.**
>
> **The model is a per-project licence priced off contract value — fifty lakh to one and a quarter crore per active project-year.**
>
> **Concretely: a fifty megawatt Tier Three campus in Chennai is about two thousand nine hundred crore. Atlas across that entire build is one and a half to two crore.**
>
> **Three months of stranded capital alone on that build is seventy-two crore.**
>
> **So the licence costs two to three per cent of the financing charge alone — before lost revenue, before liquidated damages."**

*[Stop talking after that sentence. Let it sit.]*

---

### Sheet 10 · Why it is better — 5:40–6:30

> **"Let me name the competition, because it's real.**
>
> **There is a live AI submittal-review category — BuildSync, Part3, Remy, SpecLens. Procore and Autodesk both market to data centres. CxAlloy and Facility Grid own commissioning.**
>
> **Every one of them owns one box in our chain. The submittal tools answer 'is this compliant?' and stop there. The commissioning tools start after the equipment has already arrived late.**
>
> **Nobody connects specification, procurement, schedule and commissioning as one evidence chain. That quadrant is empty.**
>
> **And we're built for Indian delivery economics — five and a half to eight million dollars a megawatt — not a US product retrofitted."**

*[Naming competitors first builds credibility. Do not skip it.]*

---

### Sheet 11 · Future plan — 6:30–7:15

> **"Our next step is one design partner and one live data-centre project.**
>
> **Three things come out of that. Authentication and role-based access — that is our honest blocker today. Real-project validation instead of a synthetic corpus. And the number we currently refuse to claim: hours saved. It is marked NOT_MEASURED in our own evaluation, and we will not put a figure on it until we have measured one.**
>
> **Three to nine months: Primavera, ERP and QMS adapters, live logistics, a second vertical. Then the portfolio tier, a Tier Three and Four commissioning audit pack, and the Middle East with the same contractors."**

---

### Sheet 12 · Close — 7:15–8:00

> **"Atlas moves an EPC team from finding out at commissioning, to knowing at submittal.**
>
> **What is measured today, on a labelled synthetic corpus: twenty-seven of twenty-seven documents ingested. Compliance precision, recall and F1 all one-point-zero. Seventeen of seventeen citations correct. A hundred and thirty-five backend tests green.**
>
> **And one that didn't win. Our advanced retrieval path scores zero-point-six-seven citation precision against the baseline's one-point-zero. It is in the report, unhidden. A system that hides its own regressions has no business asking an engineer to trust its findings.**
>
> **A hackathon prototype today. The control layer for what India is about to build, if we're right.**
>
> **Thank you."**

---

## 3. If you are running behind

The pacing pill in the deck turns amber at +20 s and red at +45 s. Cut in this order:

1. **Sheet 04** (how it works) — compress to one line: *"The model explains, it never decides."* Saves ~15 s.
2. **Sheet 05** (demo setup) — cut the six-tools list, keep the question. Saves ~12 s.
3. **Sheet 02** — drop the 35% submittal stat, keep the $30–150 M. Saves ~8 s.
4. **Sheet 11** — cut the 3–9 month and 9–18 month gates, keep only "one design partner, and the hours-saved number." Saves ~18 s.

**Never cut:** the $30–150 M number, the live Impact Chain, the refusal card, or the citation-precision disclosure. Those four are the pitch.

## 4. If the demo breaks

1. Say it plainly: *"The live API step is unavailable — I'm switching to a labelled static backup from our synthetic evaluation."* Never present stale UI as a live response.
2. Stay on sheet 06 and click **Run connected flow**. The numbers are identical to the seeded run.
3. If pressed for evidence, open appendix A1 (`O` → row 13) for the measured metrics.
4. Do not attempt a restart on stage.

## 5. Q&A bank

**"What's your accuracy on real project data?"**
Zero real-project validation. Everything measured is on a labelled synthetic corpus — compliance F1 of 1.0 on twelve labelled cases, seventeen of seventeen citations. We deliberately have not extrapolated from that. The first design partner is what buys us a real number.

**"How is this different from Procore's AI copilot?"**
Procore is the system of record and its copilot retrieves and summarises across a horizontal product. It does not take a specification deviation and compute the CPM impact on your energisation date. We integrate alongside it rather than replacing it — which is also why we price at a third of their rate.

**"BuildSync and Part3 already do AI submittal review."**
They do, and they do it well. They answer "is this compliant?" and stop at the submittal. We keep going — into the shipment ETA, the critical path, the readiness score, and a persisted human decision. That propagation is the product.

**"Why won't the LLM hallucinate an engineering number?"**
Structurally it cannot produce one. Compliance comparison, CPM float and readiness weights are deterministic Python. The model rewrites queries, extracts values and explains what the code computed. And the evidence gate refuses rather than filling gaps from model knowledge.

**"What's the moat?"**
Not the model — anyone can call an API. It is the evidence-graph schema, the deterministic engines per equipment class, and the audit trail a Tier III handover actually needs. Domain depth compounds, and a horizontal vendor will not build it for one vertical.

**"How many hours does it save?"**
We don't know, and we refuse to guess. It is literally `NOT_MEASURED` in our evaluation output. Measuring it is the first deliverable of a pilot.

**"Who is the buyer — contractor or owner?"**
We land with the EPC delivery team on a single project, because a project director can approve one to two crore without a board. We expand to the owner for the portfolio tier and the handover audit pack.

**"Data security — these documents are contractually confidential."**
Deployed inside the contractor's own tenancy. Project-scoped isolation is already how the system is built and is covered by cross-project tests. Authentication and RBAC are not implemented yet — that is our stated blocker and the first item in the next three months.

**"Why India first?"**
An 8.33 GW pipeline, the lowest build cost in the world, no incumbent owning the full chain here, and a policy regime actively subsidising the build-out. It is also where we are.

**"What data do you need to train on?"**
None. We don't train. It is retrieval over the customer's own project documents plus deterministic rules, so cold start is a document upload rather than a training set — and no customer data leaves their tenancy.

**"What about scanned drawings?"**
PDF text extraction with OCR fallback today. Computer vision on drawings is explicitly roadmap, not built.

**"Does it scale?"**
Honestly, not yet. Ingestion is synchronous today. Queue workers, object storage and Qdrant tenant sharding are roadmap — and we would rather do them after measuring a real bottleneck than guess at one.

## 6. Delivery notes

- **Pace:** ~130 words per minute. If you are hitting 150, you are rushing the numbers, and the numbers are the argument.
- **Three deliberate pauses:** after "$30–150 million" (sheet 02), after "two to three per cent of the financing charge" (sheet 09), after "no business asking an engineer to trust its findings" (sheet 12).
- **Honesty beats:** say "synthetic" on sheet 06, "no revenue, no pilots, no LOIs" on sheet 09, and "NOT_MEASURED" on sheet 11. Judges consistently reward disclosed limitations over polished claims — and it mirrors what the product itself does.
- **Numbers to know cold, without the slide:** 8.33 GW, $30–150 M, 65 vs 50 kAIC, 28 days exposure, ₹1.5–2 crore, 0.2432 vs 0.3226 on 16 held-out cases.
- **If a judge names a competitor you don't recognise:** *"I don't know that one — I'll look it up."* Never bluff. Appendix A2 has the full landscape you do know.
