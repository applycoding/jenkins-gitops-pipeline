"""Structural checks for the declarative Jenkinsfile."""

from pathlib import Path

from scripts.lint_jenkinsfile import lint_path, lint_text, main

ROOT = Path(__file__).resolve().parents[1]


def _jenkinsfile() -> str:
    return (ROOT / "Jenkinsfile").read_text(encoding="utf-8")


def test_repository_jenkinsfile_passes() -> None:
    assert lint_path(ROOT / "Jenkinsfile") == []


def test_cli_accepts_repository_jenkinsfile() -> None:
    assert main([str(ROOT / "Jenkinsfile")]) == 0


def test_scripted_pipeline_is_rejected() -> None:
    issues = lint_text("node {\n  echo 'hello'\n}\n")
    assert any("pipeline" in issue for issue in issues)


def test_missing_stage_is_rejected() -> None:
    broken = _jenkinsfile().replace("stage('Trivy scan')", "stage('Scan')", 1)
    issues = lint_text(broken)
    assert any("Trivy scan" in issue for issue in issues)


def test_stages_out_of_order_are_rejected() -> None:
    broken = _jenkinsfile().replace("stage('Lint')", "stage('TempLint')", 1)
    broken = broken.replace("stage('Test')", "stage('Lint')", 1)
    broken = broken.replace("stage('TempLint')", "stage('Test')", 1)
    issues = lint_text(broken)
    assert any("out of order" in issue for issue in issues)


def test_prod_requires_an_input_directive() -> None:
    broken = _jenkinsfile().replace("input {", "echo {", 1)
    issues = lint_text(broken)
    assert any("input" in issue for issue in issues)


def test_staging_rejects_an_input_directive() -> None:
    needle = "stage('Promote to staging') {"
    insert = needle + "\n            input {\n                message 'no'\n            }"
    broken = _jenkinsfile().replace(needle, insert, 1)
    issues = lint_text(broken)
    assert any("Promote to staging" in issue and "input" in issue for issue in issues)


def test_unbalanced_braces_are_reported() -> None:
    text = "pipeline {\n  agent any\n  stages { stage('Lint') { steps { echo 'x' }\n"
    issues = lint_text(text)
    assert any("unbalanced" in issue for issue in issues)
