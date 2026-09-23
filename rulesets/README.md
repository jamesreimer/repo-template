# Default-branch ruleset

[default-branch.json](default-branch.json) is the reusable GitHub configuration
for this template. It targets the repository's default branch and supplies:

- Active protection against branch deletion and force pushes.
- Pull requests with squash-only merges and resolved review conversations.
- Zero required approving reviews, without bypass actors.
- A required `Repository validation` check from GitHub Actions, with the branch
  up to date before merging. Check enforcement also applies on branch creation.

Zero required approvals does not waive a project's separately required review.
Consumers own their host settings and may deliberately adapt this baseline to
their actual requirements, preserving any additional local protections.

## Before installation

Copying this file or creating a repository from the template does not install
the ruleset. Repository validation checks the JSON syntax; it does not query
GitHub or establish that the live branch is protected. Later template changes
also require deliberate host reconciliation; there is no automatic propagation.

Use an authorized administrative account and the GitHub CLI with `jq` available.
Confirm rulesets are supported for the repository's plan and visibility using
[GitHub's ruleset guidance](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets).
Run the commands from the checkout root. Set `repo` to the intended repository
and `evidence` to a new directory outside the checkout for snapshots:

```sh
repo='OWNER/REPOSITORY'
evidence='/absolute/path/to/new-ruleset-evidence'
mkdir "$evidence"
gh api "repos/$repo" --jq '{full_name, default_branch, permissions}'
gh api --paginate "repos/$repo/rulesets" > "$evidence/rulesets-before.json"
```

Stop on any failed command. Verify the identity and administrative permission,
then inspect all applicable rulesets (including inherited ones) and legacy
branch protection in GitHub. Do not replace or duplicate an existing rule
merely because its name differs. Preserve additional checks and restrictions.

Before requiring CI, ensure the default branch and validation workflow already
exist. Inspect a recent successful check run on a known full commit SHA:

```sh
check_sha='<full validated commit SHA>'
gh api --paginate "repos/$repo/commits/$check_sha/check-runs" \
  --jq '.check_runs[] | {name, conclusion, app: {id: .app.id, slug: .app.slug}}'
```

Confirm `Repository validation` is produced by `github-actions` with app ID
`15368` on github.com. Verify the app ID on other GitHub hosts before adapting
the JSON. The [supplied workflow](../.github/workflows/validate.yml) runs for
every pull request without path filters. Keep that coverage when requiring its
check; a renamed job or skipped workflow can leave merges blocked. Reconcile
workflow and host settings together when changing the check contract.

## Create or update deliberately

Prepare a reviewed payload from the published baseline. Record its immutable
source commit and any adaptations in the adopting project's change record.

```sh
cp rulesets/default-branch.json "$evidence/desired.json"
```

If an applicable repository ruleset already exists, record its actual ID and
save its current state. Adapt `desired.json` to preserve additional local
protections before proceeding; PUT replaces the supplied rule configuration.
Coordinate administrative edits, refresh the snapshot immediately before the
write, and stop to reconcile any concurrent change rather than overwriting it.

```sh
ruleset_id='<existing repository ruleset ID>'
gh api "repos/$repo/rulesets/$ruleset_id" > "$evidence/before.json"
# Review before.json against desired.json before running the update.
gh api --method PUT "repos/$repo/rulesets/$ruleset_id" \
  --input "$evidence/desired.json" > "$evidence/applied.json"
```

Only when no corresponding rule exists, create one and retain its returned ID:

```sh
gh api --method POST "repos/$repo/rulesets" \
  --input "$evidence/desired.json" > "$evidence/applied.json"
ruleset_id=$(jq -er '.id' "$evidence/applied.json")
```

## Verify and retain evidence

Read back the persisted rule separately from the mutation response. Compare the
writable fields, sorting rules to avoid differences in API ordering:

```sh
gh api "repos/$repo/rulesets/$ruleset_id" > "$evidence/after.json"
fields='{name, target, enforcement, bypass_actors, conditions, rules: (.rules | sort_by(.type))}'
jq -S "$fields" "$evidence/desired.json" > "$evidence/expected.json"
jq -S "$fields" "$evidence/after.json" > "$evidence/actual.json"
diff -u "$evidence/expected.json" "$evidence/actual.json"
```

Require equality or resolve and document any server-added defaults before
claiming correspondence. Recheck all effective default-branch protections in
GitHub, including other rulesets and legacy branch protection. Inspect an actual
pull request's check and merge requirements; do not merge it just to test rules.
Retain the source revision, rule ID, adaptations, before/after evidence and
verification outcome in the project's change record.

If an update or verification fails, stop and inspect current host state before
retrying. Keep the snapshots. Do not delete/recreate the ruleset or add bypass
actors to recover. A correction or restoration through the same API needs
appropriate authority, especially when it would weaken protection; prepare a
reviewed payload from the saved writable fields, preserving unrelated changes,
and repeat read-back verification. A local JSON file alone is never proof of
successful installation or recovery.
