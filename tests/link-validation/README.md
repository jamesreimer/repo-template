# Local link regression contract

Run `npm ci --ignore-scripts`, then `npm run test:links`. The ordinary pre-commit
run also runs this suite. Tests materialize synthetic fixture strings in temporary
directories and verify their bytes after validation; no repository content is
rewritten or mirrored.

`contract.json` preserves the 63-case retained scratch qualification verbatim
(SHA-256 `320f9cc2b31fc0890e2f62b3b9745fa7807d67253080cc1cd80cbca2b4740795`).
It does not claim continuity with the vanished historical 53-case suite.
The current Planning decision makes every case offline: `expected_local` controls
Linkinator acceptance, while former `expected_external` values describe historical
online qualification only. Every discovered HTTP/HTTPS URL must be skipped.

All existing authoring expectations remain unchanged. In `dual-name-same`,
Linkinator correctly accepts the name destination while Markdownlint MD051
rejects it. This is the separately owned D2 control, not a D1 failure. The test
asserts that disagreement rather than fixing it or counting it as D1 rejection.

Additional controls cover single-key metadata, native false-green behavior,
disabled hooks, separate Marked instances, duplicate registration, independent
CLI repeatability, and original filenames in batch diagnostics. The test-only
Node module hooks use public loader APIs to disable our hook or resolve it to a
separate Marked module instance. They do not patch dependencies or add fragment
matching. These controls are never imported by the production entry point.

`tools/check-links.mjs` is a process entry point only. Each startup writes a tiny
synthetic single-key YAML document in a temporary directory and asks Linkinator
to validate its known body and metadata fragment references. The required outcome
is exactly one missing metadata fragment on a successfully rendered document.
Native Marked incorrectly accepts that fragment. Any other startup outcome exits
nonzero before repository inputs are checked. This verifies effective integration
without assuming a particular package-manager layout or importing private code.

The wrapper configures the public shared Marked instance once per process.
Other in-process consumers would share its configuration; no reusable checker
API is offered. Duplicate registration is tested only as a corruption control,
not an endorsed execution model. Indirect targets may render twice; this is
accepted and is not optimized.

Link diagnostics retain original filenames and display text. Linkinator does
not promise Markdown line/column positions. YAML snippets use metadata-relative
positions; malformed files remain named as failed local results. The earlier
broad claim that batch YAML failures could not be usefully attributed is withdrawn:
the durable batch control identifies both original failing filenames. No source-map
or line-number enhancement is part of D1.
