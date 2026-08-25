"use client";

import { useState } from "react";

import { cn } from "../lib/utils";
import { useScrollProgress } from "../lib/motion";
import { Reveal, Stagger } from "./motion";
import { Button, Card } from "./ui";

/**
 * The scroll narrative: how one clause in a specification becomes a dated
 * consequence.
 *
 * This exists because the product's central claim is a *chain*, and a dashboard
 * of panels shows the links without showing that they connect. The story is the
 * argument; the dashboard is the evidence.
 *
 * Every figure here is drawn from the seeded synthetic scenario rather than
 * invented for the page, and the panel says so. A narrative built on numbers a
 * reader cannot go and check is a brochure.
 */

/*
 * The chain, described as a mechanism.
 *
 * This previously narrated the seeded switchgear scenario: 50 kAIC against 65
 * required, 35 days, 28 days, a readiness score of 45. Those are one example's
 * figures, and presenting them on the landing page stated a particular
 * project's numbers as though they were the product. Nothing in the chain is
 * switchgear-specific - it runs on any equipment item that has a specification,
 * a submittal and a dated milestone.
 *
 * So the steps now say what each link *does*. The worked example lives in the
 * workspace, where every figure is attached to the document it came from and
 * can be checked, which is where a number belongs.
 */
const CHAIN = [
  {
    key: "deviation",
    stage: "Specification",
    headline: "A requirement is not met",
    signal: "Offered value against the specified one",
    body: "A submittal offers something the specification does not allow - a rating, a capacity, a class, a clearance. The document rarely says so; the comparison has to be made, in the unit the specification uses rather than the unit the vendor quoted.",
    tone: "critical" as const,
  },
  {
    key: "vendor",
    stage: "Procurement",
    headline: "It becomes a resubmission",
    signal: "Vendor re-offer required",
    body: "Equipment that does not meet the requirement has to be re-offered. That is not a paperwork step: the clock on the replacement starts from the decision, and the replacement carries its own lead time.",
    tone: "serious" as const,
  },
  {
    key: "delivery",
    stage: "Delivery",
    headline: "The delivery date moves",
    signal: "Forecast arrival against the dated milestone",
    body: "The forecast arrival moves out, and the delivery milestone everything downstream depends on moves with it. This is the point where a document problem becomes a date.",
    tone: "critical" as const,
  },
  {
    key: "schedule",
    stage: "Schedule",
    headline: "Float absorbs what it can",
    signal: "Critical-path exposure after float",
    body: "Some of the slip is absorbed by float. What is left propagates along the dependency chain to installation, energization and the integrated systems test - computed from the schedule, not estimated.",
    tone: "critical" as const,
  },
  {
    key: "commissioning",
    stage: "Commissioning",
    headline: "Readiness is recomputed",
    signal: "Deterministic score from the rules",
    body: "Readiness is not a status somebody types in. It is computed from the procedures that can currently be completed, so it falls on its own when the equipment they depend on is not there.",
    tone: "warning" as const,
  },
  {
    key: "decision",
    stage: "Decision",
    headline: "A person decides",
    signal: "Options and evidence, awaiting a reviewer",
    body: "Atlas produces the mitigation options and the evidence behind each one. It approves nothing. The approved record is created by a reviewer and marked as theirs.",
    tone: "good" as const,
  },
];

const TONE_RING = {
  critical: "ring-status-critical/30",
  serious: "ring-status-serious/30",
  warning: "ring-status-warning/40",
  good: "ring-status-good/30",
};
const TONE_PIP = {
  critical: "bg-status-critical",
  serious: "bg-status-serious",
  warning: "bg-status-warning",
  good: "bg-status-good",
};

/* ── hero ─────────────────────────────────────────────────────────────────── */

export function StoryHero({ onEnter, entering }: { onEnter: () => void; entering?: boolean }) {
  return (
    <section className="relative isolate overflow-hidden bg-navy-bloom text-white">
      {/* Drafting grid, faint, on the navy ground. */}
      <span
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 opacity-[.16]"
        style={{
          backgroundImage:
            "linear-gradient(to right, rgba(255,255,255,.5) 1px, transparent 1px), linear-gradient(to bottom, rgba(255,255,255,.5) 1px, transparent 1px)",
          backgroundSize: "44px 44px",
          maskImage: "radial-gradient(90% 70% at 30% 10%, black 30%, transparent 100%)",
          WebkitMaskImage: "radial-gradient(90% 70% at 30% 10%, black 30%, transparent 100%)",
        }}
      />

      <div className="relative mx-auto max-w-6xl px-6 pb-16 pt-16 sm:pb-20 sm:pt-20">
        <Reveal>
          <span className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 font-mono text-label uppercase text-sky-200 ring-1 ring-inset ring-white/15">
            <span aria-hidden="true" className="relative flex h-1.5 w-1.5">
              <span className="absolute inset-0 animate-pulse-ring rounded-full bg-signal-hi" />
              <span className="relative h-1.5 w-1.5 rounded-full bg-signal-hi" />
            </span>
            EPC project intelligence · synthetic demo data
          </span>
        </Reveal>

        <Reveal delay={80}>
          <h1 className="mt-6 max-w-4xl text-display-sm font-semibold text-white sm:text-display lg:text-display-lg">
            A clause in a specification is not a document problem.
            <span className="block text-sky-300/90">It is a date.</span>
          </h1>
        </Reveal>

        <Reveal delay={160}>
          <p className="mt-6 max-w-prose text-base leading-7 text-sky-100/80 sm:text-lg">
            Project Atlas follows one technical deviation through procurement, schedule and
            commissioning, and stops at the person who has to decide. Every step carries the
            document, page and clause it came from.
          </p>
        </Reveal>

        <Reveal delay={240}>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Button size="lg" variant="signal" onClick={onEnter} loading={entering}>
              Open the workspace
              <span aria-hidden="true" className="transition-crisp group-hover:translate-x-0.5">
                →
              </span>
            </Button>
            <a
              href="#chain"
              className="inline-flex h-11 items-center rounded-md px-4 text-[0.95rem] font-medium text-sky-100/90 ring-1 ring-inset ring-white/20 transition-crisp hover:bg-white/10 hover:text-white"
            >
              See how the chain works
            </a>
          </div>
        </Reveal>

        {/* The six links, named. Previously four figures lifted from the seeded
            switchgear scenario, which read as the product's numbers rather
            than one example's. */}
        <Reveal delay={300}>
          <ol className="mt-10 flex max-w-3xl flex-wrap items-center gap-x-2 gap-y-2 border-t border-white/15 pt-5 font-mono text-label uppercase text-sky-200/80">
            {["Specification", "Procurement", "Delivery", "Schedule", "Commissioning", "Decision"].map((stage, index) => (
              <li key={stage} className="flex items-center gap-2">
                {index > 0 ? <span aria-hidden="true" className="text-sky-400/50">→</span> : null}
                <span>{stage}</span>
              </li>
            ))}
          </ol>
        </Reveal>
      </div>
    </section>
  );
}

/* ── the chain ────────────────────────────────────────────────────────────── */

/**
 * Sticky-scroll narrative.
 *
 * The rail on the left tracks scroll progress exactly, so the reader always
 * knows where they are in the argument. On narrow screens the sticky column is
 * dropped entirely and the steps simply stack - a sticky element taller than a
 * phone viewport traps the content behind it.
 */
export function StoryChain() {
  const { ref, progress } = useScrollProgress<HTMLDivElement>();
  const [open, setOpen] = useState<string | null>(CHAIN[0].key);

  // How far down the chain the reader has scrolled. Slightly ahead of raw
  // progress so the spine reaches a step as it becomes readable, not after.
  const reached = Math.min(CHAIN.length - 1, Math.floor(progress * CHAIN.length * 1.15));

  return (
    <section id="chain" ref={ref} className="mx-auto max-w-4xl scroll-mt-20 px-6 py-16 sm:py-20">
      <Reveal>
        <p className="font-mono text-label uppercase text-signal">The impact chain</p>
        <h2 className="mt-2 text-display-sm font-semibold tracking-tight text-ink sm:text-display">
          Six steps, each one cited
        </h2>
        <p className="mt-4 max-w-prose text-base leading-7 text-muted">
          The same six links run for any equipment item that has a specification, a submittal and a
          dated milestone. The workspace holds a worked example with real figures, each one attached
          to the document, page and clause it came from, so the chain can be checked rather than
          taken on trust.
        </p>
      </Reveal>

      {/*
        A timeline, not a list of cards.
        The previous version was six separate rows beside a second "propagation"
        column that restated them - which showed the links but not the fact that
        they connect, and said everything twice. One spine with a node per step
        carries the causality visually, and the progress fill tells the reader
        where they are without a duplicate rail.
      */}
      <ol className="relative mt-10">
        {/* The spine. Behind the nodes, inset to their centre. */}
        <span aria-hidden="true" className="absolute bottom-6 left-[11px] top-3 w-px bg-slate-200 sm:left-[15px]">
          <span
            className="absolute inset-x-0 top-0 bg-signal transition-[height] duration-slow ease-swap"
            style={{ height: `${((reached + 1) / CHAIN.length) * 100}%` }}
          />
        </span>

        {CHAIN.map((step, index) => {
          const isOpen = open === step.key;
          const isReached = index <= reached;
          return (
            <Reveal as="li" key={step.key} delay={index * 40} className="relative pb-3 pl-10 last:pb-0 sm:pl-14">
              {/* Node on the spine. Filled once the reader reaches it. */}
              <span
                aria-hidden="true"
                className={cn(
                  "absolute left-0 top-2 grid h-[23px] w-[23px] place-items-center rounded-full border-2 bg-white font-mono text-[0.6rem] font-bold transition-base ease-settle sm:h-[31px] sm:w-[31px] sm:text-[0.7rem]",
                  isReached ? "border-signal text-signal" : "border-slate-300 text-slate-400",
                )}
              >
                {String(index + 1).padStart(2, "0")}
              </span>

              <button
                type="button"
                onClick={() => setOpen(isOpen ? null : step.key)}
                aria-expanded={isOpen}
                className={cn(
                  "group w-full rounded-lg border bg-white p-4 text-left shadow-card transition-base ease-settle",
                  isOpen ? cn("ring-2", TONE_RING[step.tone]) : "hover:-translate-y-px hover:shadow-card-hover motion-reduce:hover:translate-y-0",
                )}
              >
                <span className="flex items-center gap-1.5">
                  <span aria-hidden="true" className={cn("h-1.5 w-1.5 rounded-full", TONE_PIP[step.tone])} />
                  <span className="font-mono text-label uppercase text-signal">{step.stage}</span>
                </span>

                <span className="mt-1.5 block text-lg font-semibold leading-6 text-ink">{step.headline}</span>
                <span className="mt-0.5 block text-xs text-muted">{step.signal}</span>

                <span
                  className={cn(
                    "grid transition-[grid-template-rows,opacity] duration-base ease-settle",
                    isOpen ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0",
                  )}
                >
                  <span className="overflow-hidden">
                    <span className="mt-3 block border-t border-slate-100 pt-3 text-sm leading-6 text-muted">
                      {step.body}
                    </span>
                  </span>
                </span>
              </button>
            </Reveal>
          );
        })}
      </ol>
    </section>
  );
}

/* ── what it refuses to do ────────────────────────────────────────────────── */

const GUARDRAILS = [
  {
    title: "Arithmetic is code, not a model",
    body: "Delay days, unit conversions, pass/fail and readiness scores are computed in Python. A language model is asked to understand the question and explain the result, never to do the sums.",
  },
  {
    title: "No evidence, no answer",
    body: "An answer with no supporting document returns INSUFFICIENT_EVIDENCE rather than a confident guess. Generated claims are checked against the retrieved spans before they are shown.",
  },
  {
    title: "Approvals belong to people",
    body: "Every AI output is a suggestion. Reviewer decisions and commissioning records are separate, attributed, and the only things treated as approved.",
  },
  {
    title: "Synthetic data, labelled",
    body: "The corpus is fictional and marked on every document. Nothing here reproduces a real standard, vendor, or project, and simulated figures are never presented as measured.",
  },
];

export function StoryGuardrails() {
  return (
    <section className="border-y border-hairline bg-white">
      <div className="mx-auto max-w-6xl px-6 py-16 sm:py-20">
        <Reveal className="max-w-prose">
          <p className="font-mono text-label uppercase text-signal">Guardrails</p>
          <h2 className="mt-2 text-display-sm font-semibold tracking-tight text-ink sm:text-display">
            What it deliberately will not do
          </h2>
          <p className="mt-4 text-base leading-7 text-muted">
            In engineering, a confident wrong answer is worse than no answer. These are constraints
            in the code, not intentions.
          </p>
        </Reveal>

        <Stagger className="mt-10 grid gap-4 sm:grid-cols-2" step={80}>
          {GUARDRAILS.map((item) => (
            <Card key={item.title} interactive className="group h-full p-5">
              <div className="flex items-start gap-3">
                <span
                  aria-hidden="true"
                  className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-md bg-signal-soft text-sm font-bold text-signal transition-base group-hover:bg-signal group-hover:text-white"
                >
                  ✓
                </span>
                <div className="min-w-0">
                  <h3 className="text-base font-semibold text-ink">{item.title}</h3>
                  <p className="mt-1.5 text-sm leading-6 text-muted">{item.body}</p>
                </div>
              </div>
            </Card>
          ))}
        </Stagger>
      </div>
    </section>
  );
}

export function StoryClose({ onEnter, entering }: { onEnter: () => void; entering?: boolean }) {
  return (
    <section className="relative isolate overflow-hidden bg-navy-bloom text-white">
      <span aria-hidden="true" className="absolute inset-0 animate-shimmer bg-signal-sheen opacity-40" />
      <div className="relative mx-auto max-w-6xl px-6 py-16 text-center sm:py-20">
        <Reveal>
          <h2 className="mx-auto max-w-3xl text-display-sm font-semibold sm:text-display">
            The chain is inspectable. Go and check it.
          </h2>
          <p className="mx-auto mt-4 max-w-prose text-base leading-7 text-sky-100/80">
            Open the workspace, pick any equipment item with an open finding, and follow it from the
            clause to the decision. Every figure links back to the document, page and section it
            came from.
          </p>
          <div className="mt-8 flex justify-center">
            <Button size="lg" variant="signal" onClick={onEnter} loading={entering}>
              Open the workspace
              <span aria-hidden="true" className="transition-crisp group-hover:translate-x-0.5">
                →
              </span>
            </Button>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
