import nativePath from "node:path";

// The optional path implementation lets tests exercise Windows rules on POSIX.
export function repositoryIdentity(root, file, paths = nativePath) {
  const identity = paths.relative(root, paths.resolve(root, file));
  if (
    !identity ||
    identity === ".." ||
    identity.startsWith(`..${paths.sep}`) ||
    paths.isAbsolute(identity)
  ) {
    throw new Error(
      `Requested-file attestation failed: path outside repository: ${JSON.stringify(file)}`,
    );
  }
  return identity;
}

export function pageIdentity(root, page, origin, paths = nativePath) {
  const url = new URL(page);
  if (url.origin !== origin)
    throw new Error("Requested-file attestation failed: nonlocal page start.");
  const segments = url.pathname
    .slice(1)
    .split("/")
    .map((segment) => {
      const decoded = decodeURIComponent(segment);
      if (
        decoded.includes("/") ||
        decoded.includes("\0") ||
        (paths.sep === "\\" && decoded.includes("\\"))
      ) {
        throw new Error(
          "Requested-file attestation failed: ambiguous encoded path separator.",
        );
      }
      return decoded;
    });
  // Query and fragment are URL syntax, never part of a filesystem identity.
  return repositoryIdentity(root, segments.join(paths.sep), paths);
}
