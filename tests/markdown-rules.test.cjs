"use strict";

const assert = require("node:assert/strict");
const { spawnSync } = require("node:child_process");
const { mkdtempSync, readFileSync, rmSync, writeFileSync } = require("node:fs");
const { tmpdir } = require("node:os");
const { dirname, resolve, join } = require("node:path");
const { test } = require("node:test");

// Run the installed CLI from the hook environment, using the real parser and the
// repository's actual configuration. No copied parser or synthetic tokens.
// pre-commit sets NODE_PATH to its isolated Node environment. Resolve the
// package's declared binary and use Node directly, avoiding platform shell shims.
const cliRoot = dirname(require.resolve("markdownlint-cli2"));
const cliPackage = JSON.parse(readFileSync(join(cliRoot, "package.json"), "utf8"));
const cli = resolve(cliRoot, cliPackage.bin["markdownlint-cli2"]);
const root = resolve(__dirname, "..");
const configPath = join(root, ".markdownlint-cli2.jsonc");
const cases = [
  ["literal fence in raw pre block", "# Title\n\n<pre>\n\n```sh\nliteral\n</pre>\n", []],
  ["fence after HTML flow ends", "# Title\n\n<details>\n<summary>Example</summary>\n\n```sh\ncode\n", [6]],
  ["balanced literal fence in tight HTML", "# Title\n\n<details>\n```sh\ncode\n```\n</details>\n", []],
  ["closed backticks", "# Title\n\n```sh\necho ok\n```\n", []],
  ["closed tildes", "# Title\n\n~~~sh\necho ok\n~~~\n", []],
  ["longer closing fence", "# Title\n\n```sh\necho ok\n`````\n", []],
  ["embedded closed example", "# Title\n\n````markdown\n```sh\necho ok\n```\n````\n", []],
  ["embedded unclosed example", "# Title\n\n````markdown\n```sh\necho ok\n````\n", []],
  ["closed blockquote", "# Title\n\n> ```sh\n> echo ok\n> ```\n", []],
  ["closed list", "# Title\n\n- Item\n\n  ```sh\n  echo ok\n  ```\n", []],
  ["inline and indented code", "# Title\n\nInline `code` and ``a ` b``.\n\n    ```\n", []],
  ["missing closer", "# Title\n\n```sh\necho ok\n", [3]],
  ["short inner closer cannot close outer", "# Title\n\n````markdown\n```sh\necho ok\n```\n", [3]],
  ["mixed markers do not close", "# Title\n\n```sh\necho ok\n~~~\n", [3]],
  ["unclosed blockquote", "# Title\n\n> ```sh\n> echo ok\n\nOutside.\n", [3]],
  ["unclosed list", "# Title\n\n- Item\n\n  ```sh\n  echo ok\n\nOutside.\n", [5]],
  ["second block unclosed", "# Title\n\n```sh\nok\n```\n\n```sh\nmore\n", [7]],
  ["absorbed links", "# Title\n\n```sh\n[missing](absent.md)\n[fragment](#absent)\n", [3]],
  ["front matter line offset", "---\ntitle: Example\n---\n\n# Title\n\n```sh\ncode\n", [7]]
];

function lint(t, content, fix = false) {
  const dir = mkdtempSync(join(tmpdir(), "markdown-rule-"));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  const file = join(dir, "example.md");
  writeFileSync(file, content);
  const args = [cli, "--config", configPath, ...(fix ? ["--fix"] : []), file];
  const result = spawnSync(process.execPath, args, { cwd: root, encoding: "utf8" });
  assert.ifError(result.error);
  assert.equal(result.signal, null);
  return { ...result, output: result.stdout + result.stderr, file };
}

for (const [name, content, expectedLines] of cases) {
  test(name, (t) => {
    const result = lint(t, content);
    assert.equal(result.status, expectedLines.length ? 1 : 0, result.output);
    const actualLines = [...result.output.matchAll(/example\.md:(\d+)(?::\d+)? error MDX001\//g)]
      .map((match) => Number(match[1]));
    assert.deepEqual(actualLines, expectedLines, result.output);
    assert.equal(readFileSync(result.file, "utf8"), content);
  });
}

test("fix mode reports but does not invent a closing position", (t) => {
  const content = "# Title\n\n```sh\necho ok\n\nPossibly intended prose.\n";
  const result = lint(t, content, true);
  assert.equal(result.status, 1, result.output);
  assert.match(result.output, /example\.md:3.*error MDX001\//);
  assert.equal(readFileSync(result.file, "utf8"), content);
});
