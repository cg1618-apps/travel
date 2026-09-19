"""The health probe must fail in the three ways that matter."""

from fastapi.testclient import TestClient

from app.main import app
from app.routers import health


def test_it_reports_ok_when_the_schema_matches_the_code(monkeypatch):
    monkeypatch.setattr(health, "read_alembic_revision", lambda db: "abc123")
    monkeypatch.setattr(health, "expected_revision", lambda: "abc123")
    response = TestClient(app).get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_it_reports_503_when_the_database_cannot_be_read(monkeypatch):
    def boom(db):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(health, "read_alembic_revision", boom)
    response = TestClient(app).get("/api/health")
    assert response.status_code == 503


def test_it_reports_503_when_the_schema_and_the_code_disagree(monkeypatch):
    # The state a half-rolled-back deploy leaves behind: the database holds the
    # new revision, the image has rolled back to code that never heard of it.
    # Pages still serve. Only this comparison notices.
    monkeypatch.setattr(health, "read_alembic_revision", lambda db: "new456")
    monkeypatch.setattr(health, "expected_revision", lambda: "old123")
    assert TestClient(app).get("/api/health").status_code == 503


def test_two_unreadable_sides_are_not_a_match(monkeypatch):
    # None == None would be a MATCH, and an app that can read neither side
    # would report healthy. The media tracker checks this explicitly for that
    # reason; so does this.
    monkeypatch.setattr(health, "read_alembic_revision", lambda db: None)
    monkeypatch.setattr(health, "expected_revision", lambda: None)
    assert TestClient(app).get("/api/health").status_code == 503
