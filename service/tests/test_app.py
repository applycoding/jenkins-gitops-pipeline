"""Unit tests for the in-memory catalog and its HTTP routes."""

import pytest
from fastapi.testclient import TestClient

from status_api.catalog import Catalog, InvalidTag, UnknownEnvironment
from status_api.main import create_app


def _client(catalog: Catalog | None = None) -> TestClient:
    return TestClient(create_app(catalog))


def test_health_and_ready() -> None:
    client = _client()
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/ready").json() == {"status": "ready"}


def test_version() -> None:
    body = _client().get("/version").json()
    assert body["service"] == "status-api"
    assert body["version"]


def test_lists_seed_releases_in_environment_order() -> None:
    releases = _client().get("/releases").json()
    assert [item["environment"] for item in releases] == ["dev", "staging", "prod"]
    assert [item["tag"] for item in releases] == ["0.1.0-dev", "0.1.0-staging", "0.1.0-prod"]
    assert {item["image"] for item in releases} == {"ghcr.io/placeholder/status-api"}


def test_get_one_release() -> None:
    response = _client().get("/releases/staging")
    assert response.status_code == 200
    assert response.json()["tag"] == "0.1.0-staging"


def test_put_updates_only_the_named_environment() -> None:
    client = _client()
    response = client.put("/releases/dev", json={"tag": "sha-abc123"})
    assert response.status_code == 200
    assert response.json()["tag"] == "sha-abc123"
    assert client.get("/releases/dev").json()["tag"] == "sha-abc123"
    assert client.get("/releases/staging").json()["tag"] == "0.1.0-staging"


def test_unknown_environment_is_404() -> None:
    client = _client()
    assert client.get("/releases/qa").status_code == 404
    assert client.put("/releases/Prod", json={"tag": "sha-abc"}).status_code == 404


@pytest.mark.parametrize(
    "tag",
    ["", "bad tag", "../escape", "-leading", ".hidden", "a" * 129, "sha:digest"],
)
def test_invalid_tag_is_422(tag: str) -> None:
    response = _client().put("/releases/dev", json={"tag": tag})
    assert response.status_code == 422
    assert "invalid image tag" in response.json()["detail"]


def test_missing_tag_field_is_422() -> None:
    assert _client().put("/releases/dev", json={}).status_code == 422


def test_apps_do_not_share_a_catalog() -> None:
    first = _client()
    second = _client()
    first.put("/releases/prod", json={"tag": "sha-fff"})
    assert second.get("/releases/prod").json()["tag"] == "0.1.0-prod"


def test_injected_catalog_is_the_one_the_app_uses() -> None:
    catalog = Catalog()
    catalog.set_tag("dev", "sha-injected")
    assert _client(catalog).get("/releases/dev").json()["tag"] == "sha-injected"


def test_catalog_rejects_unknown_environment_and_bad_tag() -> None:
    catalog = Catalog()
    with pytest.raises(UnknownEnvironment):
        catalog.get("qa")
    with pytest.raises(InvalidTag):
        catalog.set_tag("dev", "not a tag")
