import type { Config } from "tailwindcss";

/**
 * Design tokens for Project Atlas.
 *
 * The visual language is drafting-room rather than consumer-SaaS: deep navy
 * ground, a single teal signal, hairline rules, and typography that keeps
 * measured values legible in a column. Motion is purposeful - it explains where
 * something came from - and never decorative for its own sake.
 *
 * Two token families are deliberately kept apart:
 *
 *   brand   navy / signal — chrome, emphasis, interactive affordances
 *   data    the `viz` ramp and `status` — encode values only
 *
 * Mixing them would let the accent colour imply a magnitude it does not have,
 * and would leave a chart repainting itself whenever the brand changed.
 */
export default {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#f4f6f9",
        ink: "#172235",
        navy: "#0b1f36",
        // Slightly deeper than navy, for hover on navy surfaces.
        "navy-hi": "#14375f",
        // Deepest step, for the storytelling ground where content sits on navy.
        "navy-deep": "#071528",
        signal: "#1f8a70",
        "signal-soft": "#e7f2ef",
        "signal-hi": "#25a586",
        // Muted body text that still holds contrast on canvas.
        muted: "#5a6879",
        // Hairline rule that reads on both canvas and white.
        hairline: "rgba(11,31,54,.09)",

        /**
         * Sequential ramp for magnitude - one hue, light to dark.
         *
         * Validated with the ordinal gate against a WHITE surface: monotone
         * lightness, adjacent ΔL >= 0.06, single hue (3° spread), light end
         * 2.11:1. It FAILS that last check on the canvas ground (1.95:1), which
         * is why every chart in this app sits on a white card and never
         * directly on the page ground.
         */
        viz: {
          100: "#cde2fb",
          200: "#9ec5f4",
          300: "#86b6ef",
          400: "#5598e7",
          500: "#2a78d6",
          600: "#1c5cab",
          700: "#104281",
        },

        /**
         * Status - fixed, never themed, never reused as a series colour.
         *
         * `warning` and `serious` sit below 3:1 on a light surface by design.
         * The mitigation is that a status is never colour alone: every use in
         * this app pairs it with a text label, which is why Badge takes
         * children rather than rendering a bare chip.
         */
        status: {
          good: "#0ca30c",
          warning: "#fab219",
          serious: "#ec835a",
          critical: "#d03b3b",
        },
      },

      fontFamily: {
        sans: ["var(--font-sans)", "Segoe UI", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "Consolas", "monospace"],
      },

      fontSize: {
        // Uppercase micro-labels used on metric cells and table headers.
        label: ["0.6875rem", { lineHeight: "1rem", letterSpacing: "0.07em" }],
        // Display sizes for the story sections. Negative tracking keeps large
        // text from looking loose; line-height tightens as size grows.
        "display-sm": ["2rem", { lineHeight: "1.15", letterSpacing: "-0.02em" }],
        "display": ["2.75rem", { lineHeight: "1.08", letterSpacing: "-0.025em" }],
        "display-lg": ["3.75rem", { lineHeight: "1.02", letterSpacing: "-0.03em" }],
        // Hero figures on stat tiles. Proportional figures by default; only
        // columns that must align vertically get tabular-nums.
        figure: ["2.5rem", { lineHeight: "1", letterSpacing: "-0.02em" }],
        "figure-lg": ["3.5rem", { lineHeight: "1", letterSpacing: "-0.025em" }],
      },

      boxShadow: {
        card: "0 1px 2px rgba(11,31,54,.05), 0 1px 3px rgba(11,31,54,.04)",
        "card-hover": "0 2px 4px rgba(11,31,54,.06), 0 8px 20px rgba(11,31,54,.07)",
        // Used on the lifted state of an interactive card. Deliberately soft and
        // wide rather than dark - a hard shadow reads as a modal, not a hover.
        lift: "0 4px 8px rgba(11,31,54,.05), 0 16px 40px rgba(11,31,54,.10)",
        drawer: "-12px 0 40px rgba(11,31,54,.18)",
        // Glow for emphasis on the navy ground, where a shadow is invisible.
        "signal-glow": "0 0 0 1px rgba(37,165,134,.35), 0 8px 32px rgba(37,165,134,.18)",
      },

      transitionTimingFunction: {
        // A single decisive ease for entrances: fast out of the gate, long
        // settle. Reads as physical without a spring library.
        settle: "cubic-bezier(.16,.84,.28,1)",
        // Symmetric, for state toggles where neither direction should dominate.
        swap: "cubic-bezier(.4,0,.2,1)",
        // Slight overshoot, reserved for a value landing on a counter.
        land: "cubic-bezier(.34,1.4,.5,1)",
      },

      transitionDuration: {
        crisp: "140ms",
        base: "240ms",
        slow: "420ms",
        story: "700ms",
      },

      keyframes: {
        // Reveal on scroll. Translation is small on purpose: a long slide is
        // the most common way scroll animation turns into motion sickness.
        rise: {
          from: { opacity: "0", transform: "translate3d(0,14px,0)" },
          to: { opacity: "1", transform: "translate3d(0,0,0)" },
        },
        "fade-in": { from: { opacity: "0" }, to: { opacity: "1" } },
        // Drawn connective line in the impact-chain diagram.
        "draw-line": { from: { strokeDashoffset: "1" }, to: { strokeDashoffset: "0" } },
        // Indeterminate progress and skeletons.
        shimmer: { from: { transform: "translateX(-100%)" }, to: { transform: "translateX(100%)" } },
        // A pulse that stays subtle enough to sit behind text.
        "pulse-ring": {
          "0%": { transform: "scale(.92)", opacity: ".55" },
          "70%": { transform: "scale(1.5)", opacity: "0" },
          "100%": { transform: "scale(1.5)", opacity: "0" },
        },
        "slide-in-right": {
          from: { transform: "translate3d(100%,0,0)" },
          to: { transform: "translate3d(0,0,0)" },
        },
        // Marching dashes, for a flow that is actively propagating.
        march: { to: { strokeDashoffset: "-16" } },
      },

      animation: {
        rise: "rise 560ms cubic-bezier(.16,.84,.28,1) both",
        "fade-in": "fade-in 320ms cubic-bezier(.4,0,.2,1) both",
        "draw-line": "draw-line 900ms cubic-bezier(.16,.84,.28,1) both",
        shimmer: "shimmer 1.6s cubic-bezier(.4,0,.2,1) infinite",
        "pulse-ring": "pulse-ring 2.4s cubic-bezier(.16,.84,.28,1) infinite",
        "slide-in-right": "slide-in-right 280ms cubic-bezier(.16,.84,.28,1) both",
        march: "march 1s linear infinite",
      },

      backgroundImage: {
        // Navy ground for story sections, with a single off-centre bloom so the
        // panel does not read as a flat rectangle.
        "navy-bloom":
          "radial-gradient(120% 90% at 15% 0%, #14375f 0%, #0b1f36 45%, #071528 100%)",
        "signal-sheen":
          "linear-gradient(100deg, rgba(37,165,134,0) 0%, rgba(37,165,134,.14) 45%, rgba(37,165,134,0) 100%)",
      },

      maxWidth: { shell: "1600px", prose: "68ch" },
    },
  },
  plugins: [],
} satisfies Config;
