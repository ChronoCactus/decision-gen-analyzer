import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
    // Generated PWA files:
    "public/sw.js",
    "public/workbox-*.js",
    // Node scripts:
    "generate-icons.js",
  ]),
  {
    rules: {
      // Allow explicit any types - to be fixed incrementally
      "@typescript-eslint/no-explicit-any": "off",
    },
  },
]);

export default eslintConfig;
