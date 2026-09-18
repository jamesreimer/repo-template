# Contributing

Keep changes tied to a concrete requirement or defect. Explain changes to the
baseline in terms of their benefit and maintenance cost for consuming repositories.

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

Lychee checks Markdown links offline, including fragments. Its native config
and ignore files are supported; changes to them are changes to validation
coverage. Absolute website routes, generated destinations, and external network
checks need a project-specific decision. Markdown parsing belongs to the
maintained tools. The local `fenced-code-closed` authoring rule consumes
markdownlint's micromark tokens to require explicit fence closure; it neither
parses Markdown independently nor chooses a closing position automatically.
Working symbolic links are allowed.

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
full suite. `requirements-dev.txt` pins the runner. Lychee is a system dependency:
update the version in the setup documentation and workflow together, and test
it locally. Updating its hook revision alone does not update the installed
binary. The hook uses the installed binary directly, without a download wrapper.

Dependabot proposes GitHub Actions and Python requirements updates monthly.
It does not update the workflow's Lychee version input or the hook revisions.
Actions are pinned by commit as well; review version inputs when updating them.
