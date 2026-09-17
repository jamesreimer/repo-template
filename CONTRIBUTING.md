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
| `credential-files` | on | `patterns`, `allow` |
| `path-names` | **off** | `pattern`, `scope`, `exempt` |
| `structure-snapshot` | **off** | `path` |

Glob options accept `*` within a path segment and `**` across segments.

Committed symbolic links are rejected unconditionally and have no configuration key.
A symbolic link is mechanically distinct from ordinary repository content and its
target may resolve outside the repository, so the link is reported without being
read or resolved.

`path-names` is off by default because naming conventions are repository
decisions, not universal ones. A repository with source files that are
legitimately not kebab-case should leave it off rather than accumulate
exemptions.

## Repository-specific checks

Checks that only make sense for one repository belong in
`scripts/validate_local.py`, which is optional and loaded automatically when
present:

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
required files, internal link resolution including reference-style labels,
credential-shaped filenames, committed symbolic links, and optionally path naming
and the structure snapshot.

It deliberately does not check scope, boundaries, proportionality, or prose
quality. Those remain human and AI review responsibilities.
