import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {mkdtempSync, mkdirSync, readFileSync, writeFileSync, rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {dirname, join, resolve} from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
import {test} from 'node:test';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const cli = join(root, 'tools/check-links.mjs');
const control = pathToFileURL(join(root, 'tests/link-validation/import-control.mjs')).href;
const contractBytes = readFileSync(join(root, 'tests/link-validation/contract.json'));
assert.equal(createHash('sha256').update(contractBytes).digest('hex'),
  '320f9cc2b31fc0890e2f62b3b9745fa7807d67253080cc1cd80cbca2b4740795');
const contract = JSON.parse(contractBytes);
const lintPackage = JSON.parse(readFileSync(join(root, 'node_modules/markdownlint-cli2/package.json')));
const lint = join(root, 'node_modules/markdownlint-cli2', lintPackage.bin['markdownlint-cli2']);
function fixture(t, files) {
  const dir = mkdtempSync(join(tmpdir(), 'd1-regression-'));
  t.after(() => rmSync(dir, {recursive: true, force: true}));
  for (const [name, content] of Object.entries(files)) {
    mkdirSync(dirname(join(dir, name)), {recursive: true});
    writeFileSync(join(dir, name), content);
  }
  return dir;
}
function run(dir, paths, mode) {
  const result = spawnSync(process.execPath,
    [...(mode ? ['--import', control] : []), cli, ...paths],
    {cwd: dir, encoding: 'utf8', timeout: 30000,
      env: {...process.env, LINK_TEST_CONTROL: mode || ''}});
  assert.ifError(result.error);
  assert.equal(result.signal, null);
  return result;
}
for (const c of contract.cases) {
  test(`D1 contract: ${c.name}`, t => {
    const dir = fixture(t, c.files);
    const before = Object.keys(c.files).map(f => readFileSync(join(dir, f)));
    const result = run(dir, c.inputs);
    // Planning explicitly narrows former online cases to local-only acceptance.
    assert.equal(result.status, c.expected_local ? 0 : 1, result.stdout + result.stderr);
    const data = JSON.parse(result.stdout);
    for (const link of data.result.links.filter(link => /^https?:/.test(link.url))) {
      assert.equal(link.state, 'SKIPPED', JSON.stringify(link));
    }
    if (c.name.startsWith('yaml-') || c.name === 'cross-malformed-metadata') {
      assert.ok(data.yamlErrors.length, result.stdout);
    }
    const authoring = spawnSync(process.execPath,
      [lint, '--config', join(root, '.markdownlint-cli2.jsonc'), ...c.inputs],
      {cwd: dir, encoding: 'utf8', timeout: 30000});
    assert.ifError(authoring.error);
    assert.equal(authoring.status === 0, c.expected_lint, authoring.stdout + authoring.stderr);
    if (c.owner === 'markdownlint') assert.match(authoring.stderr, /MDX001/);
    if (c.name === 'dual-name-same') {
      assert.equal(result.status, 0);
      assert.match(authoring.stderr, /MD051/);
      t.diagnostic('D2 control: Linkinator accepts; unchanged MD051 rejects. Not a D1 failure.');
    }
    Object.keys(c.files).forEach((f, index) => assert.deepEqual(readFileSync(join(dir, f)), before[index]));
  });
}
const phantom = '---\nprobe: phantom\n---\n\n# Body\n\n[metadata](#probe-phantom)\n';
test('single-key phantom: effective hook rejects metadata destination', t => {
  const dir = fixture(t, {'source.md': phantom});
  const result = run(dir, ['source.md']);
  assert.equal(result.status, 1, result.stderr);
  assert.match(result.stdout, /probe-phantom.*not found/);
});
for (const mode of ['disabled', 'isolated']) {
  test(`startup fails closed with ${mode} hook before reading repository input`, t => {
    const dir = fixture(t, {'source.md': phantom});
    const result = run(dir, ['does-not-exist.md'], mode);
    assert.equal(result.status, 2);
    assert.match(result.stderr, /startup self-check failed/);
    assert.equal(result.stdout, '');
    assert.doesNotMatch(result.stderr, /glob/);
  });
}
test('double registration preserves body and metadata isolation', t => {
  for (const [content, code] of [[phantom, 1], [phantom.replace('#probe-phantom', '#body'), 0]]) {
    const dir = fixture(t, {'source.md': content});
    const result = run(dir, ['source.md'], 'double');
    assert.equal(result.status, code, result.stdout + result.stderr);
  }
});
test('fresh CLI invocations are deterministic', t => {
  const dir = fixture(t, {'source.md': phantom});
  const results = Array.from({length: 3}, () => run(dir, ['source.md']));
  assert.ok(results.every(r => r.status === 1));
  assert.equal(results[0].stdout, results[1].stdout);
  assert.equal(results[1].stdout, results[2].stdout);
});
test('batch diagnostics name both original malformed files', t => {
  const dir = fixture(t, {'first.md': '---\na: [broken\n---\n',
    'second.md': '---\na: 1\na: 2\n---\n'});
  const result = run(dir, ['first.md', 'second.md']);
  assert.equal(result.status, 1, result.stderr);
  const data = JSON.parse(result.stdout);
  assert.deepEqual(data.result.links.filter(l => l.state === 'BROKEN').map(l => l.url).sort(),
    ['first.md', 'second.md']);
  assert.equal(data.yamlErrors.length, 2);
});
test('native hook-disabled control exposes phantom-anchor false green', t => {
  const dir = fixture(t, {'source.md': phantom});
  const result = spawnSync(process.execPath,
    [join(root, 'tests/link-validation/native-control.mjs')],
    {cwd: dir, encoding: 'utf8', timeout: 30000});
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.equal(JSON.parse(result.stdout).passed, true);
});
