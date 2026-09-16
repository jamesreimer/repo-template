# Repository Template

A technology-neutral baseline for repository hygiene, contributor and agent
guidance, and lightweight mechanical validation.

This repository owns **repository mechanics**. It does not own governance
standards, normative content, or any language, framework, or deployment
scaffolding.

## What it provides

| Area | Files |
| --- | --- |
| Encoding and line endings | `.editorconfig`, `.gitattributes`, `.vscode/settings.json` |
| Ignore rules | `.gitignore` |
| Markdown hygiene | `.markdownlint-cli2.jsonc` |
| Python tooling lint | `ruff.toml` |
| Mechanical validation | `validate.json`, `scripts/validate.py`, `tests/` |
| Structure snapshot | `repository-structure.txt`, `scripts/update_repository_structure.py` |
| Local hooks | `.githooks/pre-commit`, `scripts/setup_git_hooks.py` |
| Continuous integration | `.github/workflows/validate.yml`, `.github/dependabot.yml` |
| Contributor and agent entry points | `CONTRIBUTING.md`, `AGENTS.md`, `SECURITY.md` |
| Host branch protection | `rulesets/default-branch.json` |

## Non-goals

This repository does not provide language runtimes or framework scaffolding,
package manifests, deployment, container, or infrastructure files, release or
changelog policy, downstream synchronization machinery, or validators for
subjective judgment.

It carries no governance standards, adopted or authored. A repository's
governing authority is its own decision, made through whatever adoption process
its organization uses. Bundling a standard with repository mechanics would let
it enter an organization as a side effect of wanting line-ending configuration,
which is not adoption. [AGENTS.md](AGENTS.md) names a recommended candidate
without shipping it.

Consuming repositories keep their own authority. Adopting this baseline does
not make this repository authoritative for them.

## Design principle

Add a file, check, or automation only when a concrete need has been
demonstrated. Conventionality is not a justification. A baseline that grows
faster than its demonstrated need stops being a baseline.

## Requirements

Python 3.9 or later, from the standard library alone. No packages are
installed to run validation locally. The floor is deliberately low so that
`python3 scripts/validate.py` works on a machine with only the system Python,
including stock macOS.

Markdown, Python lint, and workflow linting run in CI through pinned actions.

## Validation

```bash
python3 -m unittest discover -s tests
```

```bash
python3 scripts/validate.py
```

Optionally enable the version-controlled pre-commit hook:

```bash
python3 scripts/setup_git_hooks.py
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the configuration reference and the
full local check list.

## Adoption

Copy the files into the consuming repository according to the classification
below, then write a `validate.json` describing which checks that repository
wants.

| Class | Meaning | Files |
| --- | --- | --- |
| **Baseline** | Copy substantially unchanged | `.editorconfig`, `.gitattributes`, `.markdownlint-cli2.jsonc`, `.vscode/settings.json`, `.githooks/pre-commit`, `scripts/validate.py`, `scripts/update_repository_structure.py`, `scripts/setup_git_hooks.py`, `tests/`, `.github/dependabot.yml` |
| **Adapt** | Copy, then customize | `.gitignore`, `AGENTS.md`, `CONTRIBUTING.md`, `SECURITY.md`, `README.md`, `ruff.toml`, `validate.json`, `.github/workflows/validate.yml`, `.github/pull_request_template.md` |
| **Local** | Author for your repository rather than copying | `LICENSE`, `scripts/validate_local.py` |
| **Generated** | Produce with the tooling; never copy this repository's artifact | `repository-structure.txt` |
| **Optional host configuration** | Install deliberately; copying the file alone has no effect | `rulesets/default-branch.json` |

File disposition and feature activation are different axes. The Git hook files
are Baseline — copy them unchanged — while running
`python3 scripts/setup_git_hooks.py` to activate them is optional.

`scripts/` is deliberately split across two classes. The three scripts above are
Baseline and should not diverge between repositories. `scripts/validate_local.py`
is Local: it does not exist here, and each repository that needs one writes its
own.

`scripts/validate.py` is intended to stay byte-identical across consumers.
Repository-specific checks belong in `scripts/validate_local.py`, never in a
fork of the validator. If a consumer cannot express a check that way, that is a
defect in this template and belongs here.

Recording provenance is recommended but not required: note the source
repository and the commit adopted from, so a later change here can be reviewed
deliberately. Changes here are review candidates, never automatic downstream
updates. This repository provides no synchronization mechanism.

## Host-side settings

Everything above describes files inside Git. A repository's behavior also
depends on state held by its host: default branch, merge methods, branch
protection, required checks, deletion of merged branches, vulnerability
reporting, and Actions permissions. That state is not established by copying
files, and this template does not manage it.

`rulesets/default-branch.json` is the one exception, and only partly. It is a
desired configuration expressed as a file:

> **A checked-in ruleset is not evidence that a branch is protected.** The
> effective configuration lives at the host, behind authentication. Unlike every
> other file here, `scripts/validate.py` cannot verify it, and deliberately does
> not try — adding authenticated network access to an offline validator would
> cost more than the check is worth.

Repository rulesets are not available on every plan and visibility combination.
Private repositories require a paid plan — Pro for a user account, Team or
Enterprise for an organization — and organizations on GitHub Free can apply
rulesets only to public repositories. This is the only file here with a billing
dependency: every other file works for anyone who copies it, while this one may
not be installable at all, and nothing in the repository will say so. Confirm
availability before relying on it. A repository that cannot install it should
treat branch protection as an unmet requirement rather than assume the file
provides one.

Install it deliberately, then confirm the result at the host:

```bash
gh api --method POST repos/OWNER/REPO/rulesets --input rulesets/default-branch.json
```

The ruleset protects the default branch by blocking deletion and
non-fast-forward pushes, requiring a pull request with squash merge, and
declaring no bypass actors. It requires zero approvals, because a single
maintainer approving their own pull request is ceremony rather than review.

It deliberately does **not** require a status check. Doing so would couple the
ruleset to the exact job name in `.github/workflows/validate.yml`; renaming that
job would leave every pull request waiting on a check that never reports. A
repository that wants CI as a merge precondition should add that rule after
confirming its own stable check context.

Access, review, merge, deployment, and authority policies beyond this remain the
consuming repository's responsibility.

## License

Released under CC0 1.0 Universal. See [LICENSE](LICENSE).
