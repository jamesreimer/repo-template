# Maintaining the Template

This document describes how this repository — the template itself — is
maintained. It is not part of the baseline a project inherits.

Consumers: delete this file. A repository created from the template owns its
own release and maintenance practices, and nothing here is prescribed for it.

## Publishing a release

A release is how this repository is adopted. A consuming repository may pin a
baseline and verify it later, and `README.md` advertises the latest release, so
a release must carry enough identity to support that verification.

When publishing a release:

1. release only from a default-branch commit that has passed the checks
   described in [CONTRIBUTING.md](CONTRIBUTING.md#workflow);
2. create an annotated tag, signed where a signing key is available, so that
   the tag records its own tagger identity, date, and message; a lightweight
   tag holds none of these and silently borrows the tagged commit's metadata,
   leaving no record of who declared the release or when;
3. write the tag message to identify the release and state what changed since
   the previous one, rather than restating the subject of the tagged commit;
4. treat a published tag as immutable: do not move, delete, or recreate it,
   and supersede a mistaken release with a later one.

Tag names follow the existing `vMAJOR.MINOR.PATCH` form. This document does not
define a version-increment policy.

A consumer that records a consumed baseline should record the commit alongside
the tag: the commit is the binding identity and the tag is its human-facing
label. A tag name alone does not establish immutable consumption.
