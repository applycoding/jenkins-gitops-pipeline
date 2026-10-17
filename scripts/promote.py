#!/usr/bin/env python3
"""Set an overlay image tag, or copy a tag along dev -> staging -> prod."""

import argparse
import re
import sys
from pathlib import Path

IMAGE_NAME = "ghcr.io/placeholder/status-api"
OVERLAYS = ("dev", "staging", "prod")
PROMOTION_EDGES = (("dev", "staging"), ("staging", "prod"))
TAG_PATTERN = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$")
_NEW_TAG = re.compile(
    r"^(?P<prefix>[ \t]*newTag:[ \t]*)"
    r"(?P<quote>[\"']?)"
    r"(?P<tag>[^\"'\s#]+)"
    r"(?P<endquote>[\"']?)"
    r"[ \t]*$",
    re.MULTILINE,
)


class PromoteError(Exception):
    """The overlay files or the requested promotion cannot be applied."""


def validate_tag(tag: str) -> None:
    if TAG_PATTERN.fullmatch(tag) is None:
        raise PromoteError(f"invalid image tag: {tag!r}")


def overlay_file(root: Path, overlay: str) -> Path:
    if overlay not in OVERLAYS:
        names = ", ".join(OVERLAYS)
        raise PromoteError(f"unknown overlay {overlay!r}; expected one of {names}")
    path = root / "deploy" / "overlays" / overlay / "kustomization.yaml"
    if not path.is_file():
        raise PromoteError(f"overlay file not found: {path}")
    return path


def read_tag(text: str) -> str:
    matches = list(_NEW_TAG.finditer(text))
    if len(matches) != 1:
        raise PromoteError(f"expected exactly one newTag entry, found {len(matches)}")
    return matches[0].group("tag")


def render_tag(text: str, tag: str) -> str:
    validate_tag(tag)
    matches = list(_NEW_TAG.finditer(text))
    if len(matches) != 1:
        raise PromoteError(f"expected exactly one newTag entry, found {len(matches)}")
    match = matches[0]
    quote = match.group("quote")
    endquote = match.group("endquote")
    if quote != endquote:
        raise PromoteError("newTag quotes are unbalanced")
    replacement = f"{match.group('prefix')}{quote}{tag}{endquote}"
    return text[: match.start()] + replacement + text[match.end() :]


def set_tag(root: Path, overlay: str, tag: str, *, dry_run: bool = False) -> str:
    validate_tag(tag)
    path = overlay_file(root, overlay)
    original = path.read_text(encoding="utf-8")
    current = read_tag(original)
    if current == tag:
        print(f"set {overlay}: {tag} unchanged")
        return tag
    updated = render_tag(original, tag)
    if dry_run:
        print(f"dry-run set {overlay}: {current} -> {tag}")
        return tag
    path.write_text(updated, encoding="utf-8")
    print(f"set {overlay}: {current} -> {tag}")
    return tag


def promote(root: Path, source: str, target: str, *, dry_run: bool = False) -> str:
    if (source, target) not in PROMOTION_EDGES:
        raise PromoteError(
            f"cannot promote {source} -> {target}; "
            "allowed steps are dev -> staging and staging -> prod"
        )
    tag = read_tag(overlay_file(root, source).read_text(encoding="utf-8"))
    prefix = "dry-run " if dry_run else ""
    print(f"{prefix}promote {source} -> {target}: {tag}")
    return set_tag(root, target, tag, dry_run=dry_run)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Set or promote Kustomize overlay image tags."
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Repository root. Defaults to the current directory.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    set_cmd = commands.add_parser("set", help="Set the image tag on one overlay.")
    set_cmd.add_argument("--overlay", required=True, choices=OVERLAYS)
    set_cmd.add_argument("--tag", required=True)
    set_cmd.add_argument("--dry-run", action="store_true")

    promote_cmd = commands.add_parser("promote", help="Copy an image tag to the next overlay.")
    promote_cmd.add_argument("--source", required=True, choices=OVERLAYS)
    promote_cmd.add_argument("--target", required=True, choices=OVERLAYS)
    promote_cmd.add_argument("--dry-run", action="store_true")

    args = parser.parse_args(argv)
    root = Path(args.root)
    try:
        if args.command == "set":
            set_tag(root, args.overlay, args.tag, dry_run=args.dry_run)
        elif args.command == "promote":
            promote(root, args.source, args.target, dry_run=args.dry_run)
        else:
            print(f"unknown command {args.command}", file=sys.stderr)
            return 2
    except PromoteError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
