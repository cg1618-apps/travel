"""The application. One process serves the API and, later, the built bundle."""

from fastapi import FastAPI

from app.routers import health

app = FastAPI(title="travel")
app.include_router(health.router)
