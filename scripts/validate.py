#!/usr/bin/env python3
"""Validate mechanical repository invariants without third-party dependencies.

This script is a managed baseline file. It is intended to stay byte-identical
across repositories that adopt it. Everything repository-specific belongs in
``validate.json`` (which checks run, and with what globs) or in an optional
``scripts/validate_local.py`` module that contributes additional findings.

The checks here cover mechanical invariants only. Scope, boundaries, normative
calibration, and prose quality remain human and AI review responsibilities.

Markdown rules run separately through markdownlint. This script does not parse
Markdown. scripts/check_markdown_links.py delegates links to Lychee.

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
from dataclasses import dataclass
from pathlib import Path

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

# Reject retired options explicitly rather than silently claiming coverage.
RETIRED_CHECKS = {
    "markdown-headings": "Markdown heading rules are configured in .markdownlint-cli2.jsonc",
    "markdown-links": (
        "the handwritten Markdown parser was removed; markdownlint checks same-file "
        "fragments and reference labels; scripts/check_markdown_links.py checks cross-file links"
    ),
}


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


# Options whose list entries are objects rather than strings, mapped to the
# expected type of each known key. Entry shape and unknown keys are reported
# where the check reads them; value types are checked here, so a malformed
# value raises ConfigError instead of a raw TypeError at match time.
OBJECT_LIST_OPTIONS = {
    ("path-names", "rules"): {"pattern": str, "scope": list, "exempt": list},
}


def describe_type(value) -> str:
    """Name a JSON value's type the way validate.json spells it."""
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, (int, float)):
        return "number"
    return "null"


def check_option_type(name: str, key: str, value, default) -> None:
    """Raise ConfigError when an option's type cannot be what the check expects.

    The expected type is taken from the default, so this stays correct as
    options are added. Without it a string where an array belongs is iterated
    character by character and reports one finding per letter.
    """
    expected = describe_type(default)
    actual = describe_type(value)
    if isinstance(default, bool):
        valid = isinstance(value, bool)
    elif isinstance(default, list):
        valid = isinstance(value, list)
    elif isinstance(default, str):
        valid = isinstance(value, str)
    else:
        valid = actual == expected

    if not valid:
        raise ConfigError(
            f"{CONFIG_PATH} check {name!r} option {key!r} must be {'an' if expected[0] in 'ao' else 'a'} "
            f"{expected}; found {actual}"
        )

    if not isinstance(default, list):
        return

    entry_types = OBJECT_LIST_OPTIONS.get((name, key))
    if entry_types is None:
        for entry in value:
            if not isinstance(entry, str):
                raise ConfigError(
                    f"{CONFIG_PATH} check {name!r} option {key!r} must contain only strings; "
                    f"found {describe_type(entry)}"
                )
        return

    for index, entry in enumerate(value):
        if not isinstance(entry, dict):
            continue  # shape is reported where the check reads it
        for entry_key, entry_value in entry.items():
            if entry_key.startswith("_"):
                continue
            expected_type = entry_types.get(entry_key)
            if expected_type is None:
                continue  # unknown keys are reported where the check reads them
            if not isinstance(entry_value, expected_type):
                wanted = "an array" if expected_type is list else "a string"
                raise ConfigError(
                    f"{CONFIG_PATH} check {name!r} {key} entry {index} option "
                    f"{entry_key!r} must be {wanted}; found {describe_type(entry_value)}"
                )
            if expected_type is list:
                for item in entry_value:
                    if not isinstance(item, str):
                        raise ConfigError(
                            f"{CONFIG_PATH} check {name!r} {key} entry {index} option "
                            f"{entry_key!r} must contain only strings; "
                            f"found {describe_type(item)}"
                        )


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
            if name in RETIRED_CHECKS:
                raise ConfigError(
                    f"{CONFIG_PATH} declares check {name!r}, which no longer exists; "
                    f"{RETIRED_CHECKS[name]}"
                )
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
            check_option_type(name, key, value, DEFAULT_CONFIG[name][key])
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
                    if entry and os.path.lexists(root / entry.decode("utf-8", errors="replace"))
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


class RepositoryValidator:
    """Run the enabled mechanical checks over one repository."""

    def __init__(self, root: Path, config: dict) -> None:
        self.root = root.resolve()
        self.config = config
        self.findings = []
        self.files = ()
        self.text = {}
        self.content = {}

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
        if self._enabled("final-newline"):
            globs.extend(self.config["final-newline"].get("globs", ()))
        if self._enabled("structure-snapshot"):
            globs.append(self.config["structure-snapshot"]["path"])
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
                self._add(
                    relative_path,
                    f"file could not be read ({error.strerror or error})",
                    "file-read",
                )
                continue
            self.content[relative_path] = data
            try:
                self.text[relative_path] = data.decode("utf-8")
            except UnicodeDecodeError as error:
                if report and matches_any(relative_path, self.config["text-encoding"]["globs"]):
                    self._add(relative_path, f"file is not valid UTF-8 ({error})", "text-encoding")

    def _check_final_newline(self) -> None:
        if not self._enabled("final-newline"):
            return
        globs = self.config["final-newline"].get("globs", ())
        for relative_path, content in sorted(self.content.items()):
            if not matches_any(relative_path, globs):
                continue
            if content and not content.endswith(b"\n"):
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
                if (
                    not isinstance(path, str)
                    or not isinstance(reason, str)
                    or type(line) is not int
                    or line < 0
                ):
                    raise ValueError("invalid finding fields")
            except (TypeError, ValueError):
                self._add(
                    LOCAL_CHECK_PATH,
                    "local checks must yield (str path, nonnegative int line, str reason) tuples",
                    "local",
                )
                continue
            self._add(path, reason, "local", line)


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
