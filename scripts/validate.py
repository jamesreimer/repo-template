#!/usr/bin/env python3
"""Validate mechanical repository invariants without third-party dependencies.

This script is a managed baseline file. It is intended to stay byte-identical
across repositories that adopt it. Everything repository-specific belongs in
``validate.json`` (which checks run, and with what globs) or in an optional
``scripts/validate_local.py`` module that contributes additional findings.

The checks here cover mechanical invariants only. Scope, boundaries, normative
calibration, and prose quality remain human and AI review responsibilities.

Runs on Python 3.9 and later with the standard library alone.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import stat
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

CONFIG_PATH = "validate.json"
STRUCTURE_SNAPSHOT_PATH = "repository-structure.txt"
STRUCTURE_UPDATE_COMMAND = "python3 scripts/update_repository_structure.py"
LOCAL_CHECK_PATH = "scripts/validate_local.py"

DEFAULT_TEXT_GLOBS = [
    "**/*.cfg",
    "**/*.css",
    "**/*.html",
    "**/*.ini",
    "**/*.js",
    "**/*.json",
    "**/*.jsonc",
    "**/*.jsx",
    "**/*.md",
    "**/*.mjs",
    "**/*.py",
    "**/*.sh",
    "**/*.toml",
    "**/*.ts",
    "**/*.tsx",
    "**/*.txt",
    "**/*.xml",
    "**/*.yaml",
    "**/*.yml",
    "**/.editorconfig",
    "**/.gitattributes",
    "**/.gitignore",
    ".githooks/*",
]

DEFAULT_CONFIG = {
    "junk-artifacts": {
        "enabled": True,
        "names": [".DS_Store", "Thumbs.db", "desktop.ini"],
        "patterns": ["**/*.pyc", "**/*.pyo", "**/*.orig", "**/*.rej", "**/*~"],
        "directories": ["__pycache__"],
    },
    "text-encoding": {
        "enabled": True,
        "globs": list(DEFAULT_TEXT_GLOBS),
    },
    "final-newline": {
        "enabled": True,
        "globs": list(DEFAULT_TEXT_GLOBS),
    },
    "required-files": {
        "enabled": True,
        "paths": [],
    },
    "markdown-links": {
        "enabled": True,
        "globs": ["**/*.md"],
    },
    "markdown-headings": {
        "enabled": True,
        "globs": ["**/*.md"],
    },
    "credential-files": {
        "enabled": True,
        "patterns": [
            "**/.env",
            "**/.env.*",
            "**/*.pem",
            "**/*.p12",
            "**/*.pfx",
            "**/*.jks",
            "**/*.keystore",
            "**/id_rsa",
            "**/id_dsa",
            "**/id_ecdsa",
            "**/id_ed25519",
        ],
        "allow": [
            "**/.env.example",
            "**/.env.sample",
            "**/.env.*.example",
            "**/*.pub",
        ],
    },
    "path-names": {
        "enabled": False,
        "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*$",
        "scope": ["**"],
        "exempt": [],
        "rules": [],
    },
    "structure-snapshot": {
        "enabled": False,
        "path": STRUCTURE_SNAPSHOT_PATH,
    },
}

CHECK_NAMES = tuple(DEFAULT_CONFIG)


@dataclass(frozen=True, order=True)
class Finding:
    """A single mechanical defect, ordered for deterministic output."""

    path: str
    line: int
    reason: str
    check: str = ""

    def __str__(self) -> str:
        location = f"{self.path}:{self.line}" if self.line else self.path
        suffix = f" [{self.check}]" if self.check else ""
        return f"{location}: {self.reason}{suffix}"


@dataclass(frozen=True)
class CheckContext:
    """Read-only repository view handed to local checks."""

    root: Path
    files: tuple
    text: dict


class ConfigError(RuntimeError):
    """Raised when validate.json cannot be understood."""


_GLOB_CACHE = {}


def glob_to_regex(pattern: str):
    """Translate a glob to a regex where ``**`` alone may cross separators.

    ``pathlib`` and ``fnmatch`` disagree about ``**`` across supported Python
    versions, so the template owns this translation to stay deterministic.
    """
    compiled = _GLOB_CACHE.get(pattern)
    if compiled is not None:
        return compiled

    parts = ["^"]
    index = 0
    length = len(pattern)
    while index < length:
        character = pattern[index]
        if character == "*":
            if pattern.startswith("**", index):
                if pattern.startswith("**/", index):
                    parts.append("(?:[^/]+/)*")
                    index += 3
                    continue
                parts.append(".*")
                index += 2
                continue
            parts.append("[^/]*")
            index += 1
            continue
        if character == "?":
            parts.append("[^/]")
            index += 1
            continue
        parts.append(re.escape(character))
        index += 1
    parts.append("$")
    compiled = re.compile("".join(parts))
    _GLOB_CACHE[pattern] = compiled
    return compiled


def matches_any(relative_path: str, patterns) -> bool:
    return any(glob_to_regex(pattern).match(relative_path) for pattern in patterns)


def load_config(root: Path) -> dict:
    """Merge validate.json over the defaults, rejecting unknown keys."""
    config = {name: dict(options) for name, options in DEFAULT_CONFIG.items()}
    config_path = root / CONFIG_PATH
    if not config_path.is_file():
        return config

    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as error:
        raise ConfigError(f"{CONFIG_PATH} could not be read ({error})") from error
    except json.JSONDecodeError as error:
        raise ConfigError(f"{CONFIG_PATH} is not valid JSON ({error})") from error

    if not isinstance(raw, dict):
        raise ConfigError(f"{CONFIG_PATH} must contain a JSON object")

    for name, options in raw.items():
        if name.startswith("_"):
            continue
        if name not in config:
            known = ", ".join(CHECK_NAMES)
            raise ConfigError(
                f"{CONFIG_PATH} declares unknown check {name!r}; known checks: {known}"
            )
        if not isinstance(options, dict):
            raise ConfigError(f"{CONFIG_PATH} check {name!r} must map to a JSON object")
        for key, value in options.items():
            if key.startswith("_"):
                continue
            if key not in config[name]:
                known = ", ".join(sorted(config[name]))
                raise ConfigError(
                    f"{CONFIG_PATH} check {name!r} declares unknown option {key!r}; "
                    f"known options: {known}"
                )
            config[name][key] = value
    return config


def enumerate_repository_files(root: Path):
    """Return tracked and unignored repository paths, relative and POSIX-style."""
    root = root.resolve()
    if (root / ".git").exists():
        result = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
                "-z",
            ],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode == 0:
            return tuple(
                sorted(
                    entry.decode("utf-8", errors="replace")
                    for entry in result.stdout.split(b"\0")
                    if entry
                )
            )

    collected = []
    for current, directory_names, file_names in os.walk(root):
        current_path = Path(current)
        retained = []
        for name in sorted(directory_names):
            if name == ".git":
                continue
            if (current_path / name).is_symlink():
                # Record the link without descending through it, so the symlink
                # check can report it. Descending would leave the repository.
                collected.append((current_path / name).relative_to(root).as_posix())
                continue
            retained.append(name)
        directory_names[:] = retained
        for file_name in sorted(file_names):
            relative = (current_path / file_name).relative_to(root)
            collected.append(relative.as_posix())
    return tuple(sorted(collected))


def parent_directories(relative_path: str):
    """Yield every ancestor directory of a path, nearest root first."""
    parts = relative_path.split("/")[:-1]
    for index in range(1, len(parts) + 1):
        yield "/".join(parts[:index])


def render_repository_structure(relative_paths) -> str:
    """Render the deterministic repository structure snapshot."""
    entries = set()
    for relative_path in relative_paths:
        for directory in parent_directories(relative_path):
            entries.add(f"{directory}/")
        entries.add(relative_path)

    header = (
        f"# Generated by {STRUCTURE_UPDATE_COMMAND}\n"
        "# Regenerate after intentional repository structure changes.\n\n"
    )
    return header + "\n".join(sorted(entries)) + "\n"


FENCE_RE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})")
HEADING_RE = re.compile(r"^[ \t]{0,3}(#{1,6})[ \t]+(.*?)[ \t]*#*[ \t]*$")
INLINE_LINK_RE = re.compile(r"\]\(([^()]*)\)")
REFERENCE_DEFINITION_RE = re.compile(r"^[ \t]{0,3}\[([^\]]+)\]:[ \t]*(\S+)")
# Full and collapsed reference links and images: [text][label] and [text][].
# Shortcut references ([text] alone) are deliberately not matched, because
# ordinary bracketed prose is indistinguishable from them.
REFERENCE_USAGE_RE = re.compile(r"\[([^\]\n]+)\]\[([^\]\n]*)\]")
# A definition line whose destination is missing entirely.
MALFORMED_DEFINITION_RE = re.compile(r"^[ \t]{0,3}\[([^\]]+)\]:[ \t]*$")
INLINE_CODE_RE = re.compile(r"`+[^`]*`+")
EMPHASIS_RE = re.compile(r"[*_~]+")
MARKDOWN_LINK_TEXT_RE = re.compile(r"\[([^\]]*)\]\([^()]*\)")
SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


def normalize_reference_label(label: str) -> str:
    """Normalize a link label the way CommonMark matches them.

    Labels match case-insensitively with internal whitespace collapsed, so
    ``[See Also]`` and ``[see   also]`` refer to the same definition.
    """
    return " ".join(label.split()).casefold()


def heading_slug(text: str) -> str:
    """Approximate GitHub's heading anchor algorithm."""
    value = MARKDOWN_LINK_TEXT_RE.sub(r"\1", text)
    value = INLINE_CODE_RE.sub(lambda match: match.group(0).strip("`"), value)
    value = EMPHASIS_RE.sub("", value)
    value = value.strip().lower()
    value = "".join(
        character for character in value if character.isalnum() or character in {" ", "-", "_"}
    )
    return value.replace(" ", "-")


def parse_markdown(content: str):
    """Return anchors, destinations, defined labels, and label usages.

    Everything inside fenced code is ignored, so examples in documentation do
    not register as real links, definitions, or usages.
    """
    anchors = set()
    counts = Counter()
    destinations = []
    defined_labels = {}
    usages = []
    headings = []
    definition_problems = []
    fence = None
    fence_line = 0
    for number, raw_line in enumerate(content.splitlines(), start=1):
        fence_match = FENCE_RE.match(raw_line)
        if fence_match:
            marker = fence_match.group(1)[0]
            if fence is None:
                fence = marker
                fence_line = number
            elif fence == marker:
                fence = None
                fence_line = 0
            continue
        if fence is not None:
            continue

        heading_match = HEADING_RE.match(raw_line)
        if heading_match:
            headings.append((number, len(heading_match.group(1))))
            base = heading_slug(heading_match.group(2))
            if base:
                seen = counts[base]
                counts[base] += 1
                anchors.add(base if seen == 0 else f"{base}-{seen}")

        line = INLINE_CODE_RE.sub("", raw_line)
        for match in INLINE_LINK_RE.finditer(line):
            destinations.append((number, match.group(1)))
        definition = REFERENCE_DEFINITION_RE.match(line)
        if definition:
            label = definition.group(1)
            normalized = normalize_reference_label(label)
            if normalized in defined_labels:
                definition_problems.append(
                    (number, f"duplicate reference-style link definition {label!r}")
                )
            else:
                defined_labels[normalized] = number
            destinations.append((number, definition.group(2)))
            continue

        malformed = MALFORMED_DEFINITION_RE.match(line)
        if malformed:
            definition_problems.append(
                (
                    number,
                    f"reference-style link definition {malformed.group(1)!r} has no destination",
                )
            )
            continue

        for match in REFERENCE_USAGE_RE.finditer(line):
            # A collapsed reference, [text][], takes its label from the text.
            label = match.group(2) or match.group(1)
            usages.append((number, label))
    if fence is not None:
        definition_problems.append((fence_line, "fenced code block is not closed"))
    return anchors, destinations, defined_labels, usages, headings, definition_problems


def strip_inline_code(line: str) -> str:
    """Remove inline code spans so prose checks ignore code samples."""
    return INLINE_CODE_RE.sub("", line)


def markdown_without_fenced_code(content: str) -> str:
    """Blank out fenced code blocks while preserving line numbering.

    Exposed for scripts/validate_local.py, whose checks frequently need to read
    Markdown prose without matching text inside code fences.
    """
    lines = []
    fence = None
    for raw_line in content.splitlines():
        fence_match = FENCE_RE.match(raw_line)
        if fence_match:
            marker = fence_match.group(1)[0]
            if fence is None:
                fence = marker
            elif fence == marker:
                fence = None
            lines.append("")
            continue
        lines.append("" if fence is not None else raw_line)
    trailing = "\n" if content.endswith("\n") else ""
    return "\n".join(lines) + trailing


def parse_destination(raw_destination: str) -> str:
    """Strip angle brackets and any trailing link title."""
    destination = raw_destination.strip()
    if destination.startswith("<") and destination.endswith(">"):
        return destination[1:-1].strip()
    for quote in ('"', "'"):
        index = destination.find(f" {quote}")
        if index != -1:
            destination = destination[:index]
            break
    return destination.strip()


def is_external(destination: str) -> bool:
    return destination.startswith("//") or bool(SCHEME_RE.match(destination))


class RepositoryValidator:
    """Run the enabled mechanical checks over one repository."""

    def __init__(self, root: Path, config: dict) -> None:
        self.root = root.resolve()
        self.config = config
        self.findings = []
        self.files = ()
        self.text = {}
        self.markdown = {}

    def _add(self, path: str, reason: str, check: str, line: int = 0) -> None:
        self.findings.append(Finding(path, line, reason, check))

    def _enabled(self, name: str) -> bool:
        return bool(self.config[name].get("enabled"))

    def validate(self):
        self.files = enumerate_repository_files(self.root)
        self._check_junk_artifacts()
        self._check_symlinks()
        self._read_text_files()
        self._check_final_newline()
        self._check_required_files()
        self._check_credential_files()
        self._check_path_names()
        self._check_markdown_links()
        self._check_heading_hierarchy()
        self._check_structure_snapshot()
        self._run_local_checks()
        return sorted(set(self.findings))

    def _check_junk_artifacts(self) -> None:
        if not self._enabled("junk-artifacts"):
            return
        options = self.config["junk-artifacts"]
        names = set(options.get("names", ()))
        patterns = options.get("patterns", ())
        directories = set(options.get("directories", ()))
        for relative_path in self.files:
            name = relative_path.rsplit("/", 1)[-1]
            if name in names or matches_any(relative_path, patterns):
                self._add(relative_path, "junk artifact is not allowed", "junk-artifacts")
                continue
            if directories.intersection(relative_path.split("/")[:-1]):
                self._add(
                    relative_path,
                    "file lives in a junk artifact directory",
                    "junk-artifacts",
                )

    def _check_symlinks(self) -> None:
        """Reject committed symbolic links without reading their targets.

        This check is unconditional. A symbolic link is mechanically distinct
        from ordinary repository content and its target may resolve outside the
        repository entirely, so allowing one by configuration would widen the
        contract for little demonstrated value. The link is never read or
        resolved, so nothing outside the repository is opened.
        """
        for relative_path in self.files:
            try:
                mode = (self.root / relative_path).lstat().st_mode
            except OSError as error:
                self._add(
                    relative_path,
                    f"repository path metadata could not be read ({error.strerror or error})",
                    "symlinks",
                )
                continue
            if stat.S_ISLNK(mode):
                self._add(
                    relative_path,
                    "symbolic link must not be committed; the link target was not read",
                    "symlinks",
                )

    def _read_text_files(self) -> None:
        globs = list(self.config["text-encoding"].get("globs", ()))
        globs.extend(self.config["markdown-links"].get("globs", ()))
        globs.extend(self.config["markdown-headings"].get("globs", ()))
        globs.append(self.config["structure-snapshot"].get("path", STRUCTURE_SNAPSHOT_PATH))
        report = self._enabled("text-encoding")
        for relative_path in self.files:
            if not matches_any(relative_path, globs):
                continue
            path = self.root / relative_path
            if path.is_symlink() or not path.is_file():
                continue
            try:
                data = path.read_bytes()
            except OSError as error:
                if report:
                    self._add(
                        relative_path,
                        f"file could not be read ({error.strerror or error})",
                        "text-encoding",
                    )
                continue
            try:
                self.text[relative_path] = data.decode("utf-8")
            except UnicodeDecodeError as error:
                if report:
                    self._add(relative_path, f"file is not valid UTF-8 ({error})", "text-encoding")

    def _check_final_newline(self) -> None:
        if not self._enabled("final-newline"):
            return
        globs = self.config["final-newline"].get("globs", ())
        for relative_path, content in sorted(self.text.items()):
            if not matches_any(relative_path, globs):
                continue
            if content and not content.endswith("\n"):
                self._add(relative_path, "text file must end with a newline", "final-newline")

    def _check_required_files(self) -> None:
        if not self._enabled("required-files"):
            return
        present = set(self.files)
        for required in self.config["required-files"].get("paths", ()):
            if required not in present:
                self._add(required, "required baseline file is missing", "required-files")

    def _check_credential_files(self) -> None:
        if not self._enabled("credential-files"):
            return
        options = self.config["credential-files"]
        patterns = options.get("patterns", ())
        allow = options.get("allow", ())
        for relative_path in self.files:
            if matches_any(relative_path, allow):
                continue
            if matches_any(relative_path, patterns):
                self._add(
                    relative_path,
                    "credential-shaped file must not be committed",
                    "credential-files",
                )

    def _path_name_rules(self):
        """Return the configured path-name rules in evaluation order.

        A repository with one naming convention states ``pattern``, ``scope``
        and ``exempt`` directly. A repository whose convention differs by
        directory states ``rules`` instead, which fully replaces the single
        form rather than layering on top of it.
        """
        options = self.config["path-names"]
        raw_rules = options.get("rules") or []
        if raw_rules:
            return raw_rules
        return [
            {
                "pattern": options.get("pattern", ""),
                "scope": options.get("scope", ()),
                "exempt": options.get("exempt", ()),
            }
        ]

    def _compile_path_name_rules(self):
        """Validate and compile the rules, or report why they cannot be used."""
        compiled = []
        for index, raw in enumerate(self._path_name_rules()):
            if not isinstance(raw, dict):
                self._add(
                    CONFIG_PATH,
                    f"path-names rule {index} must be a JSON object",
                    "path-names",
                )
                return None
            # Keys beginning with "_" are comments, as they are at the top level.
            declared = {key for key in raw if not key.startswith("_")}
            unknown = sorted(declared - {"pattern", "scope", "exempt"})
            if unknown:
                self._add(
                    CONFIG_PATH,
                    f"path-names rule {index} declares unknown option {unknown[0]!r}; "
                    "known options: exempt, pattern, scope",
                    "path-names",
                )
                return None
            try:
                pattern = re.compile(raw.get("pattern", ""))
            except re.error as error:
                self._add(
                    CONFIG_PATH,
                    f"path-names rule {index} pattern is invalid ({error})",
                    "path-names",
                )
                return None
            compiled.append((pattern, raw.get("scope", ()), raw.get("exempt", ())))
        return compiled

    def _check_path_names(self) -> None:
        if not self._enabled("path-names"):
            return
        rules = self._compile_path_name_rules()
        if rules is None:
            return

        seen = set()
        for relative_path in self.files:
            candidates = list(parent_directories(relative_path)) + [relative_path]
            for candidate in candidates:
                if candidate in seen:
                    continue
                seen.add(candidate)
                # The first rule whose scope matches decides this path, so one
                # path yields at most one finding no matter how many rules could
                # have matched. Order rules most specific first.
                for pattern, scope, exempt in rules:
                    if not matches_any(candidate, scope):
                        continue
                    if not matches_any(candidate, exempt):
                        name = candidate.rsplit("/", 1)[-1]
                        if not pattern.match(name):
                            self._add(
                                candidate,
                                f"path component {name!r} does not match the configured pattern",
                                "path-names",
                            )
                    break

    def _check_markdown_links(self) -> None:
        if not self._enabled("markdown-links"):
            return
        globs = self.config["markdown-links"].get("globs", ())
        for relative_path, content in sorted(self.text.items()):
            if matches_any(relative_path, globs):
                self.markdown[relative_path] = parse_markdown(content)

        self._check_reference_labels()

        present = set(self.files)
        for relative_path, (_, destinations, _, _, _, _) in sorted(self.markdown.items()):
            directory = relative_path.rsplit("/", 1)[0] if "/" in relative_path else ""
            for line, raw_destination in destinations:
                destination = parse_destination(raw_destination)
                if not destination or is_external(destination) or destination.startswith("#"):
                    if destination.startswith("#"):
                        self._verify_anchor(relative_path, relative_path, destination[1:], line)
                    continue

                target, _, fragment = destination.partition("#")
                target = unquote(target)
                if target.startswith("/"):
                    self._add(
                        relative_path,
                        f"link destination {destination!r} is repository-absolute",
                        "markdown-links",
                        line,
                    )
                    continue
                resolved = os.path.normpath(os.path.join(directory, target)).replace(os.sep, "/")
                if resolved.startswith(".."):
                    self._add(
                        relative_path,
                        f"link destination {destination!r} escapes the repository",
                        "markdown-links",
                        line,
                    )
                    continue
                if resolved in present:
                    if fragment:
                        self._verify_anchor(relative_path, resolved, fragment, line)
                    continue
                if any(existing.startswith(f"{resolved}/") for existing in present):
                    continue
                self._add(
                    relative_path,
                    f"link destination {destination!r} does not exist",
                    "markdown-links",
                    line,
                )

    def _check_reference_labels(self) -> None:
        """Report unresolved usages, and definitions that cannot be relied on."""
        for relative_path, parsed in sorted(self.markdown.items()):
            _, _, defined_labels, usages, _, definition_problems = parsed
            for line, reason in definition_problems:
                self._add(relative_path, reason, "markdown-links", line)
            for line, label in usages:
                if normalize_reference_label(label) not in defined_labels:
                    self._add(
                        relative_path,
                        f"reference-style link label {label!r} has no matching definition",
                        "markdown-links",
                        line,
                    )

    def _verify_anchor(self, source: str, target: str, fragment: str, line: int) -> None:
        parsed = self.markdown.get(target)
        if parsed is None:
            return
        anchors = parsed[0]
        if unquote(fragment).lower() not in anchors:
            self._add(
                source,
                f"link anchor '#{fragment}' does not match a heading in {target}",
                "markdown-links",
                line,
            )

    def _check_heading_hierarchy(self) -> None:
        """Report headings that skip a level, such as H1 followed by H4.

        A skipped level breaks document outline and assistive-technology
        navigation. The first heading in a document may be any level; only
        increases of more than one level are reported.
        """
        if not self._enabled("markdown-headings"):
            return
        globs = self.config["markdown-headings"].get("globs", ())
        for relative_path, content in sorted(self.text.items()):
            if not matches_any(relative_path, globs):
                continue
            parsed = self.markdown.get(relative_path)
            headings = (parsed or parse_markdown(content))[4]
            if not headings:
                continue

            first_line, first_level = headings[0]
            if first_level != 1:
                self._add(
                    relative_path,
                    f"first heading must be H1, found H{first_level}",
                    "markdown-headings",
                    first_line,
                )

            top_level_headings = [line for line, level in headings if level == 1]
            if len(top_level_headings) != 1:
                self._add(
                    relative_path,
                    f"document must contain exactly one H1; found {len(top_level_headings)}",
                    "markdown-headings",
                    top_level_headings[1] if len(top_level_headings) > 1 else 0,
                )

            previous = None
            for line, level in headings:
                if previous is not None and level > previous + 1:
                    self._add(
                        relative_path,
                        f"heading level skips from H{previous} to H{level}",
                        "markdown-headings",
                        line,
                    )
                previous = level

    def _check_structure_snapshot(self) -> None:
        if not self._enabled("structure-snapshot"):
            return
        options = self.config["structure-snapshot"]
        snapshot_path = options.get("path", STRUCTURE_SNAPSHOT_PATH)
        paths = set(self.files)
        paths.add(snapshot_path)
        expected = render_repository_structure(sorted(paths))
        actual = self.text.get(snapshot_path)
        if actual is None:
            try:
                actual = (self.root / snapshot_path).read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                self._add(
                    snapshot_path,
                    f"structure snapshot is missing or unreadable; run {STRUCTURE_UPDATE_COMMAND}",
                    "structure-snapshot",
                )
                return
        if actual != expected:
            self._add(
                snapshot_path,
                f"structure snapshot is out of date; run {STRUCTURE_UPDATE_COMMAND}",
                "structure-snapshot",
            )

    def _run_local_checks(self) -> None:
        module_path = self.root / LOCAL_CHECK_PATH
        if not module_path.is_file():
            return
        spec = importlib.util.spec_from_file_location("validate_local", module_path)
        if spec is None or spec.loader is None:
            self._add(LOCAL_CHECK_PATH, "local check module could not be loaded", "local")
            return
        module = importlib.util.module_from_spec(spec)
        context = CheckContext(self.root, self.files, dict(self.text))
        scripts_directory = str(module_path.parent)
        if scripts_directory not in sys.path:
            sys.path.insert(0, scripts_directory)
        # Register before executing: dataclasses and typing resolve string
        # annotations by looking the defining module up in sys.modules, so a
        # local module using postponed annotations fails without this.
        sys.modules[spec.name] = module
        try:
            spec.loader.exec_module(module)
            extra_checks = getattr(module, "extra_checks", None)
            if extra_checks is None:
                self._add(
                    LOCAL_CHECK_PATH,
                    "local check module must define extra_checks(context)",
                    "local",
                )
                return
            results = list(extra_checks(context))
        except Exception as error:  # noqa: BLE001 - a local check must not abort the run
            # A module that failed to execute must not stay importable.
            sys.modules.pop(spec.name, None)
            self._add(
                LOCAL_CHECK_PATH, f"local checks raised {type(error).__name__}: {error}", "local"
            )
            return
        for result in results:
            try:
                path, line, reason = result
            except (TypeError, ValueError):
                self._add(
                    LOCAL_CHECK_PATH,
                    "local checks must yield (path, line, reason) tuples",
                    "local",
                )
                continue
            self._add(str(path), str(reason), "local", int(line))


def validate_repository(root: Path):
    """Validate one repository and return sorted findings."""
    try:
        config = load_config(root)
    except ConfigError as error:
        return [Finding(CONFIG_PATH, 0, str(error), "config")]
    return RepositoryValidator(root, config).validate()


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    findings = validate_repository(root)
    for finding in findings:
        print(finding)
    if findings:
        print(f"\n{len(findings)} finding(s)", file=sys.stderr)
        return 1
    print("Repository validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
