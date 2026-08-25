"use client";

/**
 * Motion primitives, built on IntersectionObserver and requestAnimationFrame.
 *
 * No animation library. Everything here is a few lines of platform API, and a
 * dependency would cost more than it returns: the app ships to a 1 GB instance,
 * and this project has already been bitten twice by a lockfile that could not be
 * installed where it mattered.
 *
 * Every hook honours `prefers-reduced-motion`, and it does so by DERIVING the
 * reduced result during render rather than assigning it from an effect. That is
 * not a style preference: `react-hooks/set-state-in-effect` rejects the effect
 * form, and the derived form is genuinely better - the first painted frame is
 * already correct, so a reader who has asked for no motion never sees the
 * pre-animation state flash before an effect corrects it.
 *
 * Reduced motion lands on the FINAL state immediately. It does not animate
 * faster. globals.css collapses CSS durations globally, which covers CSS-only
 * motion; these hooks cover the JS-driven kind, where a collapsed duration would
 * otherwise leave an element stranded at its start value.
 */

import { useEffect, useRef, useState, useSyncExternalStore } from "react";

const REDUCED_QUERY = "(prefers-reduced-motion: reduce)";

function subscribeReduced(onChange: () => void): () => void {
  if (typeof window === "undefined" || !window.matchMedia) return () => {};
  try {
    const query = window.matchMedia(REDUCED_QUERY);
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  } catch {
    return () => {};
  }
}

function readReduced(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return false;
  try {
    return window.matchMedia(REDUCED_QUERY).matches;
  } catch {
    return false;
  }
}

/**
 * Whether the reader has asked for reduced motion, read during render.
 *
 * useSyncExternalStore is the right tool for a browser value that can change
 * underneath React: it gives a consistent snapshot per render, resubscribes
 * correctly, and takes an explicit server snapshot instead of guessing. The
 * server snapshot is `false` so the markup matches a first client render on a
 * machine with no preference set; a machine that does have it set corrects on
 * hydration, which is a class change and not a layout change.
 */
export function useReducedMotion(): boolean {
  return useSyncExternalStore(subscribeReduced, readReduced, () => false);
}

/**
 * True once the element has scrolled into view.
 *
 * Latches by default: an element that has been revealed stays revealed. Content
 * that re-hides and re-animates every time it leaves the viewport is the most
 * irritating form of scroll animation, and it makes the page feel unstable when
 * a reader scrolls back to re-read something.
 */
export function useInView<T extends Element = HTMLDivElement>(options?: {
  /** Fraction of the element that must be visible. */
  threshold?: number;
  /** Shrink the viewport so the reveal fires slightly before the true edge. */
  rootMargin?: string;
  /** Set false to let the element hide again when it leaves. */
  once?: boolean;
}) {
  const { threshold = 0.15, rootMargin = "0px 0px -8% 0px", once = true } = options ?? {};
  const reduced = useReducedMotion();
  const ref = useRef<T | null>(null);
  const [seen, setSeen] = useState(false);

  useEffect(() => {
    // Nothing to observe: the returned value is already true.
    if (reduced) return;

    const node = ref.current;
    if (!node) return;

    if (typeof IntersectionObserver === "undefined") {
      // No observer (an old browser, or a test environment). Show the content -
      // failing open matters far more than the animation. Deferred a frame so
      // this is a genuine post-paint update rather than a render-phase write.
      const id = requestAnimationFrame(() => setSeen(true));
      return () => cancelAnimationFrame(id);
    }

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setSeen(true);
            if (once) observer.disconnect();
          } else if (!once) {
            setSeen(false);
          }
        }
      },
      { threshold, rootMargin },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [reduced, threshold, rootMargin, once]);

  return { ref, inView: reduced || seen } as const;
}

/**
 * Count from zero to `value` once `active` is true.
 *
 * Driven by elapsed time rather than a per-frame increment, so the duration is
 * the same on a 60 Hz and a 144 Hz display and a dropped frame does not shorten
 * the count. Eased out, because a counter running at constant speed and then
 * stopping dead reads as a glitch.
 */
export function useCountUp(
  value: number,
  { active = true, duration = 900, decimals = 0 }: { active?: boolean; duration?: number; decimals?: number } = {},
) {
  const reduced = useReducedMotion();
  const [animated, setAnimated] = useState(0);
  const frame = useRef<number | null>(null);

  useEffect(() => {
    if (!active || reduced || typeof requestAnimationFrame === "undefined") return;

    const start = performance.now();
    const factor = 10 ** decimals;

    const step = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      // easeOutCubic: quick to most of the value, then settles.
      const eased = 1 - (1 - t) ** 3;
      setAnimated(Math.round(value * eased * factor) / factor);
      if (t < 1) frame.current = requestAnimationFrame(step);
    };

    frame.current = requestAnimationFrame(step);
    return () => {
      if (frame.current !== null) cancelAnimationFrame(frame.current);
    };
  }, [value, active, duration, decimals, reduced]);

  // Derived rather than assigned: an inactive or reduced-motion counter shows
  // its final value on the first painted frame.
  return !active || reduced ? value : animated;
}

/**
 * Normalised scroll progress (0 to 1) of an element through the viewport.
 *
 * Used where a value must track the scrollbar exactly - a reveal that fires once
 * cannot do that. Reads layout inside a rAF callback so a fast scroll coalesces
 * into one measurement per frame instead of one per scroll event.
 */
export function useScrollProgress<T extends Element = HTMLDivElement>() {
  const reduced = useReducedMotion();
  const ref = useRef<T | null>(null);
  const [measured, setMeasured] = useState(0);

  useEffect(() => {
    if (reduced) return;
    const node = ref.current;
    if (!node) return;

    let queued = false;

    const measure = () => {
      queued = false;
      const rect = node.getBoundingClientRect();
      const viewport = window.innerHeight || 1;
      // 0 when the element's top reaches the bottom of the viewport, 1 when its
      // bottom passes the top.
      const total = rect.height + viewport;
      const travelled = viewport - rect.top;
      setMeasured(Math.min(1, Math.max(0, travelled / total)));
    };

    const onScroll = () => {
      if (queued) return;
      queued = true;
      requestAnimationFrame(measure);
    };

    // The first measurement is deferred to the next frame too, so layout is
    // settled and nothing is written during the effect itself.
    const first = requestAnimationFrame(measure);
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll, { passive: true });
    return () => {
      cancelAnimationFrame(first);
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
    };
  }, [reduced]);

  return { ref, progress: reduced ? 1 : measured } as const;
}

/**
 * Pointer position within an element, in the -1..1 range, for a magnetic hover.
 *
 * Returns null while the pointer is away so the caller drops back to rest rather
 * than sticking at the last offset. Skipped for reduced motion and on touch,
 * where there is no hover to track and the effect would only fire on tap.
 */
export function usePointerParallax<T extends HTMLElement = HTMLDivElement>(strength = 6) {
  const reduced = useReducedMotion();
  const ref = useRef<T | null>(null);
  const [offset, setOffset] = useState<{ x: number; y: number } | null>(null);

  useEffect(() => {
    if (reduced) return;
    const node = ref.current;
    if (!node) return;
    if (typeof window !== "undefined" && window.matchMedia) {
      try {
        if (!window.matchMedia("(hover: hover) and (pointer: fine)").matches) return;
      } catch {
        return;
      }
    }

    const onMove = (event: PointerEvent) => {
      const rect = node.getBoundingClientRect();
      const x = ((event.clientX - rect.left) / rect.width - 0.5) * 2;
      const y = ((event.clientY - rect.top) / rect.height - 0.5) * 2;
      setOffset({ x: x * strength, y: y * strength });
    };
    const onLeave = () => setOffset(null);

    node.addEventListener("pointermove", onMove);
    node.addEventListener("pointerleave", onLeave);
    return () => {
      node.removeEventListener("pointermove", onMove);
      node.removeEventListener("pointerleave", onLeave);
    };
  }, [strength, reduced]);

  return { ref, offset: reduced ? null : offset } as const;
}

/** Formats a number for display without dragging in Intl on every render. */
export function formatCompact(value: number, decimals = 0): string {
  if (!Number.isFinite(value)) return "—";
  if (Math.abs(value) >= 1000) return `${(value / 1000).toFixed(1)}k`;
  return value.toFixed(decimals);
}
