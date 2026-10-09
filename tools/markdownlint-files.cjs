"use strict";

const { readFileSync } = require("node:fs");
const { createRequire } = require("node:module");
const { dirname, join, resolve } = require("node:path");
const { pathToFileURL } = require("node:url");

// Anchor resolution to this repository, even when invoked from a fixture cwd.
// The explicit local path prevents fallback to ancestor or global installations.
const rootRequire = createRequire(join(__dirname, "..", "package.json"));
let cli;
try {
  const manifest = rootRequire.resolve(
    "./node_modules/markdownlint-cli2/package.json",
  );
  const pkg = JSON.parse(readFileSync(manifest, "utf8"));
  cli = resolve(dirname(manifest), pkg.bin["markdownlint-cli2"]);
} catch (error) {
  throw new Error("Run npm ci --ignore-scripts before repository validation.", {
    cause: error,
  });
}

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
