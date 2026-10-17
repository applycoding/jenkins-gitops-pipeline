"""HTTP API for the in-memory release catalog."""

from collections.abc import Callable

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from status_api import __version__
from status_api.catalog import Catalog, InvalidTag, Release, UnknownEnvironment


class TagUpdate(BaseModel):
    tag: str


def _release_or_http(action: Callable[[], Release]) -> Release:
    try:
        return action()
    except UnknownEnvironment as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidTag as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def create_app(catalog: Catalog | None = None) -> FastAPI:
    store = catalog if catalog is not None else Catalog()
    app = FastAPI(title="status-api", version=__version__)
    app.state.catalog = store

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    def ready() -> dict[str, str]:
        return {"status": "ready"}

    @app.get("/version")
    def version() -> dict[str, str]:
        return {"service": "status-api", "version": app.version}

    @app.get("/releases")
    def list_releases() -> list[Release]:
        return store.list_releases()

    @app.get("/releases/{environment}")
    def get_release(environment: str) -> Release:
        return _release_or_http(lambda: store.get(environment))

    @app.put("/releases/{environment}")
    def put_release(environment: str, body: TagUpdate) -> Release:
        return _release_or_http(lambda: store.set_tag(environment, body.tag))

    return app


app = create_app()
