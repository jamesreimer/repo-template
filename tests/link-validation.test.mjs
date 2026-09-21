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
  'ce3927d1a459025450ac75560686412bb803e97e3be1e9300ce57c7478305e33');
const contract = JSON.parse(contractBytes);
const lintPackage = JSON.parse(readFileSync(join(root, 'node_modules/markdownlint-cli2/package.json')));
const lint = join(root, 'node_modules/markdownlint-cli2', lintPackage.bin['markdownlint-cli2']);
function fixture(t, files) {
  const dir = mkdtempSync(join(tmpdir(), 'link-regression-'));
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
  test(`Link contract: ${c.name}`, t => {
    const dir = fixture(t, c.files);
    const before = Object.keys(c.files).map(f => readFileSync(join(dir, f)));
    const result = run(dir, c.inputs);
    // Local acceptance is checked independently of external URLs, which are skipped.
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

// Exercise directory destinations in addition to the fixed contract cases.
const directoryCases = [
  {name: 'relative directory', target: 'docs'},
  {name: 'trailing slash', target: 'docs/'},
  {name: 'empty directory', target: 'empty/'},
  {name: 'nested directory', target: 'docs/nested/'},
  {name: 'parent-relative directory', input: 'docs/source.md', target: '../docs/nested'},
  {name: 'dot-segment normalization', target: 'docs/../docs/nested/'},
  {name: 'encoded space', target: 'space%20dir/'},
  {name: 'literal space', target: '<space dir/>'},
  {name: 'encoded unicode', target: 'caf%C3%A9/'},
  {name: 'query preserved through redirect', target: 'docs?view=tree'},
  {name: 'missing directory', target: 'absent', fails: true},
  {name: 'missing directory with slash', target: 'absent/', fails: true},
  {name: 'missing nested directory', target: 'docs/absent/', fails: true},
  {name: 'file with trailing slash', target: 'docs/file.md/', fails: true},
  {name: 'file fragment', target: 'docs/file.md#file'},
  {name: 'missing file fragment', target: 'docs/file.md#absent', fails: true},
  {name: 'fragment only', target: '#source'},
  {name: 'missing fragment only', target: '#absent', fails: true},
  {name: 'index fragment', target: 'indexed/#present'},
  {name: 'missing index fragment', target: 'indexed/#absent', fails: true},
  // Native generated listings have no HTML content type and no fragment contract.
  {name: 'listing fragment is not validated by native Linkinator', target: 'docs/#absent'},
];
for (const c of directoryCases) {
  test(`directory contract: ${c.name}`, t => {
    const input = c.input || 'source.md';
    const files = {
      'docs/file.md': '# File\n',
      'docs/nested/keep.txt': 'nested\n',
      'space dir/keep.txt': 'space\n',
      'café/keep.txt': 'unicode\n',
      'indexed/index.html': '<h1 id="present">Present</h1>\n',
      [input]: `# Source\n\n[directory case](${c.target})\n\n[external](https://example.invalid/)\n`,
    };
    const dir = fixture(t, files);
    mkdirSync(join(dir, 'empty'));
    const init = spawnSync('git', ['init', '--quiet'], {cwd: dir, encoding: 'utf8'});
    assert.equal(init.status, 0, init.stderr);
    const result = run(dir, [input]);
    assert.equal(result.status, c.fails ? 1 : 0, result.stdout + result.stderr);
    const data = JSON.parse(result.stdout);
    assert.equal(data.yamlErrors.length, 0);
    assert.ok(data.result.links.some(l => l.url === 'https://example.invalid/' && l.state === 'SKIPPED'));
    // Successful same-document fragments need no separate Linkinator result.
    if (c.target !== '#source') {
      assert.ok(data.result.links.some(l => l.displayText === 'directory case'));
    }
    for (const [name, content] of Object.entries(files)) {
      assert.equal(readFileSync(join(dir, name), 'utf8'), content);
    }
  });
}
test('directory contract: outside-root directory cannot be served', t => {
  const parent = fixture(t, {'outside/index.html': '<h1>Outside</h1>\n'});
  const dir = join(parent, 'repo');
  mkdirSync(dir);
  // WHATWG URL resolution clamps literal .. at the URL root. Encoded slashes
  // exercise Linkinator's server containment check after percent decoding.
  for (const target of ['../outside/', '..%2Foutside/']) {
    const source = `# Source\n\n[outside](${target})\n`;
    writeFileSync(join(dir, 'source.md'), source);
    const result = run(dir, ['source.md']);
    assert.equal(result.status, 1, result.stdout + result.stderr);
    assert.ok(JSON.parse(result.stdout).result.links.some(l => l.state === 'BROKEN'));
    assert.equal(readFileSync(join(dir, 'source.md'), 'utf8'), source);
    assert.equal(readFileSync(join(parent, 'outside/index.html'), 'utf8'), '<h1>Outside</h1>\n');
  }
});
test('native directory control: default rejects, directory listing accepts', t => {
  const dir = fixture(t, {'source.md': '[docs](docs)\n', 'docs/keep.txt': 'keep\n'});
  for (const enabled of [false, true]) {
    const result = spawnSync(process.execPath,
      [join(root, 'tests/link-validation/native-control.mjs'), ...(enabled ? ['--directory-listing'] : [])],
      {cwd: dir, encoding: 'utf8', timeout: 30000});
    assert.ifError(result.error);
    assert.equal(result.status, enabled ? 0 : 1, result.stdout + result.stderr);
    const link = JSON.parse(result.stdout).links.find(l => l.url === 'docs');
    assert.equal(link.status, enabled ? 200 : 404);
    assert.equal(link.state, enabled ? 'OK' : 'BROKEN');
  }
});
