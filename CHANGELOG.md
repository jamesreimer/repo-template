# Changelog

## [2.0.0] - 2026-10-10

_Known dependency advisories, including a high-severity `braces` advisory, remain under bounded, repository-specific risk acceptance in [#62](https://github.com/jamesreimer/repo-template/issues/62) and [#64](https://github.com/jamesreimer/repo-template/issues/64); the filename mitigation below does not patch dependencies or establish a clean npm audit._

### Changed

- **Breaking:** Require exactly Node.js 24.18.1 instead of `>=22.19.0`, install Markdown validation from the root npm lockfile with `npm ci --ignore-scripts`, and carry `.npmrc` with `engine-strict=true` so a Node engine mismatch fails installation instead of only warning; retain pre-commit orchestration, but replace its separate Markdown Node environment with install-time engine enforcement and subsequent execution through system `node` on PATH ([`083a106`](https://github.com/jamesreimer/repo-template/commit/083a10635c62e8544a0054f39661081fc6f7ef8d), [#75](https://github.com/jamesreimer/repo-template/pull/75))
- Clarify same-PR changelog preparation, durable references across merge methods, and reviewed corrections when the intended UTC publication date changes, while preserving release-delta verification and separate publication authorization ([`7525159`](https://github.com/jamesreimer/repo-template/commit/75251599d49baa89f8f9b2bdf2347b4c8682c903), [#58](https://github.com/jamesreimer/repo-template/pull/58))
- Choose GitHub issue-closing relationships according to substantive completion, distinguishing material post-merge obligations from routine housekeeping ([`1689599`](https://github.com/jamesreimer/repo-template/commit/16895990a2139747bba0d8a6622948e61b93e381), [#54](https://github.com/jamesreimer/repo-template/pull/54))

### Added

- **Breaking:** Add ESLint correctness checks and check-only Prettier formatting for JavaScript, JSON/JSONC, YAML, and Markdown, rejecting previously accepted files; adopt the dependencies and configuration together, review explicit formatting exclusions, and preserve Markdown prose wrapping and embedded examples ([`eb56488`](https://github.com/jamesreimer/repo-template/commit/eb56488ce1adc54ab7c51ac05d9cc67c4463b87a), [#76](https://github.com/jamesreimer/repo-template/pull/76))
- Require a repository-wide consumer specialization audit and completion evidence in the initialization handoff, including nested documentation and applicable live host settings; keep the procedure accessible while replacing the inherited README, without requiring a permanent report or ongoing upstream synchronization ([`4b91cc8`](https://github.com/jamesreimer/repo-template/commit/4b91cc8f79caf0d3eaba714d731604faee786735), [#78](https://github.com/jamesreimer/repo-template/pull/78))

### Removed

- **Breaking:** Remove Ruff Python linting and formatting, including Python code-block formatting, TOML syntax checking, and Python source/cache ignore defaults; retain Python for pre-commit and require consumers needing Python or TOML validation to select their own tooling ([`52dda02`](https://github.com/jamesreimer/repo-template/commit/52dda025a5bcd115eec9cfce274f1b6882ded167), [#67](https://github.com/jamesreimer/repo-template/pull/67))

### Fixed

- **Breaking:** Fail local-link validation when Linkinator cannot attest that the exact requested Markdown files were scanned, preventing glob or URL interpretation from producing false-green results; retain fail-closed limitations for some legal filenames documented in [#70](https://github.com/jamesreimer/repo-template/issues/70) ([`e58492c`](https://github.com/jamesreimer/repo-template/commit/e58492cd515091d38e2c47652eac98e78c497866), [#71](https://github.com/jamesreimer/repo-template/pull/71))
- Pass pre-commit Markdown filenames literally to Markdownlint so glob-like names are linted without filename-driven brace expansion; adopt the hook and adapter together, and assess manually supplied or configured globs separately ([`cf97424`](https://github.com/jamesreimer/repo-template/commit/cf974244a9e1c288b29d5d0444a14e5a5349cfc1), [#60](https://github.com/jamesreimer/repo-template/pull/60))

## [1.3.0] - 2026-09-29

### Added

- Add a Common Changelog history with supported backfill, independent consumer-history reset guidance, contribution-time summaries and PR prompting, and release preparation with UTC dates ([`f38ea7e`](https://github.com/jamesreimer/repo-template/commit/f38ea7e2b46769903f6653cf52d06021de3a6e5c), [#49](https://github.com/jamesreimer/repo-template/pull/49))

### Fixed

- Account for deferral cost and evidence loss in bootstrap/addition decisions, and require contemporaneous recording when delay weakens historical interpretation ([`4af4136`](https://github.com/jamesreimer/repo-template/commit/4af413673f24c1a367e08a546ee8fabd65b5d76b), [#47](https://github.com/jamesreimer/repo-template/pull/47))

## [1.2.1] - 2026-09-23

### Changed

- Use the complete version tag as the default GitHub Release title and verify it after publication ([`de0fd92`](https://github.com/jamesreimer/repo-template/commit/de0fd9206cf0448d50e0dd0f58f858eea46697ad), [#44](https://github.com/jamesreimer/repo-template/pull/44))

## [1.2.0] - 2026-09-23

### Added

- Add an installable default-branch ruleset requiring up-to-date, validated squash PRs and resolved review conversations, with deliberate installation and verification guidance ([`90d3b5a`](https://github.com/jamesreimer/repo-template/commit/90d3b5a6324bfcff6e9bb1b24de02d3677b73f93), [#42](https://github.com/jamesreimer/repo-template/pull/42))

## [1.1.0] - 2026-09-23

### Added

- Add release-maintenance guidance covering version selection, immutable annotated tags, exact local and remote tag verification, and authorized publication ([`4f848f2`](https://github.com/jamesreimer/repo-template/commit/4f848f29e9021a9f9b19a81a3a83436113880d97), [#39](https://github.com/jamesreimer/repo-template/pull/39))

## [1.0.2] - 2026-09-21

### Changed

- Simplify the link regression contract documentation and remove unused fixture metadata while preserving active coverage; update the contract and digest-pinned runner together when adopting ([`b79d8d0`](https://github.com/jamesreimer/repo-template/commit/b79d8d0f14b26a2c6414a016b9501853e68f4670), [#36](https://github.com/jamesreimer/repo-template/pull/36))

## [1.0.1] - 2026-09-21

### Fixed

- Accept local directory links without requiring `index.html`, while still rejecting missing directories; use explicit files when fragment validation is needed ([`4877171`](https://github.com/jamesreimer/repo-template/commit/4877171f3a45ed98645e8be7af8fa5e32e5b6a90), [#32](https://github.com/jamesreimer/repo-template/pull/32))

## [1.0.0] - 2026-09-20

_First stable adoption baseline._

[2.0.0]: https://github.com/jamesreimer/repo-template/releases/tag/v2.0.0
[1.3.0]: https://github.com/jamesreimer/repo-template/releases/tag/v1.3.0
[1.2.1]: https://github.com/jamesreimer/repo-template/releases/tag/v1.2.1
[1.2.0]: https://github.com/jamesreimer/repo-template/releases/tag/v1.2.0
[1.1.0]: https://github.com/jamesreimer/repo-template/releases/tag/v1.1.0
[1.0.2]: https://github.com/jamesreimer/repo-template/releases/tag/v1.0.2
[1.0.1]: https://github.com/jamesreimer/repo-template/releases/tag/v1.0.1
[1.0.0]: https://github.com/jamesreimer/repo-template/releases/tag/v1.0.0
