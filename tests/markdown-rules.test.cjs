"use strict";

const assert = require("node:assert/strict");
const { spawnSync } = require("node:child_process");
const { copyFileSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } = require("node:fs");
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

// Exercise the filename boundary with the actual configuration and CLI, including
// paths that glob interpretation would silently omit or expand to other files.
const literalNames = [
  "ordinary.md",
  "nested/deeper/new.md",
  "meta[ab].md",
  "choice{a,b}.md",
  `deep${"{".repeat(48)}a,b${"}".repeat(48)}.md`,
  "file with spaces.md",
  "plus+(a).md",
  // Windows filesystems reject colon and star in these filename positions.
  ...(process.platform === "win32" ? [] : [":literal-name.md", "star*.md"])
];

function literalFixture(t) {
  const dir = mkdtempSync(join(tmpdir(), "markdown-path-"));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  copyFileSync(configPath, join(dir, ".markdownlint-cli2.jsonc"));
  mkdirSync(join(dir, "markdownlint-rules"));
  copyFileSync(join(root, "markdownlint-rules/fenced-code-closed.cjs"),
    join(dir, "markdownlint-rules/fenced-code-closed.cjs"));
  return dir;
}

function lintLiteral(dir, names) {
  const result = spawnSync(process.execPath,
    [join(root, "tools/markdownlint-files.cjs"), ...names],
    { cwd: dir, encoding: "utf8", timeout: 30000,
      env: { ...process.env, NODE_PATH: process.env.NODE_PATH || dirname(cliRoot) } });
  assert.ifError(result.error);
  assert.equal(result.signal, null);
  return { ...result, output: result.stdout + result.stderr };
}

for (const name of literalNames) {
  test(`literal Markdown path: ${name}`, (t) => {
    const dir = literalFixture(t);
    mkdirSync(dirname(join(dir, name)), { recursive: true });
    for (const valid of [true, false]) {
      const content = valid ? "# Title\n" : "#Title\n";
      writeFileSync(join(dir, name), content);
      const result = lintLiteral(dir, [name]);
      assert.equal(result.status, valid ? 0 : 1, result.output);
      assert.match(result.stdout, /Linting: 1 file\n/);
      assert.ok(result.stdout.includes(`Finding: :${name}\n`), result.output);
      if (!valid) assert.ok(result.stderr.includes(`${name}:1:1 error MD018/`), result.output);
      assert.equal(readFileSync(join(dir, name), "utf8"), content);
    }
  });
}

test("literal Markdown batch preserves every path and rejects one invalid sibling", (t) => {
  const dir = literalFixture(t);
  for (const name of literalNames) {
    mkdirSync(dirname(join(dir, name)), { recursive: true });
    writeFileSync(join(dir, name), "# Title\n");
  }
  // A glob would select this invalid decoy when passed choice{a,b}.md.
  writeFileSync(join(dir, "choicea.md"), "#Decoy\n");
  const valid = lintLiteral(dir, literalNames);
  assert.equal(valid.status, 0, valid.output);
  assert.ok(valid.stdout.includes(`Linting: ${literalNames.length} files\n`), valid.output);
  writeFileSync(join(dir, "choice{a,b}.md"), "#Title\n");
  for (const names of [literalNames, [...literalNames].reverse()]) {
    const result = lintLiteral(dir, names);
    assert.equal(result.status, 1, result.output);
    assert.ok(result.stdout.includes(`Linting: ${names.length} files\n`), result.output);
    for (const name of names) assert.ok(result.stdout.includes(`:${name}`), result.output);
    assert.ok(result.stderr.includes("choice{a,b}.md:1:1 error MD018/"), result.output);
    assert.ok(!result.stderr.includes("choicea.md"), result.output);
  }
});
