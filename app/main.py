"""The application. One process serves the API and the built bundle."""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import logging_config
from app.request_context import RequestIdMiddleware
from app.routers import health, label_option, packing_item, packing_list

BASE_DIR = Path(__file__).resolve().parents[1]
DIST = BASE_DIR / "frontend_dist"


def create_app(dist: Path = DIST) -> FastAPI:
    """Build the application. `dist` is a parameter so tests can mount the
    catch-all against a directory they control - nothing has built
    frontend_dist/ when the suite runs, so a test that depends on it existing
    silently tests nothing.
    """
    logging_config.configure()

    app = FastAPI(title="travel")
    # Added first, so it is the OUTERMOST middleware and the id is set before
    # anything below it can log.
    app.add_middleware(RequestIdMiddleware)
    app.include_router(health.router)
    app.include_router(packing_list.router)
    app.include_router(packing_item.router)
    app.include_router(label_option.router)

    if dist.is_dir():
        # Conditional: a bundle small enough for Vite to inline every asset
        # has no assets/ directory, and StaticFiles raises on a missing one
        # while the app is being built - so the process would fail to start
        # because of a frontend change, with nothing in the frontend to point
        # at.
        if (dist / "assets").is_dir():
            app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{full_path:path}")
        def spa(full_path: str):
            """Every non-API path serves the bundle, so client routing works.

            Registered AFTER the API router, which is what stops it swallowing
            a REGISTERED /api/... route: had this route been added first, it
            would match /api/health before the health router ever got a turn.

            A `path` converter still matches any string, registered first or
            last, so ordering alone does not stop it claiming an UNREGISTERED
            /api/... path too - a mistyped endpoint would otherwise come back
            as a misleading 200 with the SPA's HTML instead of a 404. The
            explicit prefix check below is what actually prevents that.

            Past that guard, a path that names a REAL FILE in the bundle is
            served as that file. Vite copies frontend/public/ to the root of
            the bundle rather than into assets/, and only /assets is mounted
            as StaticFiles - so without this, /favicon.svg came back as
            index.html under text/html and the browser discarded it. Nothing
            sits in front of this app to cover the gap: cloudflared connects
            straight to uvicorn.

            `full_path` is user-controlled, so the candidate is resolved and
            confined to the dist directory before it is served - otherwise
            `..%2F.env` reads any file beside the bundle, the app's own
            credentials included. This is media's resolve-and-confine block,
            adopted rather than redesigned; docs/notes/decisions.md records
            why it is that rather than a list of special-cased icon paths.
            """
            if full_path == "api" or full_path.startswith("api/"):
                raise HTTPException(status_code=404)
            dist_root = dist.resolve()
            candidate = (dist_root / full_path).resolve()
            if (
                candidate != dist_root
                and candidate.is_relative_to(dist_root)
                and candidate.is_file()
            ):
                return FileResponse(candidate)
            return FileResponse(dist / "index.html")

    return app


app = create_app()
