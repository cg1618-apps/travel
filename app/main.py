"""The application. One process serves the API and the built bundle."""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.routers import health

BASE_DIR = Path(__file__).resolve().parents[1]
DIST = BASE_DIR / "frontend_dist"

app = FastAPI(title="travel")
app.include_router(health.router)

if DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

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
        """
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404)
        return FileResponse(DIST / "index.html")
