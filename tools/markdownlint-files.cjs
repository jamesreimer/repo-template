"use strict";

const { readFileSync } = require("node:fs");
const { join, resolve } = require("node:path");
const { pathToFileURL } = require("node:url");

// pre-commit sets NODE_PATH to the pinned hook's node_modules on every platform.
// Resolve there explicitly so a checkout's node_modules cannot shadow the hook.
if (!process.env.NODE_PATH) {
  throw new Error("Run markdownlint-files through the pre-commit Node hook.");
}
const cliRoot = join(process.env.NODE_PATH, "markdownlint-cli2");
const pkg = JSON.parse(readFileSync(join(cliRoot, "package.json"), "utf8"));
const cli = resolve(cliRoot, pkg.bin["markdownlint-cli2"]);

// ':' is the CLI's literal-file marker; '--' only stops option recognition.
// Run its declared executable in this process, preserving streams and signals.
process.argv = [
  process.execPath,
  cli,
  ...process.argv.slice(2).map((file) => `:${file}`),
];
import(pathToFileURL(cli).href).catch((error) => {
  console.error(error);
  process.exitCode = 2;
});
