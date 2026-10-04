# Maintaining repo-template

This document owns release preparation and publication for `repo-template`.
Ordinary changes follow [CONTRIBUTING.md](CONTRIBUTING.md). Repositories created
from this template should adapt this procedure to their own release needs.
Permission to contribute a change does not grant permission to publish a release.

## Release identifiers

Use versions `MAJOR.MINOR.PATCH` and matching Git tags `vMAJOR.MINOR.PATCH`, with
non-negative integer components and no leading zeroes. Increment MAJOR for
incompatible changes to the baseline's documented behavior or requirements,
MINOR for compatible additions, and PATCH for compatible fixes or clarifications.
Choose the version by reviewing the changes since the previous release and
their impact on consuming repositories.

Use the complete Git tag as the GitHub Release title, for example `v1.2.1`.
This is the template's default display convention; Semantic Versioning governs
version numbers, not release titles. Consumers may document a different local
title convention. The editable title does not replace the immutable tag or its
verified target.

Future formal releases must use **annotated Git tags**. A GitHub Release must
refer to the corresponding tag. Once published, release tags are immutable:
do not move, replace, or delete them. Corrections requiring a different commit
need a new version and tag.

The historical tags `v1.0.0` and `v1.0.1` are annotated; `v1.0.2` is lightweight.
This inconsistency predates this guidance. Preserve all existing published tags,
including `v1.0.2`; do not rewrite them to normalize tag type.

## Prepare the release

1. Fetch the current default branch (`main`) and tags from `origin`. Confirm
   that `origin` is `jamesreimer/repo-template` and the working tree is clean.
2. Choose an unused version under the release rules above. Check local and
   remote tags and existing
   [GitHub Releases](https://github.com/jamesreimer/repo-template/releases).
   Prepare a changelog update through the ordinary reviewed PR workflow before
   selecting the final release commit. Review every change since the previous
   release against the summaries retained in PR descriptions under the
   [contribution workflow](CONTRIBUTING.md#changelog), including summaries carried
   forward from earlier PRs. Verify that all notable changes are represented;
   resolve missing or unclear summaries with their authors and retained evidence.
   Do not reconstruct the changelog from scratch at release time.

   The release section may ship in the same PR as a release-bearing change when
   the intended version, release scope, and intended UTC publication date are
   established. In that path, complete this step's existing release-delta
   verification inside the same PR before merge, accounting for every change
   since the previous release against retained summaries. Earlier merged changes
   may cite canonical commits while the current same-PR change cites the PR.
   Mixed reference forms are acceptable when they accurately reflect publication
   state.

   Use the existing separate reviewed changelog-preparation path when version,
   scope, or intended UTC publication date is not established for the substantive
   PR, when that PR has already merged without the release section, or when a
   correction is needed after merge. Establish the release facts before preparing
   the section in that later PR. Aggregating several earlier changes does not
   itself require a separate changelog PR.

   Apply the [durable-reference guidance](CONTRIBUTING.md#changelog) according to
   the merge method used for the change:

   - With a merge commit, a substantive PR commit may be cited only when, before
     merge, the selected landing method and candidate state establish that it
     will survive unchanged in published history, and it is distinct from the
     commit adding the changelog entry. If the landing method or commit survival
     can still change, including through amendment or replacement, use the PR.
   - With a squash merge, the merge creates a new canonical commit. A same-PR
     entry uses the PR unless it refers to an earlier already-canonical change.
   - With a rebase merge that rewrites the original PR commit identities, a
     same-PR entry uses the PR unless it refers to an earlier already-canonical
     change.

   These cases do not require a particular merge method or change host settings.

   Follow [Common Changelog](https://common-changelog.org/): use a release heading
   such as `## [1.2.1] - 2026-09-23`, with the selected version without `v`, the
   intended UTC publication date in `YYYY-MM-DD`, and a link to its GitHub Release.
   For repo-template, the changelog date is the UTC calendar date of the GitHub
   Release `publishedAt` timestamp; verify it after publication as described below.
   Order releases newest first by semantic version. Use applicable `Changed`,
   `Added`, `Removed`, and `Fixed` groups in that order; write concise imperative
   entries with supporting links and mark breaking changes. Curate related
   summaries into the release delta. If publication is delayed or its scope
   changes before merge, correct the date, version, and entries in the same PR
   with proportionate re-review under the ordinary review process. This includes
   crossing UTC midnight when the intended publication day changes. If a mismatch
   is discovered after merge or publication, use the existing reviewed successor
   correction path. Validate the resulting merged commit again before tagging;
   preserve the post-publication date verification below. A prepared changelog
   section does not authorize publication.
3. Select the intended release commit from reviewed, merged work on `main`.
   Record its full commit SHA and check it out for validation. Review the changes
   since the previous release, including documentation, dependency updates, and
   effects on consumers. Verify that `CHANGELOG.md` covers the notable release
   delta and its version/date match the planned publication. Verify that any
   other repository-selected time-sensitive historical/evidence artifacts are
   current for this release candidate. Use
   those records as inputs to release preparation; keep their updates with the
   changes that create the historical facts, rather than making release time
   the default point for reconstructing history. Confirm repository CI passes
   for this commit.
4. Follow the [setup instructions](README.md#run-checks), then run:

   ```sh
   .venv/bin/pre-commit run --all-files --show-diff-on-failure
   git diff --check
   ```

   Require passing checks and a clean working tree. If checks fix files or a
   defect needs correction, submit the change through the contribution workflow
   and select and validate the resulting merged commit before proceeding.
5. Recheck that the chosen version is unused in local/remote tags and GitHub
   Releases. Prepare release notes summarizing the release delta from
   `CHANGELOG.md` and detailed Git, pull request, and issue evidence. Keep the
   notable changes consistent with the changelog and add release-specific
   consumer impact and adoption steps as needed. Keep the notes outside the
   checkout so it remains clean.

## Create and verify the tag

The commands below require Git and the GitHub CLI authenticated with release
permissions. Replace the placeholder values with the chosen tag, full validated
commit SHA, and release-notes file path. Stop if any command or verification
fails; do not proceed to publication.

```sh
tag='vMAJOR.MINOR.PATCH'
release_commit='<full validated commit SHA>'
notes_file='<path to prepared release notes>'
git fetch origin &&
  git merge-base --is-ancestor "$release_commit" origin/main
```

Require exit status zero before tagging. The ancestry check returns status 1
when the selected commit is not contained in the current `origin/main`.
A failed fetch or any other error also stops the release. Use the merged commit,
which may differ from the reviewed PR-head SHA after a squash merge.

```sh
git tag -a "$tag" "$release_commit" -m "repo-template $tag"
```

Verify both the tag object's type and the commit it resolves to:

```sh
test "$(git cat-file -t "refs/tags/$tag")" = tag &&
  test "$(git rev-parse "refs/tags/$tag^{commit}")" = "$release_commit"
```

Require exit status zero. The first test rejects a lightweight tag even when it
points to the correct commit; the second rejects a tag pointing to another
commit. Resolving a tag to a commit alone does not prove that it is annotated.

## Publish and verify

With release publication authorization, push only the verified tag, without
force, and publish its corresponding GitHub Release:

```sh
git push origin "refs/tags/$tag"
```

Before creating the GitHub Release, define and run this verification:

```sh
verify_remote_tag() {
  local_tag_object=$(git rev-parse "refs/tags/$tag") &&
    remote_tag=$(git ls-remote --exit-code origin "refs/tags/$tag") &&
    remote_commit=$(git ls-remote --exit-code origin "refs/tags/$tag^{}") &&
    test "$remote_tag" = "$(printf '%s\t%s' "$local_tag_object" "refs/tags/$tag")" &&
    test "$remote_commit" = "$(printf '%s\t%s' "$release_commit" "refs/tags/$tag^{}")"
}
verify_remote_tag
```

Require exit status zero. The comparisons require the remote tag object SHA to
match the local tag object and the remote peeled (`^{}`) SHA to match
`$release_commit`. `--exit-code` fails when a requested ref is missing, including
the peeled entry required for an annotated tag. Any failure stops publication;
investigate without overwriting a published tag.

```sh
gh release create "$tag" --repo jamesreimer/repo-template --verify-tag \
  --title "$tag" --notes-file "$notes_file"
gh release view "$tag" --repo jamesreimer/repo-template \
  --json url,tagName,name,isDraft,isPrerelease,publishedAt,body
verify_remote_tag
```

`--verify-tag` prevents implicit tag creation; it does not check tag type or
the intended commit, which the earlier checks establish. After publication,
confirm the release is published (not a draft or prerelease), its title follows
the naming convention above, its tag and notes
are correct, and its page and source archives are available. Recheck the remote
tag object and peeled commit against the same expected SHAs. If publication
fails after the tag push, inspect the remote tag and release state before
retrying; preserve the published tag.

Verify that the UTC calendar date of the release's actual `publishedAt`
timestamp matches its changelog heading. If it differs, record the discrepancy
and correct the changelog through the normal reviewed successor PR process.
Preserve the published tag and its tree; do not silently rewrite published
history. Any successor release still requires separate publication authorization.
