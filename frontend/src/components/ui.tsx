import type {
  ButtonHTMLAttributes,
  CSSProperties,
  HTMLAttributes,
  InputHTMLAttributes,
  PropsWithChildren,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from "react";

import { cn } from "../lib/utils";

const field =
  "h-9 w-full rounded-md border border-slate-300 bg-white px-3 text-sm text-ink shadow-[inset_0_1px_0_rgba(11,31,54,.03)] " +
  "outline-none transition-crisp placeholder:text-slate-400 hover:border-slate-400 " +
  "focus:border-signal focus:ring-2 focus:ring-signal/25 disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-400";

/* ── surfaces ─────────────────────────────────────────────────────────────── */

export function Card({
  className,
  children,
  interactive = false,
  ...rest
}: PropsWithChildren<{ className?: string; interactive?: boolean }> & HTMLAttributes<HTMLElement>) {
  return (
    <section
      className={cn(
        "rounded-xl border border-slate-200/90 bg-white p-4 shadow-card",
        // The lift is 1px. Anything larger makes a grid of cards look like it is
        // breathing as the pointer crosses it, and shifts text enough to notice.
        interactive &&
          "cursor-pointer transition-base ease-settle hover:-translate-y-px hover:border-slate-300 hover:shadow-lift " +
            "focus-within:-translate-y-px focus-within:shadow-lift motion-reduce:hover:translate-y-0",
        className,
      )}
      {...rest}
    >
      {children}
    </section>
  );
}

/** Section heading with an eyebrow, used to give each panel a clear hierarchy. */
export function PanelTitle({
  eyebrow,
  title,
  detail,
  right,
}: {
  eyebrow?: string;
  title: string;
  detail?: ReactNode;
  right?: ReactNode;
}) {
  return (
    <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0">
        {eyebrow ? <p className="font-mono text-label uppercase text-signal">{eyebrow}</p> : null}
        <h2 className="mt-0.5 text-lg font-semibold tracking-tight text-ink">{title}</h2>
        {detail ? <p className="mt-1 max-w-prose text-sm leading-6 text-muted">{detail}</p> : null}
      </div>
      {right ? <div className="flex shrink-0 items-center gap-2">{right}</div> : null}
    </div>
  );
}

/* ── controls ─────────────────────────────────────────────────────────────── */

export function Button({
  className,
  variant = "primary",
  size = "md",
  loading = false,
  children,
  disabled,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger" | "signal";
  size?: "sm" | "md" | "lg";
  loading?: boolean;
}) {
  const variants = {
    primary: "bg-navy text-white shadow-card hover:bg-navy-hi active:bg-navy",
    signal: "bg-signal text-white shadow-card hover:bg-signal-hi active:bg-signal",
    secondary:
      "border border-slate-300 bg-white text-slate-700 hover:border-slate-400 hover:bg-slate-50 active:bg-slate-100",
    ghost: "text-slate-600 hover:bg-slate-100 hover:text-ink",
    danger: "bg-rose-700 text-white shadow-card hover:bg-rose-800 active:bg-rose-900",
  };
  const sizes = { sm: "h-8 px-3 text-sm", md: "h-9 px-3.5 text-sm", lg: "h-11 px-5 text-[0.95rem]" };

  return (
    <button
      className={cn(
        "group relative inline-flex shrink-0 items-center justify-center gap-1.5 overflow-hidden whitespace-nowrap rounded-md font-medium",
        "transition-crisp ease-swap disabled:cursor-not-allowed disabled:opacity-45 disabled:shadow-none",
        // A 1px press. Real buttons move; the amount that reads as tactile
        // rather than broken is very small.
        "active:translate-y-px motion-reduce:active:translate-y-0",
        sizes[size],
        variants[variant],
        className,
      )}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...props}
    >
      {loading ? <Spinner /> : null}
      <span className={cn("inline-flex items-center gap-1.5", loading && "opacity-80")}>{children}</span>
    </button>
  );
}

export function Spinner({ className }: { className?: string }) {
  return (
    <svg
      className={cn("h-3.5 w-3.5 shrink-0 animate-spin", className)}
      viewBox="0 0 16 16"
      fill="none"
      aria-hidden="true"
    >
      <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeOpacity=".25" strokeWidth="2" />
      <path d="M14.5 8A6.5 6.5 0 0 0 8 1.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn(field, className)} {...props} />;
}

export function Textarea({ className, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cn(field, "min-h-20 h-auto py-2 leading-6", className)} {...props} />;
}

export function Select({ className, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={cn(field, "cursor-pointer pr-8", className)} {...props} />;
}

/* ── status ───────────────────────────────────────────────────────────────── */

/**
 * A status or category chip.
 *
 * Takes children rather than just a tone on purpose. Two of the four status
 * colours sit below 3:1 on a light surface, so the documented mitigation is that
 * a status never travels as colour alone - the label is the accessible channel
 * and the colour is the fast one.
 */
export function Badge({
  children,
  tone = "slate",
  dot = false,
}: PropsWithChildren<{ tone?: "slate" | "green" | "amber" | "red" | "blue" | "serious"; dot?: boolean }>) {
  const styles = {
    slate: "bg-slate-100 text-slate-700 ring-slate-200",
    green: "bg-emerald-50 text-emerald-800 ring-emerald-200",
    amber: "bg-amber-50 text-amber-900 ring-amber-200",
    serious: "bg-orange-50 text-orange-900 ring-orange-200",
    red: "bg-rose-50 text-rose-800 ring-rose-200",
    blue: "bg-sky-50 text-sky-800 ring-sky-200",
  };
  const dots = {
    slate: "bg-slate-400",
    green: "bg-status-good",
    amber: "bg-status-warning",
    serious: "bg-status-serious",
    red: "bg-status-critical",
    blue: "bg-viz-500",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ring-inset",
        styles[tone],
      )}
    >
      {dot ? <span className={cn("h-1.5 w-1.5 shrink-0 rounded-full", dots[tone])} aria-hidden="true" /> : null}
      {children}
    </span>
  );
}

/* ── loading, empty, and error states ─────────────────────────────────────── */

/**
 * Skeleton placeholder.
 *
 * Sized by the caller to match the content it stands in for, so the layout does
 * not jump when real data replaces it. A spinner in the middle of a panel tells
 * the reader nothing about what is coming; a skeleton tells them the shape.
 */
export function Skeleton({ className, style }: { className?: string; style?: CSSProperties }) {
  return (
    <span
      aria-hidden="true"
      style={style}
      className={cn("relative block overflow-hidden rounded-md bg-slate-100", className)}
    >
      <span className="absolute inset-0 -translate-x-full animate-shimmer bg-gradient-to-r from-transparent via-white/70 to-transparent" />
    </span>
  );
}

export function SkeletonCard({ rows = 3 }: { rows?: number }) {
  return (
    <Card>
      <Skeleton className="h-3 w-24" />
      <Skeleton className="mt-3 h-7 w-2/5" />
      <div className="mt-4 space-y-2">
        {Array.from({ length: rows }).map((_, index) => (
          <Skeleton key={index} className="h-3" style={{ width: `${88 - index * 14}%` }} />
        ))}
      </div>
    </Card>
  );
}

export function EmptyState({
  title,
  detail,
  action,
  icon,
}: {
  title: string;
  detail?: ReactNode;
  action?: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <div className="rounded-xl border border-dashed border-slate-300 bg-white/60 px-6 py-12 text-center">
      {icon ? <div className="mx-auto mb-3 text-slate-300">{icon}</div> : null}
      <p className="text-sm font-semibold text-ink">{title}</p>
      {detail ? <p className="mx-auto mt-1.5 max-w-prose text-sm leading-6 text-muted">{detail}</p> : null}
      {action ? <div className="mt-4 flex justify-center">{action}</div> : null}
    </div>
  );
}

/** Inline result banner. Tone carries an icon so it is not colour alone. */
export function Notice({ kind, children }: PropsWithChildren<{ kind: "success" | "error" | "info" }>) {
  const styles = {
    success: "border-emerald-200 bg-emerald-50 text-emerald-900",
    error: "border-rose-200 bg-rose-50 text-rose-900",
    info: "border-sky-200 bg-sky-50 text-sky-900",
  };
  const glyphs = { success: "✓", error: "!", info: "i" };
  const glyphStyles = {
    success: "bg-status-good text-white",
    error: "bg-status-critical text-white",
    info: "bg-viz-500 text-white",
  };
  return (
    <div
      role={kind === "error" ? "alert" : "status"}
      className={cn(
        "mb-4 flex animate-rise items-start gap-2.5 rounded-lg border px-3 py-2 text-sm leading-6",
        styles[kind],
      )}
    >
      <span
        aria-hidden="true"
        className={cn(
          "mt-0.5 grid h-4 w-4 shrink-0 place-items-center rounded-full text-[0.65rem] font-bold leading-none",
          glyphStyles[kind],
        )}
      >
        {glyphs[kind]}
      </span>
      <span className="min-w-0">{children}</span>
    </div>
  );
}

/** Keyboard-and-touch friendly hint. Title attribute, not a custom tooltip. */
export function Hint({ label, children }: PropsWithChildren<{ label: string }>) {
  return (
    <span title={label} className="cursor-help border-b border-dotted border-slate-400">
      {children}
    </span>
  );
}
