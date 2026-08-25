import path from "node:path";

import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // A stray package-lock.json in a parent directory makes Turbopack infer the
  // wrong workspace root, which can resolve modules from outside the app. Pin it
  // to this directory.
  turbopack: { root: path.resolve(import.meta.dirname ?? ".") },

  // Emit .next/standalone with only the traced runtime dependencies, so the
  // container ships ~150 MB instead of the whole node_modules tree. Vercel
  // ignores this setting, so the existing Vercel deploy is unaffected.
  output: "standalone",
};

export default nextConfig;
