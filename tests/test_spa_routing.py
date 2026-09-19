"""The catch-all must not shadow the API."""

from fastapi.testclient import TestClient

from app.main import app


def test_an_unknown_api_path_is_404_not_the_spa():
    # If the catch-all is mounted before the API routes, every mistyped
    # endpoint returns the index page with a 200, and a broken frontend call
    # looks like a rendering bug rather than a missing route.
    response = TestClient(app).get("/api/does-not-exist")
    assert response.status_code == 404
