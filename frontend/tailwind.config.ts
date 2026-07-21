import type { Config } from "tailwindcss";

export default {
  content: ["./src/**/*.{ts,tsx}"],
  theme: { extend: { colors: { canvas: "#f5f7fa", ink: "#172235", navy: "#0b1f36", signal: "#1f8a70" } } },
  plugins: [],
} satisfies Config;
