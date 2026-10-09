"use strict";

const assert = require("node:assert/strict");
const { spawnSync } = require("node:child_process");
const {
  copyFileSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  realpathSync,
  rmSync,
  writeFileSync,
} = require("node:fs");
const { createRequire } = require("node:module");
const { tmpdir } = require("node:os");
const { dirname, resolve, join } = require("node:path");
const { test } = require("node:test");

// Exercise the real CLI, parser, and configuration from the same root npm
// installation as the ordinary hook, independent of the caller's cwd.
const root = resolve(__dirname, "..");
const rootRequire = createRequire(join(root, "package.json"));
const cliManifest = rootRequire.resolve(
  "./node_modules/markdownlint-cli2/package.json",
);
const cliRoot = dirname(cliManifest);
const cliPackage = JSON.parse(readFileSync(cliManifest, "utf8"));
const cli = resolve(cliRoot, cliPackage.bin["markdownlint-cli2"]);
const cliRequire = createRequire(cliManifest);
const yamlParser = cliRequire.resolve("markdownlint-cli2/parsers/yaml");

const configPath = join(root, ".markdownlint-cli2.jsonc");
const cases = [
  [
    "literal fence in raw pre block",
    "# Title\n\n<pre>\n\n```sh\nliteral\n</pre>\n",
    [],
  ],
  [
    "fence after HTML flow ends",
    "# Title\n\n<details>\n<summary>Example</summary>\n\n```sh\ncode\n",
    [6],
  ],
  [
    "balanced literal fence in tight HTML",
    "# Title\n\n<details>\n```sh\ncode\n```\n</details>\n",
    [],
  ],
  ["closed backticks", "# Title\n\n```sh\necho ok\n```\n", []],
  ["closed tildes", "# Title\n\n~~~sh\necho ok\n~~~\n", []],
  ["longer closing fence", "# Title\n\n```sh\necho ok\n`````\n", []],
  [
    "embedded closed example",
    "# Title\n\n````markdown\n```sh\necho ok\n```\n````\n",
    [],
  ],
  [
    "embedded unclosed example",
    "# Title\n\n````markdown\n```sh\necho ok\n````\n",
    [],
  ],
  ["closed blockquote", "# Title\n\n> ```sh\n> echo ok\n> ```\n", []],
  ["closed list", "# Title\n\n- Item\n\n  ```sh\n  echo ok\n  ```\n", []],
  [
    "inline and indented code",
    "# Title\n\nInline `code` and ``a ` b``.\n\n    ```\n",
    [],
  ],
  ["missing closer", "# Title\n\n```sh\necho ok\n", [3]],
  [
    "short inner closer cannot close outer",
    "# Title\n\n````markdown\n```sh\necho ok\n```\n",
    [3],
  ],
  ["mixed markers do not close", "# Title\n\n```sh\necho ok\n~~~\n", [3]],
  ["unclosed blockquote", "# Title\n\n> ```sh\n> echo ok\n\nOutside.\n", [3]],
  [
    "unclosed list",
    "# Title\n\n- Item\n\n  ```sh\n  echo ok\n\nOutside.\n",
    [5],
  ],
  ["second block unclosed", "# Title\n\n```sh\nok\n```\n\n```sh\nmore\n", [7]],
  [
    "absorbed links",
    "# Title\n\n```sh\n[missing](absent.md)\n[fragment](#absent)\n",
    [3],
  ],
  [
    "front matter line offset",
    "---\ntitle: Example\n---\n\n# Title\n\n```sh\ncode\n",
    [7],
  ],
];

function lint(t, content, { fix = false } = {}) {
  const dir = mkdtempSync(join(tmpdir(), "markdown-rule-"));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  const file = join(dir, "example.md");
  writeFileSync(file, content);
  const args = [cli, "--config", configPath, ...(fix ? ["--fix"] : []), file];
  const result = spawnSync(process.execPath, args, {
    cwd: root,
    encoding: "utf8",
    timeout: 30000,
  });
  const output = result.stdout + result.stderr;
  assert.equal(result.error, undefined, output);
  assert.equal(result.signal, null, output);
  return { ...result, output, file };
}

for (const [name, content, expectedLines] of cases) {
  test(name, (t) => {
    const result = lint(t, content);
    assert.equal(result.status, expectedLines.length ? 1 : 0, result.output);
    const actualLines = [
      ...result.output.matchAll(/example\.md:(\d+)(?::\d+)? error MDX001\//g),
    ].map((match) => Number(match[1]));
    assert.deepEqual(actualLines, expectedLines, result.output);
    assert.equal(readFileSync(result.file, "utf8"), content);
  });
}

test("fix mode reports but does not invent a closing position", (t) => {
  const content = "# Title\n\n```sh\necho ok\n\nPossibly intended prose.\n";
  const result = lint(t, content, { fix: true });
  assert.equal(result.status, 1, result.output);
  assert.match(result.output, /example\.md:3.*error MDX001\//);
  assert.equal(readFileSync(result.file, "utf8"), content);
});

// Exercise the filename boundary with the actual configuration and CLI, including
// paths that glob interpretation would silently omit or expand to other files.
test("ordinary Markdown hook uses the literal-filename adapter", () => {
  const parseYaml = cliRequire("markdownlint-cli2/parsers/yaml").default;
  const config = parseYaml(
    readFileSync(join(root, ".pre-commit-config.yaml"), "utf8"),
  );
  const ordinaryHooks = config.repos
    .filter((repo) => repo.repo === "local")
    .flatMap((repo) => repo.hooks)
    .filter((hook) => hook.id === "markdownlint-cli2");
  assert.equal(
    ordinaryHooks.length,
    1,
    "Expected exactly one ordinary Markdown hook",
  );
  assert.equal(ordinaryHooks[0].entry, "node tools/markdownlint-files.cjs");
  assert.equal(ordinaryHooks[0].language, "system");
  assert.deepEqual(ordinaryHooks[0].types, ["markdown"]);
  assert.notEqual(ordinaryHooks[0].always_run, true);
  assert.notEqual(ordinaryHooks[0].pass_filenames, false);
  const testHooks = config.repos
    .filter((repo) => repo.repo === "local")
    .flatMap((repo) => repo.hooks)
    .filter((hook) => hook.id === "test-markdown-rules");
  assert.equal(
    testHooks.length,
    1,
    "Expected exactly one Markdown-rule test hook",
  );
  assert.equal(testHooks[0].language, "system");
  assert.equal(testHooks[0].entry, "node --test tests/markdown-rules.test.cjs");
  assert.deepEqual(testHooks[0].types, ["file"]);
  assert.equal(testHooks[0].always_run, true);
  assert.equal(testHooks[0].pass_filenames, false);
  assert.ok(
    !config.repos.some(
      (repo) => repo.repo === "https://github.com/DavidAnson/markdownlint-cli2",
    ),
  );
});

const literalNames = [
  "ordinary.md",
  "nested/deeper/new.md",
  "meta[ab].md",
  "choice{a,b}.md",
  `deep${"{".repeat(48)}a,b${"}".repeat(48)}.md`,
  "file with spaces.md",
  "plus+(a).md",
  "#hash.md",
  "!bang.md",
  // Windows filesystems reject colon and star in these filename positions.
  ...(process.platform === "win32" ? [] : [":literal-name.md", "star*.md"]),
];

function literalFixture(t) {
  const dir = mkdtempSync(join(tmpdir(), "markdown-path-"));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  copyFileSync(configPath, join(dir, ".markdownlint-cli2.jsonc"));
  mkdirSync(join(dir, "markdownlint-rules"));
  copyFileSync(
    join(root, "markdownlint-rules/fenced-code-closed.cjs"),
    join(dir, "markdownlint-rules/fenced-code-closed.cjs"),
  );
  return dir;
}

function lintLiteral(dir, names) {
  const result = spawnSync(
    process.execPath,
    [join(root, "tools/markdownlint-files.cjs"), ...names],
    { cwd: dir, encoding: "utf8", timeout: 30000 },
  );
  const output = result.stdout + result.stderr;
  assert.equal(result.error, undefined, output);
  assert.equal(result.signal, null, output);
  return { ...result, output };
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
      if (!valid)
        assert.ok(
          result.stderr.includes(`${name}:1:1 error MD018/`),
          result.output,
        );
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
  assert.ok(
    valid.stdout.includes(`Linting: ${literalNames.length} files\n`),
    valid.output,
  );
  writeFileSync(join(dir, "choice{a,b}.md"), "#Title\n");
  for (const names of [literalNames, [...literalNames].reverse()]) {
    const result = lintLiteral(dir, names);
    assert.equal(result.status, 1, result.output);
    assert.ok(
      result.stdout.includes(`Linting: ${names.length} files\n`),
      result.output,
    );
    for (const name of names)
      assert.ok(result.stdout.includes(`:${name}`), result.output);
    assert.ok(
      result.stderr.includes("choice{a,b}.md:1:1 error MD018/"),
      result.output,
    );
    assert.ok(!result.stderr.includes("choicea.md"), result.output);
  }
});

test("Markdown CLI and YAML parser belong to the root npm package", () => {
  const expectedRoot = realpathSync(
    join(root, "node_modules/markdownlint-cli2"),
  );
  assert.equal(realpathSync(cliManifest), join(expectedRoot, "package.json"));
  assert.equal(
    realpathSync(cli),
    resolve(expectedRoot, cliPackage.bin["markdownlint-cli2"]),
  );
  assert.equal(
    realpathSync(yamlParser),
    resolve(expectedRoot, cliPackage.exports["./parsers/yaml"]),
  );
});

test("adapter fails closed when the root npm package is missing", (t) => {
  const dir = mkdtempSync(join(tmpdir(), "markdown-missing-install-"));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  mkdirSync(join(dir, "tools"));
  writeFileSync(join(dir, "package.json"), "{}\n");
  copyFileSync(
    join(root, "tools/markdownlint-files.cjs"),
    join(dir, "tools/markdownlint-files.cjs"),
  );
  const result = spawnSync(
    process.execPath,
    [join(dir, "tools/markdownlint-files.cjs"), "example.md"],
    { cwd: root, encoding: "utf8", timeout: 30000 },
  );
  const output = result.stdout + result.stderr;
  assert.equal(result.error, undefined, output);
  assert.equal(result.signal, null, output);
  assert.notEqual(result.status, 0);
  assert.match(
    result.stderr,
    /Run npm ci --ignore-scripts before repository validation\./,
  );
});
