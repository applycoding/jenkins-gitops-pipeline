#!/usr/bin/env python3
"""Structural lint for the declarative Jenkinsfile.

This does not ask a Jenkins controller to parse the DSL. It checks that the
pipeline block, agent, required stages, prod input gate, and promotion
commands are present. Run the controller's declarative linter separately
when a Jenkins instance is available.
"""

import argparse
import re
import sys
from pathlib import Path

REQUIRED_STAGES = (
    "Lint",
    "Test",
    "Build image",
    "Trivy scan",
    "Push",
    "Bump GitOps tag",
    "Promote to staging",
    "Promote to prod",
)

_STAGE = re.compile(r"stage\s*\(\s*(['\"])(?P<name>[^'\"]+)\1\s*\)\s*\{")
_PIPELINE = re.compile(r"(?m)^\s*pipeline\s*\{")
_AGENT = re.compile(r"(?m)^\s*agent\s+(any\b|\{)")
_INPUT = re.compile(r"\binput\s*\{")

_SNIPPETS = {
    "Lint": ("ruff check",),
    "Test": ("pytest",),
    "Build image": ("docker build",),
    "Trivy scan": ("trivy image",),
    "Push": ("docker push", "branch 'main'"),
    "Bump GitOps tag": ("scripts/promote.py set", "--overlay dev", "branch 'main'"),
    "Promote to staging": (
        "scripts/promote.py promote",
        "--source dev",
        "--target staging",
        "branch 'main'",
    ),
    "Promote to prod": (
        "scripts/promote.py promote",
        "--source staging",
        "--target prod",
        "branch 'main'",
    ),
}


class JenkinsfileLintError(ValueError):
    """The file could not be scanned, usually because braces or quotes are open."""


def _skip_string(text: str, index: int) -> int:
    if text.startswith("'''", index) or text.startswith('"""', index):
        quote = text[index : index + 3]
        end = text.find(quote, index + 3)
        if end < 0:
            raise JenkinsfileLintError("unterminated triple-quoted string")
        return end + 3
    quote = text[index]
    cursor = index + 1
    while cursor < len(text):
        if text[cursor] == "\\":
            cursor += 2
            continue
        if text[cursor] == quote:
            return cursor + 1
        cursor += 1
    raise JenkinsfileLintError("unterminated string")


def _read_block(text: str, open_brace: int) -> str:
    if text[open_brace] != "{":
        raise JenkinsfileLintError("expected '{'")
    depth = 0
    index = open_brace
    while index < len(text):
        if text.startswith("'''", index) or text.startswith('"""', index) or text[index] in "'\"":
            index = _skip_string(text, index)
            continue
        if text.startswith("//", index):
            newline = text.find("\n", index)
            index = len(text) if newline < 0 else newline + 1
            continue
        if text.startswith("/*", index):
            end = text.find("*/", index + 2)
            if end < 0:
                raise JenkinsfileLintError("unterminated block comment")
            index = end + 2
            continue
        character = text[index]
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return text[open_brace + 1 : index]
        index += 1
    raise JenkinsfileLintError("unbalanced braces")


def stage_bodies(text: str) -> list[tuple[str, str]]:
    bodies: list[tuple[str, str]] = []
    for match in _STAGE.finditer(text):
        bodies.append((match.group("name"), _read_block(text, match.end() - 1)))
    return bodies


def _contains(body: str, snippet: str) -> bool:
    if snippet == "branch 'main'":
        return "branch 'main'" in body or 'branch "main"' in body
    return snippet in body


def lint_text(text: str) -> list[str]:
    issues: list[str] = []
    if _PIPELINE.search(text) is None:
        issues.append("Jenkinsfile has no top-level 'pipeline {' block")
    if _AGENT.search(text) is None:
        issues.append("Jenkinsfile does not set an agent")
    try:
        stages = stage_bodies(text)
    except JenkinsfileLintError as exc:
        issues.append(str(exc))
        return issues

    names = [name for name, _ in stages]
    seen: set[str] = set()
    for name in names:
        if name in seen:
            issues.append(f"duplicate stage {name!r}")
        seen.add(name)

    present = [name for name in names if name in REQUIRED_STAGES]
    ordered: list[str] = []
    for name in present:
        if name not in ordered:
            ordered.append(name)
    for name in REQUIRED_STAGES:
        if name not in ordered:
            issues.append(f"missing required stage {name!r}")
    expected = [name for name in REQUIRED_STAGES if name in ordered]
    if ordered != expected:
        issues.append("required stages are out of order: " + ", ".join(ordered))

    bodies = {name: body for name, body in stages}
    for name, snippets in _SNIPPETS.items():
        body = bodies.get(name)
        if body is None:
            continue
        for snippet in snippets:
            if not _contains(body, snippet):
                issues.append(f"stage {name!r} must contain {snippet!r}")
        if name == "Promote to prod" and _INPUT.search(body) is None:
            issues.append("stage 'Promote to prod' must contain an input directive")
        if name == "Promote to staging" and _INPUT.search(body) is not None:
            issues.append("stage 'Promote to staging' must not contain an input directive")
    return issues


def lint_path(path: Path) -> list[str]:
    return lint_text(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Structurally lint a declarative Jenkinsfile.")
    parser.add_argument("path", nargs="?", default="Jenkinsfile")
    args = parser.parse_args(argv)
    path = Path(args.path)
    if not path.is_file():
        print(f"Jenkinsfile not found: {path}", file=sys.stderr)
        return 1
    issues = lint_path(path)
    if issues:
        for issue in issues:
            print(issue, file=sys.stderr)
        return 1
    print(f"{path} passed structural Jenkinsfile checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
