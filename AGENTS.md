# Agent Guidance

## Authority and scope

Read [README.md](README.md) and [CONTRIBUTING.md](CONTRIBUTING.md) before changing
this baseline. No external standards are adopted by this template.

Consumers: replace this paragraph with links to your actual governing standards
or authority entry point, if any. Route work to every applicable standard within
its scope; do not assume architectural reasoning governs adoption, execution,
naming, repository responsibility, or shared-asset maintenance. Do not import
authority merely because a document is available or supplied by another repo.

Repository configuration expresses implementation choices. When a choice
obstructs an authorized requirement, evaluate and correct it within the granted
scope. Distinguish that from changing a governing requirement or another
repository's responsibilities. Existing authorization remains relevant; the
presence of an old rule is not itself a reason to request permission again.

## Working practices

- Inspect the branch and worktree; preserve unrelated work.
- Keep changes within the user's authorized scope. Do not infer permission to
  deploy, merge, or modify sibling repositories from permission to edit here.
- For substantive changes, identify the requirement, affected responsibilities,
  consumer impact, and evidence needed to establish correctness.
- Prefer maintained tools to custom parsers and validation frameworks. Add a
  dependency, file, or control only for a concrete benefit worth its upkeep.
- Evaluate findings on their merits. A non-blocking classification alone does
  not justify deferral; neither does it require unrelated cleanup.
- Use a descriptive work branch and prepare a reviewable pull request. Do not
  delete branches until their work is verified as merged or otherwise preserved.

## Validation

Stage intended new files so the runner sees them, then run:

```sh
.venv/bin/pre-commit run --all-files --show-diff-on-failure
git diff --check
```

For changes to checks, exercise representative valid and invalid files in an
isolated test repository. Report what was checked and any limitations. Automated
checks establish their specific mechanical properties, not overall correctness,
authority, prose quality, or permission to publish.
