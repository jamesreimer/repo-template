# Repository Template

[![Repository validation](https://github.com/jamesreimer/repo-template/actions/workflows/validate.yml/badge.svg?branch=main)](https://github.com/jamesreimer/repo-template/actions/workflows/validate.yml?query=branch%3Amain)
[![Latest release](https://img.shields.io/github/v/release/jamesreimer/repo-template)](https://github.com/jamesreimer/repo-template/releases/latest)
[![License: CC0](https://img.shields.io/badge/license-CC0-blue)](LICENSE)
[![Node.js: 24.18.1](https://img.shields.io/badge/Node.js-24.18.1-green)](#run-checks)
[![Python: >=3.10](https://img.shields.io/badge/Python-%3E%3D3.10-blue)](#run-checks)

A reusable starting point for Git repositories, with contributor guidance and
maintained tools for common file checks. It does not prescribe an application
language, directory layout, deployment system, or organizational governance.

## Start a repository

1. Create a repository from this template or copy the files you need.
2. Replace this README with the project's purpose and usage instructions.
3. Review and adapt `LICENSE`, `SECURITY.md`, `CONTRIBUTING.md`, `AGENTS.md`, and
   [MAINTAINING.md](MAINTAINING.md) for the new project's actual ownership,
   reporting route, working practices, and release procedure.
4. Adapt the checks and ignore patterns to the project's files and requirements.
5. Configure repository permissions and branch protection on your Git host.
   For GitHub, deliberately install and verify the
   [default-branch ruleset](rulesets/README.md). Copying template files does not
   configure live rules. The supplied required job is **Repository validation**.

The template is released under [CC0](LICENSE). Choose the appropriate license
for your project's own content deliberately.

## Run checks

Install Python 3.10 or later and Node.js 24.18.1 (including npm). Then:

```sh
npm ci --ignore-scripts
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/pre-commit run --all-files --show-diff-on-failure
```

On Windows, use `.venv\Scripts\python.exe` and
`.venv\Scripts\pre-commit.exe` instead. Initial setup downloads isolated hook
environments and requires network access. Link checking itself is offline.

The same pre-commit configuration runs locally and in CI. Checks may fix
whitespace or formatting; review those changes and rerun. `--all-files` checks
Git-tracked files, so stage new files before running it.

Optionally run checks when committing:

```sh
.venv/bin/pre-commit install
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for maintenance and validation details.

## What is checked

| Responsibility | Tool |
| --- | --- |
| Merge markers, file endings, trailing whitespace, and mixed line endings | pre-commit-hooks |
| JSON, YAML, and TOML syntax | pre-commit-hooks |
| Case-colliding paths and broken symlinks | pre-commit-hooks |
| Recognizable private-key content | pre-commit-hooks |
| Selected Markdown structure, syntax, and reference rules | markdownlint-cli2 |
| Local Markdown link destinations and fragments | Linkinator |
| Python lint and formatting, when Python files are present | Ruff |
| GitHub Actions workflow syntax and expressions | actionlint |

Private-key detection is limited; it is not a comprehensive secret scanner.
External URLs are not checked. Offline link checking does not render a website
or resolve a framework's routes. Projects with generated pages or special URL
semantics should configure checks against the appropriate source or build.

Markdown rules are selected explicitly in `.markdownlint-cli2.jsonc`. These
are editable defaults, not a claim that every flagged document is invalid
Markdown. Both ATX (`#`) and Setext headings are supported; there is no required
heading style, first heading, single-H1 rule, or prose line-length limit.

One local authoring rule requires explicit closing code fences. Although
CommonMark permits implicit closure, a forgotten closer can absorb intended
prose and prevent its links from being checked. `fenced-code-closed` uses
markdownlint's existing parser tokens and reports the opening line. It does not
autofix because the intended closing position requires the author's judgment.

## Ownership and standards

This repository owns the reusable baseline. A repository created from it owns
its copy and may change its files, tooling, and defaults. There is no obligation
to maintain byte-identical files or synchronize later template revisions.

Standards have a separate role: explicitly adopted standards govern within
their assigned scope. The baseline does not override them, and a standard's
source location does not automatically confer authority over another repository.
Record the standards that actually apply in the consuming repository's existing
authority entry point and route contributors to it from `AGENTS.md`.

The [standards template library](https://github.com/jamesreimer/standards-templates)
provides adoption candidates covering architectural reasoning, standards
adoption, repository responsibility, operational execution, work identification,
naming, shared assets, and domain-specific subjects. Consider each relevant
responsibility and any existing governing standards; architectural reasoning
is not a substitute for the other subjects. Linking to the library does not
adopt its contents, and using this template does not adopt any of them.

No separate provenance document is required by this template. Keep attribution,
license notices, and dependency identities where they serve their actual purpose
or are required by applicable terms or adopted standards.

## Design choices

Established tools own their parsing and validation domains. This template ships
configuration and one tested parser-backed authoring rule, without a custom
validation engine, extension API, or generated tree snapshot. Add project tests
and domain-specific checks when the project needs them, using the existing
runner or its own build system.

Evaluate additions against a concrete need and their maintenance cost for
consuming repositories. Revise defaults that obstruct a project's requirements
rather than treating their presence in the template as proof they are necessary.
