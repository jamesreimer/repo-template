# Contributing

Keep changes tied to a concrete requirement or defect. Explain changes to the
baseline in terms of their benefit and maintenance cost for consuming repositories.

Maintainers: follow [MAINTAINING.md](MAINTAINING.md) when preparing or publishing
a release.

## Workflow

Use a descriptive branch and pull request title that identify the work. No
specific prefix vocabulary or commit-message format is required by the template.

Follow the [setup instructions](README.md#run-checks), stage intended new files,
and run:

```sh
.venv/bin/pre-commit run --all-files --show-diff-on-failure
git diff --check
```

Hooks that fix files exit unsuccessfully until their changes are reviewed and
included. Rerun after reviewing fixes. An installed commit hook checks staged
files; the full command also catches effects on unchanged sources, such as
links to a deleted target. Run the full command before opening a pull request.

CI runs the same configuration on the checked-out commit. Required checks,
review counts, merge strategy, and permissions belong to the repository's host
settings and should be chosen for the project.

## Changing validation

`.pre-commit-config.yaml` owns tool selection and file scope. Markdown rules live
in `.markdownlint-cli2.jsonc`; Python rules live in `ruff.toml`. Use the tools'
native configuration when project requirements change. Make exclusions explicit
and explain substantive coverage reductions in the pull request.

Linkinator checks Markdown links offline, including fragments. It runs as a
fresh process through `tools/check-links.mjs`, with exact dependencies in
`package.json` and `package-lock.json`. A startup probe verifies that front matter
is excluded by the renderer actually used by Linkinator; an ineffective hook
stops validation before repository content is read. External HTTP/HTTPS links
are skipped, including redirects leaving the local serving origin. There is no
required remote-link check. Absolute website routes and generated destinations
need a project-specific decision. Markdown parsing belongs to the
maintained tools. The local `fenced-code-closed` authoring rule consumes
markdownlint's micromark tokens to require explicit fence closure; it neither
parses Markdown independently nor chooses a closing position automatically.
Working symbolic links are allowed.

Directory destinations use Linkinator's native directory listings and do not
require an `index.html`. Missing directories still fail. If an `index.html` is
present, Linkinator checks its fragments; generated listings do not expose an
HTML fragment contract, so fragments on those listings are not validated.
Use an explicit Markdown or HTML file link when a fragment must be checked.

When changing a check or its scope, verify both that representative defects fail
and that representative valid files pass in an isolated Git repository. Include
new-file selection and the full CI command where relevant. The suite includes
`tests/markdown-rules.test.cjs`, which exercises the local rule through the
installed CLI and actual configuration in the same isolated hook environment.
Keep embedded Markdown examples, container boundaries, opening-line locations,
and no-autofix behavior covered when updating the rule or its parser dependency.
Projects should add tests for the additional behavior they own.

## Updating dependencies

Hook repositories are pinned to immutable commits, with version comments.
Review updates using:

```sh
.venv/bin/pre-commit autoupdate --freeze
```

Review the resulting versions and configuration compatibility, then run the
full suite. `requirements-dev.txt` pins the runner. npm owns the link checker,
its explicit Marked dependency, the maintained front-matter stack, and the
Markdownlint dependency used by its regression tests. Use `npm ci --ignore-scripts`
locally and in CI. The lock preserves the full dependency resolution;
pre-commit `additional_dependencies` cannot provide that transitive lock.
The startup probe is still required: correctness must not depend on hoisting.
Update pins and lock together, then run the regression suite and ordinary checks.
Keep the test Markdownlint version aligned with its existing pre-commit hook.

Dependabot proposes GitHub Actions, Python requirements, and npm dependency
updates monthly. Hook revisions remain covered by `pre-commit autoupdate`.
Actions are pinned by commit as well; review version inputs when updating them.

The durable link regression contract and test controls are documented in
[tests/link-validation/README.md](tests/link-validation/README.md).
