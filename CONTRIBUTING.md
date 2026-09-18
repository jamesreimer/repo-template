# Contributing

Keep contributions bounded to a concrete need or a concrete defect. Apply the
[design principle](README.md#design-principle) before adding any file, check,
or automation.

## Branch names and pull request titles

Use a conventional type prefix, and use the same type for the branch and its
pull request.

| Type | Work | Branch example | Pull request title example |
| --- | --- | --- | --- |
| `feat` | New or extended functionality | `feat/credential-check` | `feat: add credential file check` |
| `fix` | Corrections to defects | `fix/anchor-resolution` | `fix: correct anchor resolution` |
| `docs` | Documentation and guidance | `docs/adoption-notes` | `docs: clarify adoption notes` |
| `chore` | Maintenance or configuration | `chore/update-action-pins` | `chore: update action pins` |
| `refactor` | Restructuring without behavior change | `refactor/glob-helpers` | `refactor: simplify glob helpers` |

Format branch names as `<type>/<short-kebab-case-description>` and pull request
titles as `<type>: <concise description>`. Do not use actor or tool names such
as `codex/` as branch prefixes. This applies to human and automated
contributions alike.

## Validation

Run both checks before submitting a change:

```bash
python3 -m unittest discover -s tests
```

```bash
python3 scripts/validate.py
```

CI additionally checks Markdown hygiene, Python lint and formatting, and
workflow syntax. When a contribution affects those files, run the applicable
check locally:

```bash
markdownlint-cli2
python3 scripts/check_markdown_links.py
```

```bash
ruff check scripts tests && ruff format --check scripts tests
```

```bash
actionlint .github/workflows/*.yml
```

When an intentional change adds, removes, or moves repository paths,
regenerate the structure snapshot before validating:

```bash
python3 scripts/update_repository_structure.py
```

## Updating pinned tool versions

Actions in `.github/workflows/validate.yml` are pinned by commit SHA, and
Dependabot updates those references monthly.

It does not update the tool versions passed to them. `ruff-action` and the
`actionlint` action take a `version:` input naming the tool to run; Lychee uses
`lycheeVersion:`. The Markdown linter version is pinned in its installation
command. These tool versions are invisible to Dependabot's `github-actions`
ecosystem. Without attention they stay frozen while the actions around them move.

Review them when a Dependabot pull request touches the surrounding action, or
when a lint failure suggests the pinned version has fallen behind. Bump the
`version:` input deliberately, in its own change, and confirm the suite still
passes. No automation is provided, because a tool version that changes without
review is exactly what pinning exists to prevent.

## Who checks Markdown

Markdown is linted by `markdownlint-cli2`, using `.markdownlint-cli2.jsonc`.
It checks heading structure, same-file fragments, reference labels and
definitions, and the selected formatting rules. Run it alongside the Python
checks when Markdown changes; it also runs in CI.

`python3 scripts/check_markdown_links.py` uses Lychee 0.24.2 to check local
link targets and fragments offline. It selects Markdown files from the same
Git-aware working-tree inventory as the Python validator and rejects links
that resolve outside the repository before checking destinations. Absolute
link paths are rejected by Lychee; no website root is configured. External
URLs are not requested. Markdown links, images, and embedded HTML links are
handled by Lychee's parsers, including code and comment context.

An unclosed fence is valid CommonMark and no longer triggers a separate
custom rule. Undefined full/collapsed reference uses are diagnosed by MD052;
unused or duplicate definitions by MD053. The template no longer tries to
infer malformed definitions from ordinary bracketed prose.

## Tooling rule

Repository-owned scripts use Python's standard library. Markdown linting and
link validation use maintained external tools instead of a handwritten parser.
Dependencies are justified by demonstrated correctness and maintenance needs;
the absence of dependencies is not an overriding design requirement.

Install `markdownlint-cli2@0.23.2` (Node.js 22 or later) and Lychee 0.24.2 before
running the full suite. CI pins both tool versions. The link-check command
fails with installation guidance if Lychee is missing. Python unit tests skip external-tool integration cases when a tool is
unavailable; passing those tests alone does not establish Markdown coverage.

## Configuration reference

`validate.json` selects which checks run. Every key is optional; omitted keys
take the default. Keys beginning with `_` are ignored and may be used as
comments. An unknown check or option is an error rather than a silent no-op.

| Check | Default | Options |
| --- | --- | --- |
| `junk-artifacts` | on | `names`, `patterns`, `directories` |
| `text-encoding` | on | `globs` |
| `final-newline` | on | `globs` |
| `required-files` | on, empty | `paths` |
| `credential-files` | on | `patterns`, `allow` |
| `path-names` | **off** | `pattern`, `scope`, `exempt`, `rules` |
| `structure-snapshot` | **off** | `path` |

Glob options accept `*` within a path segment and `**` across segments.

A trailing `/**` matches what is inside a directory, not the directory itself.
Scoping `src/**` never examines `src`, so a rule that should cover both needs
both entries: `["src", "src/**"]`. The same applies to `exempt`.

Committed symbolic links are rejected unconditionally and have no configuration key.
A symbolic link is mechanically distinct from ordinary repository content and its
target may resolve outside the repository, so the link is reported without being
read or resolved.

`path-names` is off by default because naming conventions are repository
decisions, not universal ones.

A repository with one convention states `pattern`, `scope` and `exempt`
directly. A repository whose convention differs by directory states `rules`
instead: a list of objects each taking its own `pattern`, `scope` and `exempt`.
Providing `rules` replaces the single-rule form rather than layering on top of
it.

Rules are evaluated in declared order, and the first rule whose `scope` matches
decides a path. One path therefore produces at most one finding no matter how
many rules could have matched. Order rules most specific first and put any
catch-all last. A path matched by no rule is not checked.

This lets one repository require kebab-case for content while requiring
snake_case for Python modules, which a single pattern cannot express:

```json
{
  "path-names": {
    "enabled": true,
    "rules": [
      {
        "_": "Python modules in Python-owned directories.",
        "pattern": "^(?:[a-z][a-z0-9]*(?:_[a-z0-9]+)*|__init__)\\.py$",
        "scope": ["scripts/*.py", "tests/*.py"]
      },
      {
        "_": "Everything else is kebab-case.",
        "pattern": "^[a-z0-9]+(?:-[a-z0-9]+)*(?:\\.[a-z0-9]+)*$",
        "scope": ["**"],
        "exempt": ["scripts", "tests"]
      }
    ]
  }
}
```

As at the top level, keys beginning with `_` inside a rule are ignored and may
be used as comments.

## Repository-specific checks

Checks that only make sense for one repository belong in
`scripts/validate_local.py`, which is optional and loaded automatically when
present. It is imported as an ordinary module, so `dataclasses`, `typing`, and
`from __future__ import annotations` all work as usual:

```python
def extra_checks(context):
    # context.root, context.files, context.text
    return [("path/to/file.md", 0, "what is wrong")]
```

Return `(path, line, reason)` tuples with string paths and reasons and a
nonnegative integer line number (0 means the whole file). Exceptions and
malformed results are reported as findings rather than aborting the run.

Do not fork `scripts/validate.py` to add a repository-specific check. If a
check cannot be expressed through configuration or a local module, that is a
defect in this template and should be fixed here.

## Scope of automated validation

Validation checks mechanical invariants: encoding, newlines, junk artifacts,
required files, credential-shaped filenames, symbolic links, and optionally
path naming and the structure snapshot. The validator inspects the current
working tree, including unignored new files; it does not validate the Git index
as a separate snapshot. Markdown linting is a separate command as described
above.

It deliberately does not check scope, boundaries, proportionality, or prose
quality. Those remain human and AI review responsibilities.
