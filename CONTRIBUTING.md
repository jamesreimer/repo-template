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

## Tooling rule

Repository tooling is Python, standard library only, targeting the version
floor in [README.md](README.md). Because a newer local interpreter will not
reject older syntax, CI pins the floor explicitly. Use shell only where the
shell is itself the interface.

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
| `markdown-links` | on | `globs` |
| `markdown-headings` | on | `globs` |
| `credential-files` | on | `patterns`, `allow` |
| `path-names` | **off** | `pattern`, `scope`, `exempt`, `rules` |
| `structure-snapshot` | **off** | `path` |

Glob options accept `*` within a path segment and `**` across segments.

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
from validate import markdown_without_fenced_code


def extra_checks(context):
    # context.root, context.files, context.text
    return [("path/to/file.md", 0, "what is wrong")]
```

Return `(path, line, reason)` tuples. A local check that raises is reported as
a finding rather than aborting the run.

Do not fork `scripts/validate.py` to add a repository-specific check. If a
check cannot be expressed through configuration or a local module, that is a
defect in this template and should be fixed here.

## Scope of automated validation

Validation checks mechanical invariants: encoding, newlines, junk artifacts,
required files, internal link resolution including reference-style label and
definition integrity, fenced code block balance, heading hierarchy including a
single leading H1, credential-shaped filenames, committed symbolic links, and
optionally path naming and the structure snapshot.

It deliberately does not check scope, boundaries, proportionality, or prose
quality. Those remain human and AI review responsibilities.
