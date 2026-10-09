import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import {
  mkdtempSync,
  mkdirSync,
  readFileSync,
  writeFileSync,
  rmSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve, posix, win32 } from "node:path";
import {
  repositoryIdentity,
  pageIdentity,
} from "../tools/requested-file-identity.mjs";
import { fileURLToPath, pathToFileURL } from "node:url";
import { createHash } from "node:crypto";
import { test } from "node:test";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const cli = join(root, "tools/check-links.mjs");
const control = pathToFileURL(
  join(root, "tests/link-validation/import-control.mjs"),
).href;
const contractBytes = readFileSync(
  join(root, "tests/link-validation/contract.json"),
);
assert.equal(
  createHash("sha256").update(contractBytes).digest("hex"),
  "ce3927d1a459025450ac75560686412bb803e97e3be1e9300ce57c7478305e33",
);
const contract = JSON.parse(contractBytes);
const lintPackage = JSON.parse(
  readFileSync(join(root, "node_modules/markdownlint-cli2/package.json")),
);
const lint = join(
  root,
  "node_modules/markdownlint-cli2",
  lintPackage.bin["markdownlint-cli2"],
);
function createFixture(t, files) {
  const dir = mkdtempSync(join(tmpdir(), "link-regression-"));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  for (const [name, content] of Object.entries(files)) {
    mkdirSync(dirname(join(dir, name)), { recursive: true });
    writeFileSync(join(dir, name), content);
  }
  return dir;
}
function runNode(dir, args, env = process.env) {
  const result = spawnSync(process.execPath, args, {
    cwd: dir,
    encoding: "utf8",
    timeout: 30000,
    env,
  });
  const output = result.stdout + result.stderr;
  assert.equal(result.error, undefined, output);
  assert.equal(result.signal, null, output);
  return { ...result, output };
}
function checkLinks(dir, paths, mode) {
  return runNode(dir, [...(mode ? ["--import", control] : []), cli, ...paths], {
    ...process.env,
    LINK_TEST_CONTROL: mode || "",
  });
}
for (const contractCase of contract.cases) {
  test(`Link contract: ${contractCase.name}`, (t) => {
    const dir = createFixture(t, contractCase.files);
    const originalContents = new Map(
      Object.keys(contractCase.files).map((file) => [
        file,
        readFileSync(join(dir, file)),
      ]),
    );
    const result = checkLinks(dir, contractCase.inputs);
    // Local acceptance is checked independently of external URLs, which are skipped.
    assert.equal(
      result.status,
      contractCase.expected_local ? 0 : 1,
      result.output,
    );
    const report = JSON.parse(result.stdout);
    for (const link of report.result.links.filter((link) =>
      /^https?:/.test(link.url),
    )) {
      assert.equal(link.state, "SKIPPED", JSON.stringify(link));
    }
    if (
      contractCase.name.startsWith("yaml-") ||
      contractCase.name === "cross-malformed-metadata"
    ) {
      assert.ok(report.yamlErrors.length, result.stdout);
    }
    const authoring = runNode(dir, [
      lint,
      "--config",
      join(root, ".markdownlint-cli2.jsonc"),
      ...contractCase.inputs,
    ]);
    assert.equal(
      authoring.status,
      contractCase.expected_lint ? 0 : 1,
      authoring.output,
    );
    if (contractCase.owner === "markdownlint")
      assert.match(authoring.stderr, /error MDX001\//);
    if (contractCase.name === "dual-name-same") {
      assert.equal(result.status, 0);
    }
    for (const [file, originalContent] of originalContents) {
      assert.deepEqual(readFileSync(join(dir, file)), originalContent);
    }
  });
}
const phantom =
  "---\nprobe: phantom\n---\n\n# Body\n\n[metadata](#probe-phantom)\n";
test("single-key phantom: effective hook rejects metadata destination", (t) => {
  const dir = createFixture(t, { "source.md": phantom });
  const result = checkLinks(dir, ["source.md"]);
  assert.equal(result.status, 1, result.stderr);
  const phantomLink = JSON.parse(result.stdout).result.links.find(
    (link) => link.url === "source.md#probe-phantom",
  );
  assert.ok(phantomLink, result.output);
  assert.equal(phantomLink.state, "BROKEN", result.output);
  assert.equal(phantomLink.status, 200, result.output);
});
for (const mode of ["disabled", "isolated"]) {
  test(`startup fails closed with ${mode} hook before reading repository input`, (t) => {
    const dir = createFixture(t, { "source.md": phantom });
    const result = checkLinks(dir, ["does-not-exist.md"], mode);
    assert.equal(result.status, 2);
    assert.match(result.stderr, /startup self-check failed/);
    assert.equal(result.stdout, "");
    assert.doesNotMatch(result.stderr, /glob/);
  });
}
test("double registration preserves body and metadata isolation", (t) => {
  for (const [content, expectedStatus] of [
    [phantom, 1],
    [phantom.replace("#probe-phantom", "#body"), 0],
  ]) {
    const dir = createFixture(t, { "source.md": content });
    const result = checkLinks(dir, ["source.md"], "double");
    assert.equal(result.status, expectedStatus, result.output);
  }
});
test("fresh CLI invocations are deterministic", (t) => {
  const dir = createFixture(t, { "source.md": phantom });
  const results = Array.from({ length: 3 }, () =>
    checkLinks(dir, ["source.md"]),
  );
  assert.ok(results.every((r) => r.status === 1));
  assert.equal(results[0].stdout, results[1].stdout);
  assert.equal(results[1].stdout, results[2].stdout);
});
test("batch diagnostics name both original malformed files", (t) => {
  const dir = createFixture(t, {
    "first.md": "---\na: [broken\n---\n",
    "second.md": "---\na: 1\na: 2\n---\n",
  });
  const result = checkLinks(dir, ["first.md", "second.md"]);
  assert.equal(result.status, 1, result.stderr);
  const report = JSON.parse(result.stdout);
  assert.deepEqual(
    report.result.links
      .filter((link) => link.state === "BROKEN")
      .map((link) => link.url)
      .sort(),
    ["first.md", "second.md"],
  );
  assert.equal(report.yamlErrors.length, 2);
});
test("native hook-disabled control exposes phantom-anchor false green", (t) => {
  const dir = createFixture(t, { "source.md": phantom });
  const result = runNode(dir, [
    join(root, "tests/link-validation/native-control.mjs"),
  ]);
  assert.equal(result.status, 0, result.output);
  assert.equal(JSON.parse(result.stdout).passed, true);
});

// Exercise directory destinations in addition to the fixed contract cases.
const directoryCases = [
  { name: "relative directory", target: "docs" },
  { name: "trailing slash", target: "docs/" },
  { name: "empty directory", target: "empty/" },
  { name: "nested directory", target: "docs/nested/" },
  {
    name: "parent-relative directory",
    input: "docs/source.md",
    target: "../docs/nested",
  },
  { name: "dot-segment normalization", target: "docs/../docs/nested/" },
  { name: "encoded space", target: "space%20dir/" },
  { name: "literal space", target: "<space dir/>" },
  { name: "encoded unicode", target: "caf%C3%A9/" },
  { name: "query preserved through redirect", target: "docs?view=tree" },
  { name: "missing directory", target: "absent", fails: true },
  { name: "missing directory with slash", target: "absent/", fails: true },
  { name: "missing nested directory", target: "docs/absent/", fails: true },
  { name: "file with trailing slash", target: "docs/file.md/", fails: true },
  { name: "file fragment", target: "docs/file.md#file" },
  { name: "missing file fragment", target: "docs/file.md#absent", fails: true },
  { name: "fragment only", target: "#source" },
  { name: "missing fragment only", target: "#absent", fails: true },
  { name: "index fragment", target: "indexed/#present" },
  { name: "missing index fragment", target: "indexed/#absent", fails: true },
  // Native generated listings have no HTML content type and no fragment contract.
  {
    name: "listing fragment is not validated by native Linkinator",
    target: "docs/#absent",
  },
];
for (const directoryCase of directoryCases) {
  test(`directory contract: ${directoryCase.name}`, (t) => {
    const input = directoryCase.input || "source.md";
    const files = {
      "docs/file.md": "# File\n",
      "docs/nested/keep.txt": "nested\n",
      "space dir/keep.txt": "space\n",
      "café/keep.txt": "unicode\n",
      "indexed/index.html": '<h1 id="present">Present</h1>\n',
      [input]: `# Source\n\n[directory case](${directoryCase.target})\n\n[external](https://example.invalid/)\n`,
    };
    const dir = createFixture(t, files);
    mkdirSync(join(dir, "empty"));
    const init = spawnSync("git", ["init", "--quiet"], {
      cwd: dir,
      encoding: "utf8",
    });
    assert.ifError(init.error);
    assert.equal(init.signal, null, init.stdout + init.stderr);
    assert.equal(init.status, 0, init.stdout + init.stderr);
    const result = checkLinks(dir, [input]);
    assert.equal(result.status, directoryCase.fails ? 1 : 0, result.output);
    const report = JSON.parse(result.stdout);
    assert.equal(report.yamlErrors.length, 0);
    assert.ok(
      report.result.links.some(
        (link) =>
          link.url === "https://example.invalid/" && link.state === "SKIPPED",
      ),
    );
    // Successful same-document fragments need no separate Linkinator result.
    if (directoryCase.target !== "#source") {
      assert.ok(
        report.result.links.some(
          (link) => link.displayText === "directory case",
        ),
      );
    }
    for (const [name, content] of Object.entries(files)) {
      assert.equal(readFileSync(join(dir, name), "utf8"), content);
    }
  });
}
test("directory contract: outside-root directory cannot be served", (t) => {
  const parent = createFixture(t, {
    "outside/index.html": "<h1>Outside</h1>\n",
  });
  const dir = join(parent, "repo");
  mkdirSync(dir);
  // WHATWG URL resolution clamps literal .. at the URL root. Encoded slashes
  // exercise Linkinator's server containment check after percent decoding.
  for (const target of ["../outside/", "..%2Foutside/"]) {
    const source = `# Source\n\n[outside](${target})\n`;
    writeFileSync(join(dir, "source.md"), source);
    const result = checkLinks(dir, ["source.md"]);
    assert.equal(result.status, 1, result.output);
    assert.ok(
      JSON.parse(result.stdout).result.links.some(
        (link) => link.state === "BROKEN",
      ),
    );
    assert.equal(readFileSync(join(dir, "source.md"), "utf8"), source);
    assert.equal(
      readFileSync(join(parent, "outside/index.html"), "utf8"),
      "<h1>Outside</h1>\n",
    );
  }
});
test("native directory control: default rejects, directory listing accepts", (t) => {
  const dir = createFixture(t, {
    "source.md": "[docs](docs)\n",
    "docs/keep.txt": "keep\n",
  });
  for (const enabled of [false, true]) {
    const result = runNode(dir, [
      join(root, "tests/link-validation/native-control.mjs"),
      ...(enabled ? ["--directory-listing"] : []),
    ]);
    assert.equal(result.status, enabled ? 0 : 1, result.output);
    const link = JSON.parse(result.stdout).links.find(
      (link) => link.url === "docs",
    );
    assert.equal(link.status, enabled ? 200 : 404);
    assert.equal(link.state, enabled ? "OK" : "BROKEN");
  }
});

// These are literal argv values, not shell patterns. Unsupported selections
// must fail closed; successful literal-file support remains an upstream concern.
const requestedPathCases = [
  { name: "ordinary.md", validStatus: 0, brokenStatus: 1 },
  { name: "nested/deeper/new.md", validStatus: 0, brokenStatus: 1 },
  { name: "with space.md", validStatus: 0, brokenStatus: 1 },
  { name: "!bang.md", validStatus: 0, brokenStatus: 1 },
  {
    name: "choice{a,b}.md",
    decoy: "choicea.md",
    validStatus: 2,
    brokenStatus: 2,
  },
  { name: "meta[ab].md", decoy: "metaa.md", validStatus: 2, brokenStatus: 2 },
  { name: "plus+(a).md", decoy: "plusa.md", validStatus: 2, brokenStatus: 2 },
  { name: "#hash.md", validStatus: 2, brokenStatus: 2 },
  { name: "percent%23.md", validStatus: 1, brokenStatus: 1 },
  // Windows forbids these characters in filenames, not the other matrix cases.
  ...(process.platform === "win32"
    ? []
    : [
        {
          name: "star*.md",
          decoy: "star-decoy.md",
          validStatus: 2,
          brokenStatus: 1,
        },
        {
          name: "question?.md",
          decoy: "questionx.md",
          validStatus: 1,
          brokenStatus: 1,
        },
        {
          name: "at@(a|b).md",
          decoy: "ata.md",
          validStatus: 2,
          brokenStatus: 2,
        },
      ]),
];
for (const entry of requestedPathCases) {
  test(`requested-file attestation: ${entry.name}`, (t) => {
    const files = { [entry.name]: "# Source\n" };
    if (entry.decoy) files[entry.decoy] = "# Decoy\n";
    const dir = createFixture(t, files);
    for (const broken of [false, true]) {
      const content = "# Source\n" + (broken ? "\n[missing](absent.md)\n" : "");
      writeFileSync(join(dir, entry.name), content);
      const result = checkLinks(dir, [entry.name]);
      assert.equal(
        result.status,
        broken ? entry.brokenStatus : entry.validStatus,
        result.output,
      );
      if (result.status === 2) {
        assert.match(result.stderr, /Requested-file attestation failed/);
        assert.ok(result.stderr.includes(entry.name), result.stderr);
        assert.equal(result.stdout, "");
      } else if (result.status === 0) {
        const report = JSON.parse(result.stdout);
        assert.deepEqual(
          report.result.links.map((link) => decodeURIComponent(link.url)),
          [entry.name],
        );
      }
      assert.equal(readFileSync(join(dir, entry.name), "utf8"), content);
    }
    rmSync(join(dir, entry.name));
    const missing = checkLinks(dir, [entry.name]);
    assert.equal(missing.status, 2, missing.stdout + missing.stderr);
    assert.match(missing.stderr, /Requested-file attestation failed/);
    assert.ok(missing.stderr.includes(entry.name), missing.stderr);
  });
}

test("requested-file attestation: batches, duplicate inputs and linked targets", (t) => {
  const dir = createFixture(t, {
    "first.md":
      "# First\n\n[target](target.md#target)\n[redirect](docs)\n[external](https://example.invalid/)\n",
    "second.md": "# Second\n",
    "target.md": "# Target\n",
    "docs/index.html": "<h1>Directory</h1>\n",
    "choice{a,b}.md": "# Source\n\n[missing](absent.md)\n",
    "choicea.md": "# Decoy\n",
    "#hash.md": "# Source\n\n[missing](absent.md)\n",
  });
  for (const paths of [
    ["first.md", "second.md"],
    ["second.md", "first.md"],
    ["first.md", "./first.md"],
  ]) {
    const result = checkLinks(dir, paths);
    assert.equal(result.status, 0, result.output);
    const links = JSON.parse(result.stdout).result.links;
    assert.ok(
      links.some((link) => link.url === "target.md" && link.state === "OK"),
    );
    assert.ok(
      links.some(
        (link) =>
          link.url === "https://example.invalid/" && link.state === "SKIPPED",
      ),
    );
  }
  for (const name of ["choice{a,b}.md", "#hash.md"]) {
    const result = checkLinks(dir, ["second.md", name]);
    assert.equal(result.status, 2, result.output);
    assert.match(result.stderr, /Requested-file attestation failed/);
    assert.ok(result.stderr.includes(name), result.stderr);
  }
});

test("requested-file attestation: URL decoding cannot substitute a sibling", (t) => {
  for (const [requested, decoy] of [
    ["percent%23.md", "percent#.md"],
    ["percent%2Fname.md", "percent/name.md"],
  ]) {
    const dir = createFixture(t, {
      [requested]: "# Source\n\n[missing](absent.md)\n",
      [decoy]: "# Decoy\n",
    });
    const result = checkLinks(dir, [requested]);
    assert.equal(result.status, 2, result.output);
    assert.match(result.stderr, /Requested-file attestation failed/);
    assert.ok(result.stderr.includes(requested), result.stderr);
    assert.equal(result.stdout, "");
  }
});

for (const [platform, paths, root] of [
  ["POSIX", posix, "/repo"],
  ["Windows", win32, "C:\\repo"],
]) {
  test(`requested-file identity normalization: ${platform}`, () => {
    const origin = "http://127.0.0.1:12345";
    for (const [file, encoded] of [
      ["nested/space café.md", "nested/space%20caf%C3%A9.md"],
      ["nested/#hash.md", "nested/%23hash.md"],
      ["percent%23.md", "percent%2523.md"],
    ]) {
      assert.equal(
        pageIdentity(root, `${origin}/${encoded}`, origin, paths),
        repositoryIdentity(root, file, paths),
      );
    }
    assert.notEqual(
      pageIdentity(root, `${origin}/source.md?query#fragment`, origin, paths),
      repositoryIdentity(root, "source.md?query#fragment", paths),
    );
    assert.throws(
      () => pageIdentity(root, `${origin}/bad%2Fname.md`, origin, paths),
      /ambiguous/,
    );
    assert.throws(
      () => pageIdentity(root, `${origin}/bad%00name.md`, origin, paths),
      /ambiguous/,
    );
    assert.throws(
      () => pageIdentity(root, `${origin}/bad%zz.md`, origin, paths),
      URIError,
    );
    assert.throws(
      () =>
        pageIdentity(root, "http://example.invalid/source.md", origin, paths),
      /nonlocal/,
    );
    assert.throws(
      () => repositoryIdentity(root, "../outside.md", paths),
      /outside repository/,
    );
    if (platform === "Windows") {
      assert.equal(
        repositoryIdentity(root, "nested\\file.md", paths),
        repositoryIdentity(root, "nested/file.md", paths),
      );
      assert.throws(
        () => pageIdentity(root, `${origin}/C:/outside.md`, origin, paths),
        /outside repository/,
      );
      assert.throws(
        () => pageIdentity(root, `${origin}/bad%5Cname.md`, origin, paths),
        /ambiguous/,
      );
      assert.throws(
        () => repositoryIdentity(root, "D:\\outside.md", paths),
        /outside repository/,
      );
    }
  });
}
