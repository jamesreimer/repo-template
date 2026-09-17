# Agent Guidance

This file describes repository mechanics. It is not a governance standard and
does not grant authority.

## Local authority

> **Consumers: replace this section.** List the authority that actually governs
> work in your repository — adopted standards, a program record, an authority
> index, or nothing at all. Route agents to it here.

No governing standards are adopted here. Work in this repository is governed
by this file and [CONTRIBUTING.md](CONTRIBUTING.md).

Where a consuming repository has adopted standards, those govern within their
assigned scope. Do not invent a parallel rule, workflow, taxonomy, or authority
model where an existing one already applies, and do not import authority from
another repository merely because it is available or because a file happens to
be present.

### Recommended adoption candidate

This template's own design was worked out by applying the Architectural
Reasoning Standard, which is domain-neutral and governs how work is reasoned
about rather than any particular subject. It is a good candidate for
repositories that do not already govern architectural reasoning:

<https://github.com/jamesreimer/standards-templates/blob/8eafbc58279d265908d75ae784c8df1927063c12/templates/architectural-reasoning/standard.md>

Adopting it is a deliberate decision belonging to the consuming repository or
its organization, made through whatever adoption process that organization
uses. This template does not bundle it, and copying this template does not
adopt it.

## Before planning or editing

- Inspect the current branch and worktree first. Preserve unrelated changes;
  do not revert work you did not make.
- Read [CONTRIBUTING.md](CONTRIBUTING.md) and any local authority listed above.
- Identify whether the request changes repository structure, the baseline file
  set, or the validation model.
- Determine whether the work touches sibling repositories, infrastructure,
  deployment, secrets, or production systems. If it may, stop and confirm the
  required authority before executing.

## Proportional reasoning

Match the depth of analysis to what the change can break. Correcting a typo,
adjusting a comment, or fixing an obviously wrong value needs no deliberation
beyond getting it right. Changing the baseline file set, the validation model,
or repository structure affects every repository that adopts this one, and
deserves a stated reason before implementation.

Two questions are worth asking before adding anything:

- What concrete problem does this solve, and where has that problem actually
  occurred? An anticipated problem is not evidence.
- If this were added later instead, what would that cost? If the answer is
  "almost nothing," add it later.

A control or check is subject to the same test as the thing it protects. A
check that rejects correct work, or that costs more attention than the defect
it catches, is a defect in its own right rather than a reason to add another
layer around it.

## Tooling

Repository tooling is Python, using only the standard library, targeting the
version floor stated in [README.md](README.md). Use shell only where the shell
is itself the interface, such as a Git hook shim.

Do not add a package manager, dependency, or runtime to this repository solely
to support repository tooling.

## Implementation lifecycle

1. Work on a bounded branch following the naming convention in
   [CONTRIBUTING.md](CONTRIBUTING.md). Keep unrelated work out of its commits.
2. Run the validation below and open a reviewable pull request stating scope,
   validation evidence, and any unresolved questions.
3. Confirm the merge before cleanup. Delete merged local branches only after
   verifying their work is present on the default branch and that no unique
   work would be lost.
4. Report merge identity, branch cleanup, and anything left unresolved.

## Validation and completion

- Run `python3 -m unittest discover -s tests` and `python3 scripts/validate.py`.
- Run the supplemental checks in [CONTRIBUTING.md](CONTRIBUTING.md) when the
  files they cover have changed, along with `git diff --check`.
- Regenerate `repository-structure.txt` only for an intentional structural
  change, by running `python3 scripts/update_repository_structure.py`.
- Automated validation covers mechanical invariants only. Scope, boundaries,
  and prose quality remain review responsibilities. A green check is not a
  statement that the change is correct.
