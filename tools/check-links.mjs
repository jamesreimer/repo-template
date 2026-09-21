// Process entry point only: every invocation owns its Marked configuration.
import {LinkChecker} from 'linkinator';
import {mkdtemp, writeFile, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {observations} from './link-frontmatter.mjs';

// Linkinator calls this for the initial local URL before discovering links.
// Only its ephemeral serving origin may be requested, including redirects.
function offlineOptions(root, paths) {
  let origin;
  return {path: paths, serverRoot: root, markdown: true, checkFragments: true,
    // Repository directories need not contain a website index.html.
    directoryListing: true,
    timeout: 10000, retry: false, retryErrors: false,
    linksToSkip(url) {
      origin ??= new URL(url).origin;
      return new URL(url).origin !== origin;
    }};
}

async function selfCheck() {
  const root = await mkdtemp(join(tmpdir(), 'linkinator-startup-'));
  try {
    // Unhooked Marked creates #probe-phantom from this single-key metadata.
    await writeFile(join(root, 'probe.md'),
      '---\nprobe: phantom\n---\n\n# Body\n\n[body](#body)\n[metadata](#probe-phantom)\n');
    const result = await new LinkChecker().check(offlineOptions(root, ['probe.md']));
    const broken = result.links.filter(link => link.state === 'BROKEN');
    if (result.passed || observations.yamlErrors.length || broken.length !== 1 ||
        broken[0].url !== 'probe.md#probe-phantom' || broken[0].status !== 200 ||
        !result.links.some(link => link.url === 'probe.md' && link.state === 'OK')) {
      throw new Error('Front-matter startup self-check failed: Linkinator did not isolate metadata. Check the pinned Marked instance and hook installation.');
    }
  } finally {
    await rm(root, {recursive: true, force: true});
  }
}

try {
  await selfCheck();
  const paths = process.argv.slice(2);
  if (!paths.length || paths.some(path => /^https?:/i.test(path))) {
    throw new Error('Supply repository-relative local Markdown paths.');
  }
  const result = await new LinkChecker().check(offlineOptions(process.cwd(), paths));
  console.log(JSON.stringify({result, yamlErrors: observations.yamlErrors},
    (key, value) => value instanceof Error ? {message: value.message} : value));
  process.exitCode = result.passed && !observations.yamlErrors.length ? 0 : 1;
} catch (error) {
  console.error(error.message);
  process.exitCode = 2;
}
