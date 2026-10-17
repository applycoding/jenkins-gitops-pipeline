"""Unit tests for overlay tag edits. They use temp directories, not the repo."""

from pathlib import Path

import pytest

from scripts.promote import (
    IMAGE_NAME,
    OVERLAYS,
    PromoteError,
    main,
    overlay_file,
    promote,
    read_tag,
    render_tag,
    set_tag,
    validate_tag,
)


def _kustomization(tag: str) -> str:
    return (
        "apiVersion: kustomize.config.k8s.io/v1beta1\n"
        "kind: Kustomization\n"
        "resources:\n"
        "  - ../../base\n"
        "images:\n"
        f"  - name: {IMAGE_NAME}\n"
        f'    newTag: "{tag}"\n'
        "replicas:\n"
        "  - name: status-api\n"
        "    count: 1\n"
    )


def _scaffold(root: Path, **tags: str) -> None:
    for name in OVERLAYS:
        path = root / "deploy" / "overlays" / name / "kustomization.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_kustomization(tags.get(name, f"0.1.0-{name}")), encoding="utf-8")


def _tag(root: Path, overlay: str) -> str:
    return read_tag(overlay_file(root, overlay).read_text(encoding="utf-8"))


def test_render_preserves_neighboring_lines() -> None:
    updated = render_tag(_kustomization("0.1.0-dev"), "sha-abc")
    assert 'newTag: "sha-abc"' in updated
    assert "count: 1" in updated
    assert f"name: {IMAGE_NAME}" in updated


def test_render_keeps_an_unquoted_tag() -> None:
    assert render_tag("newTag: 0.1.0-dev\n", "sha-abc") == "newTag: sha-abc\n"


def test_read_tag_requires_exactly_one_entry() -> None:
    with pytest.raises(PromoteError, match="exactly one"):
        read_tag("kind: Kustomization\n")
    with pytest.raises(PromoteError, match="exactly one"):
        read_tag('newTag: "one"\nnewTag: "two"\n')


def test_unbalanced_quotes_are_rejected() -> None:
    with pytest.raises(PromoteError, match="unbalanced"):
        render_tag('newTag: "0.1.0-dev\n', "sha-abc")


def test_validate_tag_rejects_a_space() -> None:
    with pytest.raises(PromoteError, match="invalid image tag"):
        validate_tag("bad tag")


def test_set_then_promote_copies_the_tag_forward(tmp_path: Path) -> None:
    _scaffold(tmp_path, dev="sha-111")
    set_tag(tmp_path, "dev", "sha-222")
    assert _tag(tmp_path, "dev") == "sha-222"
    promote(tmp_path, "dev", "staging")
    assert _tag(tmp_path, "staging") == "sha-222"
    promote(tmp_path, "staging", "prod")
    assert _tag(tmp_path, "prod") == "sha-222"
    assert _tag(tmp_path, "dev") == "sha-222"


def test_dry_run_does_not_write(tmp_path: Path) -> None:
    _scaffold(tmp_path)
    before = overlay_file(tmp_path, "staging").read_bytes()
    set_tag(tmp_path, "dev", "sha-dry", dry_run=True)
    promote(tmp_path, "dev", "staging", dry_run=True)
    assert "sha-dry" not in overlay_file(tmp_path, "dev").read_text(encoding="utf-8")
    assert overlay_file(tmp_path, "staging").read_bytes() == before


def test_unchanged_tag_does_not_rewrite_the_file(tmp_path: Path) -> None:
    _scaffold(tmp_path, dev="sha-same")
    path = overlay_file(tmp_path, "dev")
    before = path.read_bytes()
    set_tag(tmp_path, "dev", "sha-same")
    assert path.read_bytes() == before


def test_skipping_staging_is_rejected(tmp_path: Path) -> None:
    _scaffold(tmp_path)
    with pytest.raises(PromoteError, match="allowed steps"):
        promote(tmp_path, "dev", "prod")


def test_reverse_promotion_is_rejected(tmp_path: Path) -> None:
    _scaffold(tmp_path)
    with pytest.raises(PromoteError, match="allowed steps"):
        promote(tmp_path, "staging", "dev")


def test_missing_overlay_file(tmp_path: Path) -> None:
    with pytest.raises(PromoteError, match="not found"):
        set_tag(tmp_path, "dev", "sha-abc")


def test_unknown_overlay(tmp_path: Path) -> None:
    with pytest.raises(PromoteError, match="unknown overlay"):
        overlay_file(tmp_path, "qa")


def test_cli_promote(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _scaffold(tmp_path, dev="sha-cli")
    code = main(["--root", str(tmp_path), "promote", "--source", "dev", "--target", "staging"])
    assert code == 0
    assert "sha-cli" in capsys.readouterr().out
    assert _tag(tmp_path, "staging") == "sha-cli"


def test_cli_rejects_a_skipped_environment(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _scaffold(tmp_path)
    code = main(["--root", str(tmp_path), "promote", "--source", "dev", "--target", "prod"])
    assert code == 1
    assert "allowed steps" in capsys.readouterr().err


def test_cli_requires_a_command() -> None:
    with pytest.raises(SystemExit) as caught:
        main([])
    assert caught.value.code == 2
