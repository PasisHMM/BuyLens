import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  test: {
    // Component tests opt into a browser with `// @vitest-environment jsdom`.
    include: ["src/**/*.test.{ts,tsx}"],
    coverage: {
      provider: "v8",
      // Every source file counts, so untested files show as 0% instead of disappearing.
      include: ["src/**/*.{ts,tsx}"],
      exclude: ["src/**/*.test.{ts,tsx}", "src/**/*.d.ts"],
      reporter: ["text-summary", "lcov"],
    },
  },
});
