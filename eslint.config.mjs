import { defineConfig } from "eslint/config";
import js from "@eslint/js";

export default defineConfig([
  { ignores: [".venv/**"] },
  {
    files: ["**/*.{js,mjs,cjs}"],
    extends: [js.configs.recommended],
    languageOptions: {
      globals: { process: "readonly", console: "readonly", URL: "readonly" },
    },
    rules: { eqeqeq: ["error", "always"], "prefer-const": "error" },
  },
  {
    files: ["**/*.{js,cjs}"],
    languageOptions: {
      sourceType: "commonjs",
      globals: { __dirname: "readonly", __filename: "readonly" },
    },
  },
]);
