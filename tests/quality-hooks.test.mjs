import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import {
  copyFileSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  symlinkSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { parse } from "yaml";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const tools = [
  {
    id: "lint-js",
    package: "eslint",
    bin: "bin/eslint.js",
    options: ["--max-warnings=0", "--"],
    invalid: "missingName();\n",
  },
  {
    id: "format-check",
    package: "prettier",
    bin: "bin/prettier.cjs",
    options: ["--check", "--"],
    invalid: "console.log('bad')\n",
  },
];
const names = [
  "ordinary.mjs",
  "nested/example.mjs",
  "file with spaces.mjs",
  "meta[ab].mjs",
  "choice{a,b}.mjs",
  "!bang.mjs",
  "--option.mjs",
];
const decoys = ["metaa.mjs", "metab.mjs", "choicea.mjs", "choiceb.mjs"];
const valid = 'console.log("ok");\n';

// A shell-backed npm entry can expand braces before either tool sees argv.
// Keep this wiring assertion alongside actual CLI path/decoy behavior.
test("quality hooks invoke root package binaries directly with selected filenames", () => {
  const config = parse(
    readFileSync(join(root, ".pre-commit-config.yaml"), "utf8"),
  );
  const localHooks = config.repos
    .filter((repo) => repo.repo === "local")
    .flatMap((repo) => repo.hooks);
  for (const tool of tools) {
    const hooks = localHooks.filter((hook) => hook.id === tool.id);
    assert.equal(hooks.length, 1);
    const hook = hooks[0];
    assert.equal(hook.language, "system");
    assert.equal(
      hook.entry,
      `node node_modules/${tool.package}/${tool.bin} ${tool.options.join(" ")}`,
    );
    assert.notEqual(hook.always_run, true);
    assert.notEqual(hook.pass_filenames, false);
    const manifest = JSON.parse(
      readFileSync(join(root, "node_modules", tool.package, "package.json")),
    );
    const declared =
      typeof manifest.bin === "string"
        ? manifest.bin
        : manifest.bin[tool.package];
    assert.equal(declared.replace(/^\.\//, ""), tool.bin);
    const extensions =
      tool.id === "lint-js"
        ? ["js", "cjs", "mjs"]
        : ["js", "cjs", "mjs", "json", "jsonc", "yaml", "yml", "md"];
    for (const extension of extensions)
      assert.match(`example.${extension}`, new RegExp(hook.files));
    for (const extension of [
      "html",
      "css",
      "py",
      "toml",
      "txt",
      ...(tool.id === "lint-js" ? ["json", "jsonc", "yaml", "yml", "md"] : []),
    ]) {
      assert.doesNotMatch(`example.${extension}`, new RegExp(hook.files));
    }
    if (tool.id === "format-check") {
      for (const name of [
        "package-lock.json",
        "tests/link-validation/contract.json",
        "tests/fixtures/yaml-stream.yaml",
      ]) {
        assert.match(name, new RegExp(hook.exclude));
      }
      for (const name of [
        "README.md",
        "tools/example.mjs",
        ".prettierrc.json",
      ]) {
        assert.doesNotMatch(name, new RegExp(hook.exclude));
      }
    }
  }
});

for (const tool of tools) {
  test(`${tool.package} checks literal filenames and rejects invalid batches without selecting decoys`, (t) => {
    const dir = mkdtempSync(join(tmpdir(), "quality-filenames-"));
    t.after(() => rmSync(dir, { recursive: true, force: true }));
    for (const name of [
      "eslint.config.mjs",
      ".prettierrc.json",
      ".prettierignore",
    ]) {
      copyFileSync(join(root, name), join(dir, name));
    }
    // The copied ESLint config imports @eslint/js from the same installed graph.
    symlinkSync(
      join(root, "node_modules"),
      join(dir, "node_modules"),
      "junction",
    );
    for (const name of names) {
      mkdirSync(dirname(join(dir, name)), { recursive: true });
      writeFileSync(join(dir, name), valid);
    }
    function check(selected, expected) {
      const result = spawnSync(
        process.execPath,
        [
          join(root, "node_modules", tool.package, tool.bin),
          ...tool.options,
          ...selected,
        ],
        { cwd: dir, encoding: "utf8", timeout: 30000 },
      );
      assert.ifError(result.error);
      assert.equal(result.signal, null);
      const output = result.stdout + result.stderr;
      assert.equal(result.status, expected, output);
      for (const decoy of decoys) assert.ok(!output.includes(decoy), output);
      return output;
    }
    for (const name of names) {
      // Invalid unselected siblings must not make a valid literal path fail.
      for (const decoy of decoys) writeFileSync(join(dir, decoy), tool.invalid);
      check([name], 0);
      // Valid decoys must not hide an invalid selected filename.
      for (const decoy of decoys) writeFileSync(join(dir, decoy), valid);
      writeFileSync(join(dir, name), tool.invalid);
      assert.ok(check([name], 1).includes(name));
      assert.equal(readFileSync(join(dir, name), "utf8"), tool.invalid);
      writeFileSync(join(dir, name), valid);
    }
    for (const decoy of decoys) writeFileSync(join(dir, decoy), tool.invalid);
    check(names, 0);
    for (const decoy of decoys) writeFileSync(join(dir, decoy), valid);
    writeFileSync(join(dir, "choice{a,b}.mjs"), tool.invalid);
    for (const selected of [names, [...names].reverse()]) {
      assert.ok(check(selected, 1).includes("choice{a,b}.mjs"));
    }
  });
}
