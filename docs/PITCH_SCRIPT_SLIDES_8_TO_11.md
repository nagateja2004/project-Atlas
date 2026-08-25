# Spoken script — slides 8 to 11

**About 120 seconds.** Roughly 30 seconds a slide.

Written as connected speech, not bullet points — each slide hands off to the
next, so the four play as one argument rather than four separate readings. The
**bold** words are where to lean; everything else can move quickly.

⚠️ = say it exactly as written. Those three lines are what make every number
around them worth stating.

---

## Slide 8 — MARKET PLAN · ~30s

> India has announced a data-centre pipeline of **8.33 gigawatts**, and about
> **1,123 megawatts** of it is actually running today — roughly doubling by
> 2027. So there is an enormous gap between what has been promised and what has
> been built, and every megawatt in that gap belongs to a delivery team working
> to a date somebody has already committed to.
>
> Those are our users: project controls, procurement, QA and commissioning. The
> contractor buys Atlas for a project; the owner buys it across a portfolio. We
> start deliberately narrow, on **30 to 100 megawatt builds in India**, because
> that is the size where a delay is expensive enough to be worth preventing.
>
> ⚠️ And the $29 million on the right is our own arithmetic, not a published
> market figure — the assumption is on the slide.

*(hand off)* → **"So that's the market. Here's how we charge for it."**

---

## Slide 9 — PRICED AGAINST DELAY · ~30s

> A project licence runs **fifty lakh to one and a quarter crore** a year, and a
> portfolio licence starts at **three point three crore**.
>
> But we don't ask anyone to roll this out across a campus. We start with a
> **twelve-week pilot on a single equipment package** — the switchgear, say —
> and we measure what it caught: deviations found, and schedule exposure
> identified before it turned into a delay. If those numbers hold up, we expand.
> If they don't, the customer has spent twelve weeks rather than a year.
>
> The reason that price works is simple. **A three-month slip on a 50 megawatt
> project costs roughly ₹72 crore in financing alone** — before lost revenue,
> before penalties. We cost two to three percent of that one number.
>
> ⚠️ That ₹72 crore is an illustrative calculation, not a measured customer
> result.

*(hand off)* → **"And we can price against delay because of what the product actually does."**

---

## Slide 10 — WHY ATLAS · ~30s

> If you take one sentence from this pitch, take this one: **other tools manage
> project stages — Atlas connects their consequences.**
>
> It works in three moves. **Evidence:** you ask one question and get one cited
> answer, linked back to the clause it came from; if the documents don't support
> an answer, Atlas says so rather than guessing. **Consequence:** and this is the
> part nobody else does — we don't stop at "non-compliant", we carry that
> deviation forward into the procurement delay, the critical path, and the
> commissioning impact. **Control:** the engineering maths is deterministic code
> rather than a language model, and every action Atlas suggests stays pending
> until an engineer approves it.
>
> **One question, one cited answer, one connected impact chain, one controlled
> decision.**

*(hand off)* → **"That chain has to hold when it's not one project."**

---

## Slide 11 — SCALABILITY · ~30s

> It's built for that already: async and stateless, so it takes replicas today,
> with every row and every vector isolated by project.
>
> From there we scale in three stages, and each one is triggered by a customer
> rather than a calendar. With our **first design partner** we add sparse
> retrieval, worker-based ingestion and object storage, targeting p95 under two
> seconds. At **five to ten projects** we split embedding and reranking into
> their own service and add read replicas and quotas. At **portfolio scale** it's
> tenant sharding, autoscaling, backups and published SLOs.
>
> **We split services only after measuring a real bottleneck** — a prototype that
> ships as twelve microservices isn't scalable, it's just harder to change.

---

## If you're running over

Cut slide 11 to: *"It's async, stateless and project-isolated, so it takes
replicas today — and we scale in three stages, splitting services only after
measuring a real bottleneck."*

Never cut the ₹72 crore line or the hook on slide 10. Those two carry the pitch.

## Three questions you'll get

**"Is the $29M real?"**
> It's our arithmetic and the assumption is on the slide — change the software
> rate and the number changes. We'd rather show the method than quote a number
> we can't defend.

**"Why not just Procore?"**
> They'll keep Procore; we don't replace the system of record. Procore tells you
> the submittal was rejected. It won't tell you what that does to your
> energisation date — and that calculation is the product.

**"You have no customers."**
> Correct — no revenue, no pilots, no letters of intent. That's exactly why the
> entry point is a twelve-week pilot on one package rather than a campus.
