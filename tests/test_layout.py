"""Checks that the checked-in demo files stay consistent with each other."""

from pathlib import Path

from scripts.promote import IMAGE_NAME, OVERLAYS, TAG_PATTERN, read_tag
from status_api.catalog import DEFAULT_IMAGE, ENVIRONMENTS
from status_api.catalog import TAG_PATTERN as APP_TAG

ROOT = Path(__file__).resolve().parents[1]
SKIP = {".git", ".tools", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache"}
FORBIDDEN = (
    "BEGIN PRIVATE KEY",
    "BEGIN OPENSSH PRIVATE KEY",
    "ghp_",
    "github_pat_",
    "xoxb-",
    "AKIA",
)


def test_service_and_promote_share_image_and_tag_rules() -> None:
    assert DEFAULT_IMAGE == IMAGE_NAME
    assert ENVIRONMENTS == OVERLAYS
    assert APP_TAG.pattern == TAG_PATTERN.pattern


def test_overlays_have_placeholder_tags() -> None:
    for overlay in OVERLAYS:
        text = (ROOT / "deploy" / "overlays" / overlay / "kustomization.yaml").read_text(
            encoding="utf-8"
        )
        assert f"name: {IMAGE_NAME}" in text
        assert f"namespace: status-api-{overlay}" in text
        assert read_tag(text) == f"0.1.0-{overlay}"


def test_base_image_matches_the_promotion_image() -> None:
    deployment = (ROOT / "deploy" / "base" / "deployment.yaml").read_text(encoding="utf-8")
    assert f"image: {IMAGE_NAME}:set-by-overlay" in deployment


def test_argocd_manifests_point_at_the_placeholder_repo() -> None:
    application = (ROOT / "argocd" / "application.yaml").read_text(encoding="utf-8")
    appset = (ROOT / "argocd" / "applicationset.yaml").read_text(encoding="utf-8")
    assert "kind: Application\n" in application
    assert "kind: ApplicationSet\n" in appset
    for text in (application, appset):
        assert "https://github.com/PLACEHOLDER_ORG/jenkins-gitops-pipeline.git" in text
    assert 'automated: "false"' in appset
    assert "status-api-prod" in appset
    assert "path: deploy/overlays/dev" in application


def test_jenkins_config_uses_an_env_password_and_the_placeholder_remote() -> None:
    casc = (ROOT / "jenkins" / "casc.yaml").read_text(encoding="utf-8")
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "PLACEHOLDER_ORG" in casc
    assert "scriptPath('Jenkinsfile')" in casc
    assert "${JENKINS_ADMIN_PASSWORD}" in casc
    assert "dev-only-change-me" not in casc
    assert "18080:8080" in compose
    assert "./jenkins/casc.yaml:/var/jenkins_casc/casc.yaml:ro" in compose
    assert "dev-only-change-me" in compose


def test_ci_invokes_the_same_checks_as_make() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    script = (ROOT / "scripts" / "validate_manifests.sh").read_text(encoding="utf-8")
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "make test" in workflow
    assert "python3 -m pytest" in makefile
    assert "scripts/lint_jenkinsfile.py" in makefile
    assert "validate_manifests.sh" in makefile
    assert "KUSTOMIZE_VERSION:-5.8.3" in script
    assert "KUBECONFORM_VERSION:-0.8.0" in script
    assert "KUBERNETES_VERSION:-1.37.0" in script


def test_repo_has_no_credential_material() -> None:
    for path in ROOT.rglob("*"):
        if path.resolve() == Path(__file__).resolve():
            continue
        if not path.is_file() or any(part in SKIP for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for marker in FORBIDDEN:
            assert marker not in text, f"{marker} found in {path}"
