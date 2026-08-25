"use client";

import type { PropsWithChildren, ReactNode } from "react";
import { Children, isValidElement } from "react";

import { cn } from "../lib/utils";
import { useCountUp, useInView } from "../lib/motion";

/**
 * Reveal children when they scroll into view.
 *
 * The element is rendered in its final position and only the opacity/transform
 * are animated, so nothing reflows as it appears - a reveal that changes layout
 * makes the whole page shudder on every scroll.
 */
export function Reveal({
  children,
  className,
  delay = 0,
  as: Tag = "div",
}: PropsWithChildren<{ className?: string; delay?: number; as?: "div" | "section" | "li" | "article" | "header" }>) {
  const { ref, inView } = useInView<HTMLDivElement>();
  return (
    <Tag
      ref={ref as never}
      className={cn(
        "transition-[opacity,transform] duration-slow ease-settle motion-reduce:transition-none",
        inView ? "translate-y-0 opacity-100" : "translate-y-3.5 opacity-0",
        className,
      )}
      style={inView && delay ? { transitionDelay: `${delay}ms` } : undefined}
    >
      {children}
    </Tag>
  );
}

/**
 * Reveal a list with a per-child delay.
 *
 * The stagger is capped: past roughly eight items an incremental delay stops
 * reading as choreography and starts reading as a slow page. Later children
 * share the last step instead of waiting ever longer.
 */
export function Stagger({
  children,
  className,
  step = 70,
  max = 8,
}: PropsWithChildren<{ className?: string; step?: number; max?: number }>) {
  const items = Children.toArray(children).filter(isValidElement);
  return (
    <div className={className}>
      {items.map((child, index) => (
        <Reveal key={index} delay={Math.min(index, max) * step}>
          {child}
        </Reveal>
      ))}
    </div>
  );
}

/**
 * A number that counts up the first time it is seen.
 *
 * `suffix`/`prefix` sit outside the animated value so the unit does not jitter
 * as digits change width. Proportional figures by default - `tabular` is for
 * values that must align down a column.
 */
export function CountUp({
  value,
  decimals = 0,
  prefix,
  suffix,
  className,
  tabular = false,
  duration,
}: {
  value: number;
  decimals?: number;
  prefix?: ReactNode;
  suffix?: ReactNode;
  className?: string;
  tabular?: boolean;
  duration?: number;
}) {
  const { ref, inView } = useInView<HTMLSpanElement>({ threshold: 0.4 });
  const shown = useCountUp(value, { active: inView, decimals, duration });
  return (
    <span ref={ref} className={cn(tabular && "tabular", className)}>
      {prefix}
      {Number.isFinite(shown) ? shown.toFixed(decimals) : "—"}
      {suffix}
    </span>
  );
}
