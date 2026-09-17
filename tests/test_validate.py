"""Unit tests for the mechanical repository validator."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from validate import (  # noqa: E402
    ConfigError,
    enumerate_repository_files,
    glob_to_regex,
    heading_slug,
    load_config,
    parse_destination,
    render_repository_structure,
    validate_repository,
)


class RepositoryTestCase(unittest.TestCase):
    """Build a throwaway repository tree and run the validator over it."""

    def build(self, files, config=None):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        for relative_path, content in files.items():
            path = root / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, bytes):
                path.write_bytes(content)
            else:
                path.write_text(content, encoding="utf-8")
        if config is not None:
            (root / "validate.json").write_text(
                json.dumps(config, indent=2) + "\n", encoding="utf-8"
            )
        return root

    def reasons(self, root):
        return [finding.reason for finding in validate_repository(root)]

    def checks(self, root):
        return [finding.check for finding in validate_repository(root)]


class GlobTranslationTests(unittest.TestCase):
    def test_double_star_matches_root_and_nested(self):
        pattern = glob_to_regex("**/*.md")
        self.assertTrue(pattern.match("README.md"))
        self.assertTrue(pattern.match("docs/guide.md"))
        self.assertTrue(pattern.match("a/b/c/deep.md"))

    def test_single_star_does_not_cross_separators(self):
        pattern = glob_to_regex("scripts/*.py")
        self.assertTrue(pattern.match("scripts/validate.py"))
        self.assertFalse(pattern.match("scripts/nested/validate.py"))

    def test_literal_dots_are_escaped(self):
        pattern = glob_to_regex("**/.env")
        self.assertTrue(pattern.match(".env"))
        self.assertFalse(pattern.match("xenv"))


class HeadingSlugTests(unittest.TestCase):
    def test_lowercases_and_hyphenates(self):
        self.assertEqual(heading_slug("Repository Architecture"), "repository-architecture")

    def test_drops_punctuation_and_formatting(self):
        self.assertEqual(heading_slug("What's **new**, really?"), "whats-new-really")

    def test_preserves_code_span_text(self):
        self.assertEqual(heading_slug("`validate.py` options"), "validatepy-options")


class DestinationParsingTests(unittest.TestCase):
    def test_strips_angle_brackets(self):
        self.assertEqual(parse_destination("<docs/a.md>"), "docs/a.md")

    def test_strips_trailing_title(self):
        self.assertEqual(parse_destination('docs/a.md "A title"'), "docs/a.md")


class JunkArtifactTests(RepositoryTestCase):
    def test_reports_junk_file(self):
        root = self.build({"README.md": "# Title\n", ".DS_Store": "junk\n"})
        self.assertIn("junk artifact is not allowed", self.reasons(root))

    def test_reports_file_in_junk_directory(self):
        root = self.build({"README.md": "# Title\n", "scripts/__pycache__/a.txt": "x\n"})
        self.assertIn("file lives in a junk artifact directory", self.reasons(root))

    def test_clean_tree_is_silent(self):
        root = self.build({"README.md": "# Title\n"})
        self.assertEqual(self.reasons(root), [])


class TextEncodingTests(RepositoryTestCase):
    def test_reports_invalid_utf8(self):
        root = self.build({"README.md": b"# Title\n\xff\xfe\n"})
        self.assertTrue(any("not valid UTF-8" in reason for reason in self.reasons(root)))

    def test_ignores_binary_extensions(self):
        root = self.build({"README.md": "# Title\n", "logo.png": b"\x89PNG\r\n\x1a\n\xff"})
        self.assertEqual(self.reasons(root), [])


class FinalNewlineTests(RepositoryTestCase):
    def test_reports_missing_final_newline(self):
        root = self.build({"README.md": "# Title"})
        self.assertIn("text file must end with a newline", self.reasons(root))

    def test_empty_file_is_allowed(self):
        root = self.build({"README.md": "# Title\n", "placeholder.txt": ""})
        self.assertEqual(self.reasons(root), [])


class RequiredFileTests(RepositoryTestCase):
    def test_reports_missing_required_file(self):
        root = self.build(
            {"README.md": "# Title\n"},
            config={"required-files": {"paths": ["LICENSE"]}},
        )
        self.assertIn("required baseline file is missing", self.reasons(root))

    def test_present_required_file_passes(self):
        root = self.build(
            {"README.md": "# Title\n", "LICENSE": "CC0\n"},
            config={"required-files": {"paths": ["LICENSE"]}},
        )
        self.assertEqual(self.reasons(root), [])


class CredentialFileTests(RepositoryTestCase):
    def test_reports_committed_env_file(self):
        root = self.build({"README.md": "# Title\n", ".env": "SECRET=1\n"})
        self.assertIn("credential-shaped file must not be committed", self.reasons(root))

    def test_allows_env_example(self):
        root = self.build({"README.md": "# Title\n", ".env.example": "SECRET=\n"})
        self.assertEqual(self.reasons(root), [])

    def test_reports_private_key(self):
        root = self.build({"README.md": "# Title\n", "deploy/server.pem": "key\n"})
        self.assertIn("credential-shaped file must not be committed", self.reasons(root))

    def test_allows_public_key(self):
        root = self.build({"README.md": "# Title\n", "deploy/id_ed25519.pub": "key\n"})
        self.assertEqual(self.reasons(root), [])


class PathNameTests(RepositoryTestCase):
    def test_disabled_by_default(self):
        root = self.build({"README.md": "# Title\n", "src/SiteHeader.tsx": "x\n"})
        self.assertEqual(self.reasons(root), [])

    def test_reports_when_enabled(self):
        root = self.build(
            {"README.md": "# Title\n", "src/SiteHeader.tsx": "x\n"},
            config={
                "path-names": {
                    "enabled": True,
                    "pattern": "^\\.?[a-z0-9][a-z0-9._-]*$",
                    "exempt": ["README.md"],
                }
            },
        )
        self.assertTrue(any("does not match" in reason for reason in self.reasons(root)))

    def test_exempt_paths_are_skipped(self):
        root = self.build(
            {"README.md": "# Title\n"},
            config={
                "path-names": {
                    "enabled": True,
                    "pattern": "^[a-z]+$",
                    "exempt": ["README.md", "validate.json"],
                }
            },
        )
        self.assertEqual(self.reasons(root), [])


class SymlinkTests(RepositoryTestCase):
    def test_committed_symlink_is_rejected(self):
        root = self.build({"README.md": "# Title\n", "notes.md": "# Notes\n"})
        (root / "link.md").symlink_to(root / "notes.md")
        self.assertIn(
            "symbolic link must not be committed; the link target was not read",
            self.reasons(root),
        )

    def test_symlink_to_target_outside_repository_is_rejected(self):
        root = self.build({"README.md": "# Title\n"})
        (root / "escape.md").symlink_to(Path("/etc/passwd"))
        reasons = self.reasons(root)
        self.assertIn("symbolic link must not be committed; the link target was not read", reasons)
        # The target must never be read, so no encoding or newline finding can
        # be raised about the content on the other side of the link.
        self.assertNotIn("file is not valid UTF-8", " ".join(reasons))
        self.assertNotIn("text file must end with a newline", reasons)

    def test_broken_symlink_is_rejected_without_resolution_error(self):
        root = self.build({"README.md": "# Title\n"})
        (root / "dangling.md").symlink_to(root / "does-not-exist.md")
        self.assertIn(
            "symbolic link must not be committed; the link target was not read",
            self.reasons(root),
        )

    def test_symlinked_directory_is_rejected(self):
        root = self.build({"README.md": "# Title\n", "real/page.md": "# Page\n"})
        (root / "alias").symlink_to(root / "real", target_is_directory=True)
        self.assertIn(
            "symbolic link must not be committed; the link target was not read",
            self.reasons(root),
        )

    def test_symlink_check_is_unconditional(self):
        root = self.build(
            {"README.md": "# Title\n"},
            config={"junk-artifacts": {"enabled": False}, "text-encoding": {"enabled": False}},
        )
        (root / "link.md").symlink_to(root / "README.md")
        self.assertIn("symlinks", self.checks(root))

    def test_ordinary_files_produce_no_symlink_finding(self):
        root = self.build({"README.md": "# Title\n", "docs/page.md": "# Page\n"})
        self.assertNotIn("symlinks", self.checks(root))


class MarkdownLinkTests(RepositoryTestCase):
    def test_reports_missing_target(self):
        root = self.build({"README.md": "# Title\n\n[gone](docs/missing.md)\n"})
        self.assertTrue(any("does not exist" in reason for reason in self.reasons(root)))

    def test_resolves_relative_target(self):
        root = self.build(
            {
                "README.md": "# Title\n\n[guide](docs/guide.md)\n",
                "docs/guide.md": "# Guide\n\n[home](../README.md)\n",
            }
        )
        self.assertEqual(self.reasons(root), [])

    def test_reports_unknown_anchor(self):
        root = self.build({"README.md": "# Title\n\n[jump](#nowhere)\n"})
        self.assertTrue(any("does not match a heading" in reason for reason in self.reasons(root)))

    def test_accepts_known_anchor(self):
        root = self.build({"README.md": "# Title\n\n## Real Section\n\n[jump](#real-section)\n"})
        self.assertEqual(self.reasons(root), [])

    def test_ignores_external_links(self):
        root = self.build({"README.md": "# Title\n\n[ext](https://example.com/a.md)\n"})
        self.assertEqual(self.reasons(root), [])

    def test_ignores_links_inside_fenced_code(self):
        root = self.build({"README.md": "# Title\n\n```\n[gone](docs/missing.md)\n```\n"})
        self.assertEqual(self.reasons(root), [])

    def test_reports_repository_absolute_link(self):
        root = self.build({"README.md": "# Title\n\n[abs](/docs/guide.md)\n"})
        self.assertTrue(any("repository-absolute" in reason for reason in self.reasons(root)))

    def test_duplicate_headings_get_suffixed_anchors(self):
        content = "# Title\n\n## Notes\n\n## Notes\n\n[second](#notes-1)\n"
        root = self.build({"README.md": content})
        self.assertEqual(self.reasons(root), [])


class StructureSnapshotTests(RepositoryTestCase):
    def test_reports_stale_snapshot(self):
        root = self.build(
            {"README.md": "# Title\n", "repository-structure.txt": "stale\n"},
            config={"structure-snapshot": {"enabled": True}},
        )
        self.assertTrue(any("out of date" in reason for reason in self.reasons(root)))

    def test_generated_snapshot_matches(self):
        root = self.build(
            {"README.md": "# Title\n", "docs/guide.md": "# Guide\n"},
            config={"structure-snapshot": {"enabled": True}},
        )
        paths = set(enumerate_repository_files(root))
        paths.add("repository-structure.txt")
        (root / "repository-structure.txt").write_text(
            render_repository_structure(sorted(paths)), encoding="utf-8"
        )
        self.assertEqual(self.reasons(root), [])

    def test_renders_directories_and_files(self):
        rendered = render_repository_structure(["README.md", "src/nested/b.ts"])
        self.assertIn("src/", rendered)
        self.assertIn("src/nested/", rendered)
        self.assertIn("src/nested/b.ts", rendered)
        self.assertIn("README.md", rendered)


class ConfigTests(RepositoryTestCase):
    def test_underscore_keys_are_ignored(self):
        root = self.build(
            {"README.md": "# Title\n"},
            config={"_note": "a comment", "required-files": {"_why": "x", "paths": []}},
        )
        self.assertEqual(self.reasons(root), [])

    def test_unknown_check_is_reported(self):
        root = self.build({"README.md": "# Title\n"}, config={"nonsense": {"enabled": True}})
        self.assertTrue(any("unknown check" in reason for reason in self.reasons(root)))

    def test_unknown_option_is_reported(self):
        root = self.build({"README.md": "# Title\n"}, config={"required-files": {"nonsense": True}})
        self.assertTrue(any("unknown option" in reason for reason in self.reasons(root)))

    def test_malformed_json_is_reported(self):
        root = self.build({"README.md": "# Title\n"})
        (root / "validate.json").write_text("{not json", encoding="utf-8")
        self.assertTrue(any("not valid JSON" in reason for reason in self.reasons(root)))

    def test_missing_config_uses_defaults(self):
        root = self.build({"README.md": "# Title\n"})
        config = load_config(root)
        self.assertTrue(config["markdown-links"]["enabled"])
        self.assertFalse(config["path-names"]["enabled"])

    def test_config_error_type_is_raised_directly(self):
        root = self.build({"README.md": "# Title\n"})
        (root / "validate.json").write_text('{"nope": {}}', encoding="utf-8")
        with self.assertRaises(ConfigError):
            load_config(root)


class LocalCheckTests(RepositoryTestCase):
    def test_local_checks_contribute_findings(self):
        module = "def extra_checks(context):\n    return [('README.md', 3, 'local rule fired')]\n"
        root = self.build({"README.md": "# Title\n", "scripts/validate_local.py": module})
        self.assertIn("local rule fired", self.reasons(root))
        self.assertIn("local", self.checks(root))

    def test_local_check_failure_is_contained(self):
        module = "def extra_checks(context):\n    raise ValueError('boom')\n"
        root = self.build({"README.md": "# Title\n", "scripts/validate_local.py": module})
        self.assertTrue(any("local checks raised" in reason for reason in self.reasons(root)))

    def test_missing_entry_point_is_reported(self):
        root = self.build({"README.md": "# Title\n", "scripts/validate_local.py": "x = 1\n"})
        self.assertTrue(any("must define extra_checks" in reason for reason in self.reasons(root)))

    def test_local_context_exposes_files(self):
        module = (
            "def extra_checks(context):\n"
            "    return [(p, 0, 'seen') for p in context.files if p.endswith('.md')]\n"
        )
        root = self.build({"README.md": "# Title\n", "scripts/validate_local.py": module})
        self.assertIn("seen", self.reasons(root))


class EnumerationTests(RepositoryTestCase):
    def test_git_enumeration_respects_gitignore(self):
        root = self.build(
            {"README.md": "# Title\n", "ignored.txt": "x\n", ".gitignore": "ignored.txt\n"}
        )
        result = subprocess.run(
            ["git", "-C", str(root), "init", "-q"], check=False, capture_output=True
        )
        if result.returncode != 0:
            self.skipTest("git is unavailable")
        files = enumerate_repository_files(root)
        self.assertIn("README.md", files)
        self.assertNotIn("ignored.txt", files)

    def test_walk_fallback_lists_files(self):
        root = self.build({"README.md": "# Title\n", "docs/guide.md": "# Guide\n"})
        files = enumerate_repository_files(root)
        self.assertEqual(files, ("README.md", "docs/guide.md"))


if __name__ == "__main__":
    unittest.main()
