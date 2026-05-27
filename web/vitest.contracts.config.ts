import { defineConfig } from "vitest/config";
import baseConfig from "./vitest.config";

export default defineConfig({
  ...baseConfig,
  test: {
    ...baseConfig.test,
    exclude: ["node_modules/**"],
    include: [
      "config.test.mts",
      "promptc-api.test.mts",
      "lib/server/backendProxy.test.ts",
      "app/proxy-routes.test.ts",
    ],
  },
});
