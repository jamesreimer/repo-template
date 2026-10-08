# Contributing

Keep changes tied to a concrete requirement or defect. Explain changes to the
baseline in terms of their benefit, maintenance cost, and cost of deferral for
consuming repositories, including any loss of evidence quality from waiting.

Maintainers: follow [MAINTAINING.md](MAINTAINING.md) when preparing or publishing
a release.

## Workflow

Use a descriptive branch and pull request title that identify the work. No
specific prefix vocabulary or commit-message format is required by the template.

Record notable changes through the [changelog workflow](#changelog) as part of
the change that creates the historical fact, while context is fresh. Update any
other deliberately selected historical/evidence artifacts in the same change.

Follow the [setup instructions](README.md#run-checks), stage intended new files,
and run:

```sh
.venv/bin/pre-commit run --all-files --show-diff-on-failure
git diff --check
```

Hooks that fix files exit unsuccessfully until their changes are reviewed and
included. Rerun after reviewing fixes. An installed commit hook checks staged
files and runs the repository-wide quality scripts; the full command also catches
effects on unchanged sources, such as links to a deleted target. Run the full
command before opening a pull request.

CI runs the same configuration on the checked-out commit. Required checks,
review counts, merge strategy, and permissions belong to the repository's host
settings and should be chosen for the project.
The [default-branch ruleset](rulesets/README.md) supplies a reusable starting
configuration and a separate host verification procedure. When changing the
required job's name, source, or triggers, reconcile the live required check with
the workflow so every pull request targeting the protected branch can report it.

## Changelog

[CHANGELOG.md](CHANGELOG.md) follows [Common Changelog](https://common-changelog.org/)
and preserves a concise interpretation of notable repository changes. Git owns
exact history; PRs and issues retain implementation and decision evidence;
GitHub Releases record publication and release-specific notes; current files
define current behavior. The changelog does not duplicate those responsibilities.

For each PR, include a proposed changelog summary and supporting references in
the PR description, or explain why the change is not notable. Capture consumer
impact and compatibility implications while context is fresh. Reviewers verify
that this summary reflects the final change before merge. Keep it concise and
curated: baseline additions, consumer fixes, validation behavior, and meaningful
maintenance or release-procedure changes belong here; routine dependency bumps
and trivial edits generally do not.

Common Changelog states that changes must reference relevant commits, while its
own examples also show pull-request references. This repository interprets those
examples as permitting a pull request to serve as the durable change reference
when the commit that will represent a same-PR change in published history does
not yet exist.

When that canonical commit already exists, use it and include the associated
pull request where useful. A pull-request reference used for a same-PR change
is final; do not later supplement or replace it merely because the canonical
merged commit becomes available. Do not cite a commit that will not belong to
published history. [Release preparation](MAINTAINING.md#prepare-the-release)
describes reference selection across merge methods without requiring one method.

Before a release version and date are selected, pending summaries accumulate in
those retained PR descriptions. Do not add an `Unreleased` section, invent a
version/date, or put new changes under an already published release. Once a
release section is being prepared, update it in the same PR as any further
notable change included in that release. Maintainers reconcile the complete
delta with the recorded summaries before publication, as described in
[release preparation](MAINTAINING.md#prepare-the-release). This transfers and
curates existing interpretation rather than reconstructing it from scratch.

Repo-template's initial changelog history, `1.0.0` through `1.2.1`, was backfilled
from retained release notes, tags, and changes; it was not written
contemporaneously. Consuming repositories should adapt or remove this
repo-template-specific note when establishing their own independent history.

## Changing validation

`.pre-commit-config.yaml` owns tool selection and file scope. Markdown rules live
in `.markdownlint-cli2.jsonc`. Use the tools' native configuration when project
requirements change. Make exclusions explicit and explain substantive coverage
reductions in the pull request.

ESLint owns JavaScript correctness and maintainability through `eslint.config.mjs`;
Prettier owns mechanical formatting through `.prettierrc.json` and the format
scripts in `package.json`. Run `npm run lint:js` and `npm run format:check` for
focused checks. Both also run through pre-commit, using the repository-installed
npm dependencies. Validation is check-only for these tools; run `npm run format`
from this repository to apply formatting deliberately, then review the diff.

Formatting covers JavaScript, JSON/JSONC, YAML, and Markdown. `.prettierignore`
excludes the Python environment, npm-owned lockfile, digest-pinned link contract,
and YAML parser fixture. Markdown prose wrapping is preserved and embedded
examples are not reformatted. Existing syntax, Markdown, link, and workflow
validators retain their semantic responsibilities.

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
Markdownlint dependency used by its regression tests, ESLint, and Prettier.
Use `npm ci --ignore-scripts`
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
