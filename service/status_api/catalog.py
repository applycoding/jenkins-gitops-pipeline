"""In-memory release catalog. There is no database and no cluster client."""

import re
from dataclasses import dataclass

ENVIRONMENTS = ("dev", "staging", "prod")
DEFAULT_IMAGE = "ghcr.io/placeholder/status-api"
TAG_PATTERN = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$")


class CatalogError(Exception):
    """Base error for catalog edits."""


class UnknownEnvironment(CatalogError):
    """The caller named an environment this catalog does not track."""

    def __init__(self, environment: str) -> None:
        self.environment = environment
        super().__init__(f"unknown environment: {environment}")


class InvalidTag(CatalogError):
    """The image tag is empty or outside the OCI tag character set."""

    def __init__(self, tag: str) -> None:
        self.tag = tag
        super().__init__(f"invalid image tag: {tag!r}")


@dataclass(frozen=True)
class Release:
    environment: str
    image: str
    tag: str


class Catalog:
    """Seeded list of environment tags. Process memory is the only store."""

    def __init__(self, image: str = DEFAULT_IMAGE) -> None:
        self._image = image
        self._tags = {environment: f"0.1.0-{environment}" for environment in ENVIRONMENTS}

    def list_releases(self) -> list[Release]:
        return [self.get(environment) for environment in ENVIRONMENTS]

    def get(self, environment: str) -> Release:
        self._require(environment)
        return Release(environment, self._image, self._tags[environment])

    def set_tag(self, environment: str, tag: str) -> Release:
        self._require(environment)
        if TAG_PATTERN.fullmatch(tag) is None:
            raise InvalidTag(tag)
        self._tags[environment] = tag
        return self.get(environment)

    def _require(self, environment: str) -> None:
        if environment not in self._tags:
            raise UnknownEnvironment(environment)
