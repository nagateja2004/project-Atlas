import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// dashboard.test.tsx renders JSX, so the React plugin must be declared rather
// than relying on esbuild picking up tsconfig's jsx setting. Tests render with
// react-dom/server, so no DOM environment is required.
export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": new URL("./src", import.meta.url).pathname } },
  test: {
    environment: "node",
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
