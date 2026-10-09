// Process entry point only: every invocation owns its Marked configuration.
import { LinkChecker } from "linkinator";
import { mkdtemp, writeFile, rm, stat } from "node:fs/promises";
import { tmpdir } from "node:os";
import { isAbsolute, join, resolve } from "node:path";
import {
  repositoryIdentity,
  pageIdentity,
} from "./requested-file-identity.mjs";
import { observations } from "./link-frontmatter.mjs";

// Linkinator calls this for the initial local URL before discovering links.
// Only its ephemeral serving origin may be requested, including redirects.
function offlineOptions(root, paths, recordOrigin) {
  let origin;
  return {
    path: paths,
    serverRoot: root,
    markdown: true,
    checkFragments: true,
    // Repository directories need not contain a website index.html.
    directoryListing: true,
    timeout: 10000,
    retry: false,
    retryErrors: false,
    linksToSkip(url) {
      origin ??= new URL(url).origin;
      recordOrigin?.(origin);
      return new URL(url).origin !== origin;
    },
  };
}

async function selfCheck() {
  const root = await mkdtemp(join(tmpdir(), "linkinator-startup-"));
  try {
    // Unhooked Marked creates #probe-phantom from this single-key metadata.
    await writeFile(
      join(root, "probe.md"),
      "---\nprobe: phantom\n---\n\n# Body\n\n[body](#body)\n[metadata](#probe-phantom)\n",
    );
    const result = await new LinkChecker().check(
      offlineOptions(root, ["probe.md"]),
    );
    const broken = result.links.filter((link) => link.state === "BROKEN");
    if (
      result.passed ||
      observations.yamlErrors.length ||
      broken.length !== 1 ||
      broken[0].url !== "probe.md#probe-phantom" ||
      broken[0].status !== 200 ||
      !result.links.some(
        (link) => link.url === "probe.md" && link.state === "OK",
      )
    ) {
      throw new Error(
        "Front-matter startup self-check failed: Linkinator did not isolate metadata. Check the pinned Marked instance and hook installation.",
      );
    }
  } finally {
    await rm(root, { recursive: true, force: true });
  }
}

try {
  await selfCheck();
  const paths = process.argv.slice(2);
  if (!paths.length || paths.some((path) => /^https?:/i.test(path))) {
    throw new Error("Supply repository-relative local Markdown paths.");
  }
  const root = process.cwd();
  const requested = new Map();
  for (const path of paths) {
    if (isAbsolute(path))
      throw new Error(
        `Supply a repository-relative path: ${JSON.stringify(path)}`,
      );
    const identity = repositoryIdentity(root, path);
    const info = await stat(resolve(root, identity)).catch(() => undefined);
    if (!info?.isFile())
      throw new Error(
        `Requested-file attestation failed: not an existing file: ${JSON.stringify(path)}`,
      );
    requested.set(identity, path);
  }
  const pages = [];
  const checker = new LinkChecker();
  let origin;
  // Snapshot the public URL immediately; do not retain a mutable event object.
  checker.on("pagestart", (page) => pages.push(String(page)));
  const result = await checker.check(
    offlineOptions(root, paths, (value) => {
      origin = value;
    }),
  );
  // Rendering failures (for example malformed YAML) can precede pagestart.
  // Preserve their existing failure result; only proven exact scans may pass.
  if (result.passed && !observations.yamlErrors.length) {
    let observed;
    try {
      observed = new Set(pages.map((page) => pageIdentity(root, page, origin)));
    } catch (error) {
      throw new Error(
        `Requested-file attestation failed for ${JSON.stringify(paths)}: ${error.message}`,
        { cause: error },
      );
    }
    const missing = [...requested]
      .filter(([identity]) => !observed.has(identity))
      .map(([, path]) => path);
    const unexpected = [...observed].filter(
      (identity) => !requested.has(identity),
    );
    if (missing.length || unexpected.length) {
      throw new Error(
        `Requested-file attestation failed for ${JSON.stringify(paths)}: unproven requested paths ${JSON.stringify(missing)}; unexpected initial paths ${JSON.stringify(unexpected)}. Linkinator cannot prove exact selection.`,
      );
    }
  }
  console.log(
    JSON.stringify(
      { result, yamlErrors: observations.yamlErrors },
      (key, value) =>
        value instanceof Error ? { message: value.message } : value,
    ),
  );
  process.exitCode = result.passed && !observations.yamlErrors.length ? 0 : 1;
} catch (error) {
  console.error(error.message);
  process.exitCode = 2;
}
