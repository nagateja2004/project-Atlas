"use client";

import type { ReactNode } from "react";
import { useState } from "react";

import { cn } from "../lib/utils";
import { CountUp } from "./motion";
import { Badge, Card } from "./ui";

/**
 * Data visualization primitives.
 *
 * Two rules shape everything here.
 *
 * The palette is split by job. Magnitude uses one sequential hue (`viz-300` to
 * `viz-700`), validated as an ordinal ramp: monotone lightness, adjacent ΔL >=
 * 0.06, single hue, light end 2.11:1 against WHITE. That last figure is why
 * every component below renders on a white card - the same ramp measures 1.95:1
 * on the canvas ground and fails the 2:1 floor. State uses the fixed status
 * palette, never a series colour, and always beside a text label because two of
 * its four steps are sub-3:1 on light by design.
 *
 * The form follows the data's job rather than the desire for a chart. A single
 * current value is a stat tile, not a one-bar bar chart. A ratio against a limit
 * is a meter, not a two-slice pie. Only ranked magnitude across items becomes
 * bars.
 */

/* ── stat tile ────────────────────────────────────────────────────────────── */

export type Trend = { direction: "up" | "down" | "flat"; label: string; good?: boolean };

/**
 * One headline value.
 *
 * The value animates the first time it is seen; the unit sits outside the
 * animated span so it does not jitter as digits change width.
 */
export function StatTile({
  label,
  value,
  unit,
  decimals = 0,
  trend,
  footnote,
  tone = "neutral",
  loading = false,
}: {
  label: string;
  value: number | null;
  unit?: string;
  decimals?: number;
  trend?: Trend;
  footnote?: ReactNode;
  tone?: "neutral" | "good" | "warning" | "serious" | "critical";
  loading?: boolean;
}) {
  const tones = {
    neutral: "text-ink",
    good: "text-status-good",
    warning: "text-amber-700",
    serious: "text-orange-800",
    critical: "text-status-critical",
  };

  return (
    <Card className="group relative overflow-hidden">
      {/* A hairline that fills on hover: enough to signal the tile is a live
          surface without competing with the number. */}
      <span
        aria-hidden="true"
        className="absolute inset-x-0 top-0 h-px origin-left scale-x-0 bg-signal transition-base ease-settle group-hover:scale-x-100"
      />
      <p className="font-mono text-label uppercase text-muted">{label}</p>

      {loading ? (
        <span className="mt-2 block h-9 w-24 animate-pulse rounded bg-slate-100" aria-hidden="true" />
      ) : value === null ? (
        <p className="mt-1 text-figure font-semibold leading-none text-slate-300">—</p>
      ) : (
        <p className={cn("mt-1 text-figure font-semibold leading-none", tones[tone])}>
          <CountUp value={value} decimals={decimals} />
          {unit ? <span className="ml-1 text-base font-medium text-muted">{unit}</span> : null}
        </p>
      )}

      {trend && !loading ? (
        <p className="mt-2 flex items-center gap-1.5 text-xs font-medium">
          <span
            aria-hidden="true"
            className={cn(
              "font-mono",
              trend.direction === "flat"
                ? "text-muted"
                : trend.good
                  ? "text-status-good"
                  : "text-status-critical",
            )}
          >
            {trend.direction === "up" ? "▲" : trend.direction === "down" ? "▼" : "■"}
          </span>
          <span className="text-muted">{trend.label}</span>
        </p>
      ) : null}

      {footnote ? <p className="mt-2 text-xs leading-5 text-muted">{footnote}</p> : null}
    </Card>
  );
}

/* ── meter ────────────────────────────────────────────────────────────────── */

/**
 * A single ratio against a limit.
 *
 * The track is a lighter step of the same hue as the fill rather than gray, so
 * the reader sees one scale with a filled portion instead of two competing
 * colours. Thresholds are labelled, because a bar that turns red without saying
 * why is a decoration.
 */
export function Meter({
  label,
  value,
  max = 100,
  unit = "",
  thresholds,
  caption,
}: {
  label: string;
  value: number;
  max?: number;
  unit?: string;
  /** Ascending boundaries mapped to a status, e.g. [[50,"critical"],[75,"warning"]]. */
  thresholds?: Array<[number, "critical" | "warning" | "serious" | "good"]>;
  caption?: ReactNode;
}) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));

  const status = (() => {
    if (!thresholds) return null;
    for (const [limit, tone] of thresholds) if (value < limit) return tone;
    return "good" as const;
  })();

  const fills = {
    good: "bg-status-good",
    warning: "bg-status-warning",
    serious: "bg-status-serious",
    critical: "bg-status-critical",
  };
  const badgeTone = { good: "green", warning: "amber", serious: "serious", critical: "red" } as const;

  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between gap-3">
        <span className="font-mono text-label uppercase text-muted">{label}</span>
        <span className="flex items-center gap-2">
          <span className="tabular text-sm font-semibold text-ink">
            <CountUp value={value} />
            {unit}
          </span>
          {status ? (
            <Badge tone={badgeTone[status]} dot>
              {status === "good" ? "Ready" : status === "critical" ? "Not ready" : "Needs review"}
            </Badge>
          ) : null}
        </span>
      </div>
      <div
        className="h-2.5 w-full overflow-hidden rounded-full bg-viz-100"
        role="meter"
        aria-valuenow={Math.round(value)}
        aria-valuemin={0}
        aria-valuemax={max}
        aria-label={label}
      >
        <div
          className={cn(
            "h-full rounded-full transition-[width] duration-story ease-settle",
            status ? fills[status] : "bg-viz-500",
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
      {caption ? <p className="mt-1.5 text-xs leading-5 text-muted">{caption}</p> : null}
    </div>
  );
}

/* ── ranked bars ──────────────────────────────────────────────────────────── */

export type BarDatum = { label: string; value: number; note?: ReactNode; emphasis?: boolean };

/**
 * Horizontal bars for ranked magnitude.
 *
 * Horizontal because the labels are task and equipment names, which do not fit
 * under a vertical column without rotating them. One hue, darker with
 * magnitude; the ramp is stepped rather than continuous so adjacent bars stay
 * distinguishable. Values are direct-labelled at the end of each bar, so no
 * axis or gridline is needed and nothing depends on colour alone.
 *
 * Bars carry a 2px surface gap and a 4px rounded data-end anchored to the
 * baseline, per the mark spec.
 */
export function BarSeries({
  data,
  unit = "",
  max,
  emptyLabel = "No values to plot.",
}: {
  data: BarDatum[];
  unit?: string;
  max?: number;
  emptyLabel?: string;
}) {
  const [hovered, setHovered] = useState<number | null>(null);

  if (!data.length) {
    return <p className="py-6 text-center text-sm text-muted">{emptyLabel}</p>;
  }

  const ceiling = max ?? Math.max(...data.map((d) => d.value), 1);
  // Steps run light to dark with rank. Index 0 is the largest value, so it takes
  // the darkest step.
  const steps = ["bg-viz-700", "bg-viz-600", "bg-viz-500", "bg-viz-400", "bg-viz-300"];
  const ranked = [...data].sort((a, b) => b.value - a.value);

  return (
    <ul className="space-y-2">
      {ranked.map((datum, index) => {
        const pct = Math.max(1.5, (datum.value / ceiling) * 100);
        const active = hovered === index;
        return (
          <li
            key={`${datum.label}-${index}`}
            onPointerEnter={() => setHovered(index)}
            onPointerLeave={() => setHovered(null)}
            className="group/bar rounded-md px-1 py-1 transition-crisp hover:bg-slate-50"
          >
            <div className="flex items-baseline justify-between gap-3">
              <span className="min-w-0 truncate text-sm text-ink" title={datum.label}>
                {datum.label}
              </span>
              <span className="tabular shrink-0 text-sm font-semibold text-ink">
                {datum.value}
                {unit ? <span className="ml-0.5 font-normal text-muted">{unit}</span> : null}
              </span>
            </div>
            <div className="mt-1 h-2 w-full rounded-sm bg-slate-100">
              <div
                className={cn(
                  "h-full rounded-sm transition-[width,opacity] duration-story ease-settle",
                  datum.emphasis ? "bg-status-critical" : steps[Math.min(index, steps.length - 1)],
                  hovered !== null && !active && "opacity-45",
                )}
                style={{ width: `${pct}%` }}
              />
            </div>
            {datum.note ? (
              <p
                className={cn(
                  "mt-1 text-xs leading-5 text-muted transition-crisp",
                  active ? "opacity-100" : "opacity-0 group-hover/bar:opacity-100",
                )}
              >
                {datum.note}
              </p>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}

/* ── impact chain ─────────────────────────────────────────────────────────── */

export type ChainStage = {
  key: string;
  label: string;
  value?: string;
  detail?: string;
  tone?: "neutral" | "warning" | "serious" | "critical" | "good";
};

/**
 * The propagation diagram: a deviation becoming a dated consequence.
 *
 * A process diagram, not a chart - there is no scale here, only sequence and
 * state. Rendered as a real list so it reads in order without the SVG, with the
 * connector drawn behind it. Vertical on small screens, because six horizontal
 * stages on a phone means either a scroll nobody finds or text nobody can read.
 */
export function ImpactChain({
  stages,
  activeIndex,
  onSelect,
}: {
  stages: ChainStage[];
  activeIndex?: number;
  onSelect?: (index: number) => void;
}) {
  // White cards with a coloured top rule, rather than tinted fills. Six pale
  // washes sitting side by side read as muddy and make the row look like a
  // warning in itself; a rule carries the same state on a clean surface.
  const accents = {
    neutral: "bg-slate-300",
    good: "bg-status-good",
    warning: "bg-status-warning",
    serious: "bg-status-serious",
    critical: "bg-status-critical",
  };
  const pips = {
    neutral: "bg-slate-300",
    good: "bg-status-good",
    warning: "bg-status-warning",
    serious: "bg-status-serious",
    critical: "bg-status-critical",
  };

  return (
    <ol className="relative grid gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-6">
      {stages.map((stage, index) => {
        const tone = stage.tone ?? "neutral";
        const active = activeIndex === index;
        const Tag = onSelect ? "button" : "div";
        return (
          <li key={stage.key} className="relative">
            {/* Connector to the next stage. Hidden on the last item and on the
                narrow layout, where the cards already stack in order. */}
            {index < stages.length - 1 ? (
              <span
                aria-hidden="true"
                className="absolute -right-3 top-1/2 z-0 hidden h-px w-3 bg-slate-300 2xl:block"
              />
            ) : null}
            <Tag
              type={onSelect ? "button" : undefined}
              onClick={onSelect ? () => onSelect(index) : undefined}
              className={cn(
                "relative z-10 flex h-full w-full flex-col overflow-hidden rounded-lg border border-slate-200 bg-white p-3 pt-3.5 text-left shadow-card transition-base ease-settle",
                onSelect && "hover:-translate-y-px hover:shadow-card-hover motion-reduce:hover:translate-y-0",
                active && "ring-2 ring-signal/40",
              )}
            >
              <span aria-hidden="true" className={cn("absolute inset-x-0 top-0 h-[3px]", accents[tone])} />
              <span className="flex items-center gap-1.5">
                <span aria-hidden="true" className={cn("h-1.5 w-1.5 rounded-full", pips[tone])} />
                <span className="font-mono text-label uppercase text-muted">
                  {String(index + 1).padStart(2, "0")}
                </span>
              </span>
              <span className="mt-1.5 text-sm font-semibold leading-5 text-ink">{stage.label}</span>
              {stage.value ? (
                <span className="tabular mt-1 text-sm font-semibold text-ink">{stage.value}</span>
              ) : null}
              {stage.detail ? (
                <span className="mt-1 text-xs leading-5 text-muted">{stage.detail}</span>
              ) : null}
            </Tag>
          </li>
        );
      })}
    </ol>
  );
}

/* ── data table fallback ──────────────────────────────────────────────────── */

/**
 * The table view every chart owes its reader.
 *
 * Colour and length are fast but approximate; a reader who needs the exact
 * figure, or who cannot use the colour channel at all, needs the numbers. Kept
 * collapsed so it does not compete with the chart it backs.
 */
export function TableView({
  caption,
  columns,
  rows,
}: {
  caption: string;
  columns: string[];
  rows: Array<Array<ReactNode>>;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-3 border-t border-slate-100 pt-2">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="flex items-center gap-1.5 text-xs font-semibold text-muted transition-crisp hover:text-ink"
      >
        <span aria-hidden="true" className={cn("transition-base", open && "rotate-90")}>
          ›
        </span>
        {open ? "Hide" : "Show"} values as a table
      </button>
      {open ? (
        <div className="scroll-x mt-2 animate-fade-in">
          <table className="w-full text-left text-sm">
            <caption className="sr-only">{caption}</caption>
            <thead>
              <tr className="border-b border-slate-200">
                {columns.map((column) => (
                  <th key={column} className="py-1.5 pr-3 font-mono text-label uppercase text-muted">
                    {column}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr key={index} className="border-b border-slate-100 last:border-0">
                  {row.map((cell, cellIndex) => (
                    <td key={cellIndex} className="py-1.5 pr-3 text-ink">
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}
