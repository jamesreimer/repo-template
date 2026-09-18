"""Unit tests for the mechanical repository validator."""

from __future__ import annotations

import contextlib
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from check_markdown_links import check_links  # noqa: E402
from validate import (  # noqa: E402
    ConfigError,
    enumerate_repository_files,
    glob_to_regex,
    load_config,
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

    def test_custom_glob_is_checked_independently_of_encoding(self):
        root = self.build(
            {"data.custom": b"value"},
            config={
                "text-encoding": {"enabled": False, "globs": []},
                "final-newline": {"globs": ["**/*.custom"]},
            },
        )
        self.assertIn("text file must end with a newline", self.reasons(root))

    def test_newline_check_does_not_require_utf8_decoding(self):
        root = self.build(
            {"data.custom": b"\xff"},
            config={"final-newline": {"globs": ["**/*.custom"]}},
        )
        self.assertEqual(["text file must end with a newline"], self.reasons(root))

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


class PathNameRuleTests(RepositoryTestCase):
    """Mixed conventions: kebab-case generally, snake_case for Python modules."""

    KEBAB = r"^[a-z0-9]+(?:-[a-z0-9]+)*(?:\.[a-z0-9]+)*$"
    SNAKE = r"^(?:[a-z][a-z0-9]*(?:_[a-z0-9]+)*|__init__)\.py$"

    def mixed(self):
        return {
            "path-names": {
                "enabled": True,
                "rules": [
                    {"pattern": self.SNAKE, "scope": ["scripts/*.py", "tests/*.py"]},
                    {"pattern": self.KEBAB, "scope": ["**"], "exempt": ["scripts", "tests"]},
                ],
            }
        }

    def test_mixed_conventions_accept_both_styles(self):
        root = self.build(
            {
                "readme-page.md": "# Page\n",
                "docs/getting-started.md": "# Start\n",
                "scripts/update_repository_structure.py": "x = 1\n",
                "tests/test_validate.py": "x = 1\n",
            },
            config=self.mixed(),
        )
        self.assertEqual([], self.reasons(root))

    def test_python_module_must_be_snake_case(self):
        root = self.build(
            {"readme-page.md": "# P\n", "scripts/BadName.py": "x = 1\n"}, config=self.mixed()
        )
        self.assertIn(
            "path component 'BadName.py' does not match the configured pattern",
            self.reasons(root),
        )

    def test_kebab_rule_does_not_reject_python_modules(self):
        root = self.build({"scripts/setup_git_hooks.py": "x = 1\n"}, config=self.mixed())
        self.assertEqual([], self.reasons(root))

    def test_ordinary_path_must_be_kebab_case(self):
        root = self.build({"docs/Bad_Name.md": "# B\n"}, config=self.mixed())
        self.assertIn(
            "path component 'Bad_Name.md' does not match the configured pattern",
            self.reasons(root),
        )

    def test_one_path_yields_at_most_one_finding(self):
        root = self.build(
            {"scripts/BadName.py": "x = 1\n"},
            config={
                "path-names": {
                    "enabled": True,
                    "rules": [
                        {"pattern": self.SNAKE, "scope": ["scripts/*.py"]},
                        {"pattern": self.KEBAB, "scope": ["**"]},
                    ],
                }
            },
        )
        findings = [f for f in validate_repository(root) if f.check == "path-names"]
        self.assertEqual(1, len(findings))

    def test_first_matching_rule_decides(self):
        # The narrow rule is listed first and exempts the path, so the later
        # catch-all never sees it.
        root = self.build(
            {"scripts/BadName.py": "x = 1\n"},
            config={
                "path-names": {
                    "enabled": True,
                    "rules": [
                        {"pattern": self.SNAKE, "scope": ["scripts/**"], "exempt": ["scripts/**"]},
                        {"pattern": self.KEBAB, "scope": ["**"]},
                    ],
                }
            },
        )
        self.assertEqual([], self.reasons(root))

    def test_single_rule_form_still_works(self):
        root = self.build(
            {"Bad_Name.md": "# B\n"},
            config={"path-names": {"enabled": True, "pattern": self.KEBAB, "scope": ["**"]}},
        )
        self.assertIn(
            "path component 'Bad_Name.md' does not match the configured pattern",
            self.reasons(root),
        )

    def test_rules_replace_the_single_rule_form(self):
        # The top-level pattern would reject this name; the rules list governs.
        root = self.build(
            {"docs/page.md": "# P\n"},
            config={
                "path-names": {
                    "enabled": True,
                    "pattern": "^never-matches$",
                    "rules": [{"pattern": self.KEBAB, "scope": ["**"]}],
                }
            },
        )
        self.assertEqual([], self.reasons(root))

    def test_path_outside_every_rule_scope_is_not_checked(self):
        root = self.build(
            {"Vendor_Dir/Thing.md": "# T\n"},
            config={
                "path-names": {
                    "enabled": True,
                    "rules": [{"pattern": self.KEBAB, "scope": ["docs/**"]}],
                }
            },
        )
        self.assertEqual([], self.reasons(root))

    def test_invalid_rule_pattern_is_reported(self):
        root = self.build(
            {"README.md": "# T\n"},
            config={"path-names": {"enabled": True, "rules": [{"pattern": "["}]}},
        )
        self.assertTrue(any("rule 0 pattern is invalid" in reason for reason in self.reasons(root)))

    def test_unknown_rule_option_is_reported(self):
        root = self.build(
            {"README.md": "# T\n"},
            config={"path-names": {"enabled": True, "rules": [{"patern": "^x$"}]}},
        )
        self.assertTrue(any("unknown option 'patern'" in reason for reason in self.reasons(root)))

    def test_non_object_rule_is_reported(self):
        root = self.build(
            {"README.md": "# T\n"},
            config={"path-names": {"enabled": True, "rules": ["not-an-object"]}},
        )
        self.assertTrue(any("must be a JSON object" in reason for reason in self.reasons(root)))


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
        self.assertTrue(config["final-newline"]["enabled"])
        self.assertFalse(config["path-names"]["enabled"])

    def test_config_error_type_is_raised_directly(self):
        root = self.build({"README.md": "# Title\n"})
        (root / "validate.json").write_text('{"nope": {}}', encoding="utf-8")
        with self.assertRaises(ConfigError):
            load_config(root)


class ConfigTypeTests(RepositoryTestCase):
    """Option values must have the type the check expects.

    Covered in both directions: a well-typed configuration is accepted, and
    each mistyped shape raises rather than being iterated as characters.
    """

    def test_well_typed_configuration_is_accepted(self):
        root = self.build(
            {"README.md": "# Title\n"},
            config={
                "required-files": {"paths": ["README.md"]},
                "final-newline": {"enabled": True},
                "path-names": {
                    "enabled": True,
                    "pattern": "^[a-z.]+$",
                    "exempt": ["README.md"],
                },
            },
        )
        self.assertEqual([], self.reasons(root))

    def test_string_where_an_array_is_expected_is_rejected(self):
        root = self.build({"README.md": "# T\n"}, config={"required-files": {"paths": "README.md"}})
        reasons = self.reasons(root)
        self.assertEqual(1, len(reasons))
        self.assertIn("must be an array; found string", reasons[0])

    def test_non_string_array_entry_is_rejected(self):
        root = self.build(
            {"README.md": "# T\n"}, config={"required-files": {"paths": ["README.md", 42]}}
        )
        self.assertIn("must contain only strings; found number", self.reasons(root)[0])

    def test_non_boolean_enabled_is_rejected(self):
        root = self.build({"README.md": "# T\n"}, config={"final-newline": {"enabled": "yes"}})
        self.assertIn("must be a boolean; found string", self.reasons(root)[0])

    def test_array_where_a_string_is_expected_is_rejected(self):
        root = self.build({"README.md": "# T\n"}, config={"path-names": {"pattern": ["^x$"]}})
        self.assertIn("must be a string; found array", self.reasons(root)[0])

    def test_object_valued_rules_entries_are_allowed(self):
        root = self.build(
            {"readme.md": "# T\n"},
            config={
                "path-names": {
                    "enabled": True,
                    "rules": [{"pattern": "^[a-z.]+$", "scope": ["**"]}],
                }
            },
        )
        self.assertEqual([], self.reasons(root))

    def test_rule_scope_must_be_an_array(self):
        root = self.build(
            {"README.md": "# T\n"},
            config={"path-names": {"enabled": True, "rules": [{"pattern": "^x$", "scope": 5}]}},
        )
        self.assertIn("rules entry 0 option 'scope' must be an array", self.reasons(root)[0])

    def test_rule_pattern_must_be_a_string(self):
        root = self.build(
            {"README.md": "# T\n"},
            config={"path-names": {"enabled": True, "rules": [{"pattern": 7}]}},
        )
        self.assertIn("rules entry 0 option 'pattern' must be a string", self.reasons(root)[0])

    def test_rule_scope_entries_must_be_strings(self):
        root = self.build(
            {"README.md": "# T\n"},
            config={
                "path-names": {"enabled": True, "rules": [{"pattern": "^x$", "scope": ["**", 3]}]}
            },
        )
        self.assertIn("must contain only strings", self.reasons(root)[0])

    def test_rule_comment_keys_are_still_allowed(self):
        root = self.build(
            {"readme.md": "# T\n"},
            config={
                "path-names": {
                    "enabled": True,
                    "rules": [{"_": "why", "pattern": "^[a-z.]+$", "scope": ["**"]}],
                }
            },
        )
        self.assertEqual([], self.reasons(root))

    def test_config_error_reports_one_finding_not_one_per_character(self):
        root = self.build({"README.md": "# T\n"}, config={"required-files": {"paths": "README.md"}})
        self.assertEqual(1, len(validate_repository(root)))


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

    def test_malformed_results_are_contained_and_valid_results_survive(self):
        for invalid in [
            ("a", "bad", "x"),
            ("a", None, "x"),
            ("a", -1, "x"),
            ("a", True, "x"),
            ("a", 1.2, "x"),
            ("a", 0, None),
            "abc",
        ]:
            with self.subTest(result=invalid):
                module = (
                    "def extra_checks(context):\n    return "
                    + repr([invalid, ("README.md", 1, "valid result")])
                    + "\n"
                )
                root = self.build({"scripts/validate_local.py": module})
                reasons = self.reasons(root)
                self.assertIn("valid result", reasons)
                self.assertTrue(any("must yield" in reason for reason in reasons))

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


class LocalCheckLoaderTests(RepositoryTestCase):
    def test_local_module_may_use_dataclasses_with_postponed_annotations(self):
        root = self.build({"README.md": "# Title\n"})
        (root / "scripts").mkdir(exist_ok=True)
        (root / "scripts" / "validate_local.py").write_text(
            "from __future__ import annotations\n\n"
            "from dataclasses import dataclass\n\n\n"
            "@dataclass(frozen=True)\n"
            "class Note:\n"
            "    line: int\n"
            "    reason: str\n\n\n"
            "def extra_checks(context):\n"
            "    note = Note(1, 'local check ran')\n"
            "    return [('README.md', note.line, note.reason)]\n",
            encoding="utf-8",
        )
        self.assertIn("local check ran", self.reasons(root))

    def test_failed_local_module_is_not_left_importable(self):
        import sys as _sys

        root = self.build({"README.md": "# Title\n"})
        (root / "scripts").mkdir(exist_ok=True)
        (root / "scripts" / "validate_local.py").write_text(
            "raise RuntimeError('boom')\n", encoding="utf-8"
        )
        _sys.modules.pop("validate_local", None)
        reasons = self.reasons(root)
        self.assertTrue(any("boom" in reason for reason in reasons))
        self.assertNotIn("validate_local", _sys.modules)


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

    def test_working_tree_deletion_is_not_a_symlink_error(self):
        root = self.build({"old.txt": "old\n"}, {"required-files": {"paths": ["old.txt"]}})
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "add", "old.txt"], check=True)
        (root / "old.txt").unlink()
        self.assertNotIn("old.txt", enumerate_repository_files(root))
        self.assertEqual(["required baseline file is missing"], self.reasons(root))

    def test_walk_fallback_lists_files(self):
        root = self.build({"README.md": "# Title\n", "docs/guide.md": "# Guide\n"})
        files = enumerate_repository_files(root)
        self.assertEqual(files, ("README.md", "docs/guide.md"))


class RetiredMarkdownConfigTests(RepositoryTestCase):
    def test_old_options_fail_explicitly(self):
        for name in ("markdown-links", "markdown-headings"):
            with self.subTest(check=name):
                root = self.build({}, {name: {"enabled": True}})
                findings = validate_repository(root)
                self.assertEqual(1, len(findings))
                self.assertEqual("config", findings[0].check)
                self.assertIn("no longer exists", findings[0].reason)


class LinkToolTests(RepositoryTestCase):
    def run_links(self, root):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            result = check_links(root)
        self.link_output = output.getvalue()
        return result

    def test_missing_tool_fails_instead_of_skipping_validation(self):
        root = self.build({"README.md": "# Guide\n"})
        with patch("check_markdown_links.shutil.which", return_value=None):
            self.assertEqual(1, self.run_links(root))

    @unittest.skipUnless(shutil.which("lychee"), "Lychee is not installed")
    def test_real_parser_accepts_valid_markdown_and_rejects_broken_links(self):
        cases = [
            ("multiline reference", "See [doc][d].\n\n[d]:\n  guide.md\n", "# Guide\n", True),
            ("quoted code", "> ```md\n> [sample](missing.md)\n> ```\n", "# Guide\n", True),
            ("indented code", "    [sample](missing.md)\n", "# Guide\n", True),
            ("angle title", '[doc](<guide.md> "Guide")\n', "# Guide\n", True),
            ("missing parentheses", "[doc](missing(1).md)\n", "# Guide\n", False),
            ("existing parentheses", "[doc](guide(1).md)\n", "# Guide\n", True),
            ("comment heading", "[doc](guide.md#fake)\n", "# Guide\n\n<!--\n## Fake\n-->\n", False),
            ("underscore", "[doc](guide.md#foo_bar)\n", "# Guide\n\n## foo_bar\n", True),
            (
                "inline html",
                "[doc](guide.md#ctrl-keys)\n",
                "# Guide\n\n## <kbd>Ctrl</kbd> keys\n",
                True,
            ),
            ("setext", "[doc](guide.md#section)\n", "Title\n=====\n\nSection\n-------\n", True),
            (
                "duplicate",
                "[doc](guide.md#section-1)\n",
                "# Guide\n\n## Section\n\n## Section\n",
                True,
            ),
            ("missing fragment", "[doc](guide.md#missing)\n", "# Guide\n", False),
            ("absolute", "[doc](/guide.md)\n", "# Guide\n", False),
            ("external offline", "[doc](https://nonexistent.invalid/)\n", "# Guide\n", True),
        ]
        for label, body, target, valid in cases:
            with self.subTest(case=label):
                root = self.build(
                    {
                        "README.md": "# Guide\n\n" + body,
                        "guide.md": target,
                        "guide(1).md": "# Guide\n",
                    }
                )
                self.assertEqual(valid, self.run_links(root) == 0)

    @unittest.skipUnless(shutil.which("lychee"), "Lychee is not installed")
    def test_existing_file_outside_repository_is_rejected(self):
        root = self.build({"README.md": "# Guide\n"})
        with tempfile.TemporaryDirectory(dir=root.parent) as outside:
            target = Path(outside) / "guide.md"
            target.write_text("# Outside\n")
            (root / "README.md").write_text(
                "# Guide\n\n[outside](../" + Path(outside).name + "/guide.md)\n"
            )
            self.assertNotEqual(0, self.run_links(root))

    @unittest.skipUnless(shutil.which("lychee"), "Lychee is not installed")
    def test_ignored_markdown_is_not_checked(self):
        root = self.build(
            {
                "README.md": "# Guide\n",
                ".gitignore": "generated/\n",
                "generated/guide.md": "[broken](missing.md)\n",
            }
        )
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        self.assertEqual(0, self.run_links(root))


MARKDOWNLINT_CONFIG = Path(__file__).resolve().parents[1] / ".markdownlint-cli2.jsonc"

# The Markdown semantics the validator no longer implements, and the defect
# each rule exists to catch.
DELEGATED_RULES = {
    "MD001": "heading levels increment by one",
    "MD025": "a document has one top-level heading",
    "MD041": "a document opens at the top level",
    "MD051": "a same-file link fragment names a heading",
    "MD052": "a reference label is defined",
    "MD053": "a reference definition is used and not duplicated",
}


def load_markdownlint_config():
    """Read the repository's markdownlint configuration, stripping comments."""
    text = MARKDOWNLINT_CONFIG.read_text(encoding="utf-8")
    without_comments = re.sub(r"^\s*//.*$", "", text, flags=re.MULTILINE)
    return json.loads(without_comments)["config"]


class MarkdownlintConfigurationTests(unittest.TestCase):
    """The rules the validator delegates to must actually be enabled.

    Removing a check from validate.py only moves ownership if markdownlint is
    configured to make it. These read the configuration this repository ships,
    which is also the one consumers inherit.
    """

    def test_every_delegated_rule_is_enabled(self):
        config = load_markdownlint_config()
        for rule, purpose in sorted(DELEGATED_RULES.items()):
            with self.subTest(rule=rule):
                self.assertIn(rule, config, f"{rule} must be enabled so that {purpose}")
                self.assertTrue(config[rule], f"{rule} must not be disabled")

    def test_first_heading_rule_allows_a_preamble(self):
        # Without this MD041 reads as "the first line is a heading", which
        # rejects a document opening with a badge block or a table of contents.
        self.assertEqual({"allow_preamble": True}, load_markdownlint_config()["MD041"])

    def test_default_rules_are_opt_in(self):
        self.assertIs(False, load_markdownlint_config()["default"])


class MarkdownlintBehaviorTests(unittest.TestCase):
    """Evidence that markdownlint reports the defects the validator gave up.

    This is an integration check against the real tool, not a reimplementation
    of its test suite: one document per delegated rule, plus the valid
    CommonMark that the validator's own parser used to reject. It is skipped
    when markdownlint-cli2 is unavailable, because the Python suite must keep
    running with no Node toolchain present.
    """

    REPORTED = {
        "MD001": "# Title\n\n#### Deep\n",
        "MD025": "# One\n\n# Two\n",
        "MD041": "## Starts At Two\n\n### Then Three\n",
        "MD051": "# Title\n\nSee [x](#nowhere).\n",
        "MD052": "# Title\n\nSee [x][missing].\n",
        "MD053": "# Title\n\n[unused]: https://example.com\n",
    }

    # Valid CommonMark that the hand-rolled parser rejected. markdownlint must
    # accept all of it, or the ownership move traded one false positive set for
    # another.
    ACCEPTED = {
        "setext headings": "Document Title\n==============\n\n## Section\n",
        "type-7 html block": '<img src="logo.png" alt="Logo">\nProject Banner\n---\n\n# Real Title\n',
        "type-1 html block": "<pre>code</pre>\n\n# Real Title\n\n## Section\n",
        "reference definition then rule": "[ref]: https://example.com\n\n---\n\n# T\n\nUse [it][ref].\n",
        "loose list then rule": "# Guide\n\n- item\n\n  inner paragraph\n\n---\n\n## Section\n",
        "heading in a blockquote": "# Guide\n\n> ## Quoted heading\n>\n> body\n\nSee [q](#quoted-heading).\n",
        "setext heading in a blockquote": "# Guide\n\n> Quoted title\n> ---\n>\n> body\n\nSee [q](#quoted-title).\n",
    }

    @classmethod
    def setUpClass(cls):
        if shutil.which("markdownlint-cli2") is None:
            raise unittest.SkipTest("markdownlint-cli2 is not installed")

    def lint(self, files):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        shutil.copy(MARKDOWNLINT_CONFIG, root / MARKDOWNLINT_CONFIG.name)
        for name, content in files.items():
            (root / name).write_text(content, encoding="utf-8")
        result = subprocess.run(
            ["markdownlint-cli2", "**/*.md"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        # markdownlint-cli2 writes its findings to stderr.
        self.assertIn(result.returncode, (0, 1), result.stdout + result.stderr)
        return result.returncode, result.stdout + result.stderr

    def test_each_delegated_rule_reports_its_defect(self):
        files = {f"{rule.lower()}.md": body for rule, body in self.REPORTED.items()}
        code, output = self.lint(files)
        self.assertEqual(code, 1, output)
        for rule in sorted(self.REPORTED):
            with self.subTest(rule=rule):
                self.assertIn(rule, output, f"{rule} did not report {rule.lower()}.md")

    def test_valid_commonmark_is_accepted(self):
        files = {f"ok{index}.md": body for index, body in enumerate(self.ACCEPTED.values())}
        names = dict(zip(files, self.ACCEPTED))
        code, output = self.lint(files)
        self.assertEqual(code, 0, output)
        for name, label in names.items():
            with self.subTest(case=label):
                self.assertNotIn(name, output, f"{label} was rejected: {output}")


if __name__ == "__main__":
    unittest.main()
