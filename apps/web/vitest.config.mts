import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  test: {
    include: ["src/**/*.test.ts"],
    coverage: {
      provider: "v8",
      // Every source file counts, so untested files show as 0% instead of disappearing.
      include: ["src/**/*.{ts,tsx}"],
      exclude: ["src/**/*.test.ts", "src/**/*.d.ts"],
      reporter: ["text-summary", "lcov"],
    },
  },
});
