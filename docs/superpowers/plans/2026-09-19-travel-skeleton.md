# The travel skeleton — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** An application that runs locally, builds as a container, and answers a
health probe that cannot lie — with no features in it at all.

**Architecture:** FastAPI serving both the API and the built React bundle from
one process, PostgreSQL through SQLAlchemy, Alembic for migrations, and the
four things the platform's app contract requires. The health endpoint is ported
from the media tracker rather than invented: it compares the revision the
database claims against the head the running code ships, which is the only
check that catches a half-rolled-back deploy.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy, Alembic, pydantic-settings,
pytest, React + Vite, Docker.

**Spec:** `docs/notes/decisions.md` in this repository (the stack and access
decisions) and `docs/registry.md` in `cg1618-apps/platform` (the app contract).

## Global Constraints

- **Ports, so all four apps can run at once:** this app is **uvicorn 8002, Vite
  5175**. The rule is uvicorn = the app's registry port, Vite = 5173 + (port −
  8000). `media` keeps 8000/5173.
- **One development PostgreSQL**, the existing `anime_site_postgres_db`
  container, with **one database per app**. This app's is `travel`. Mirrors
  production; does not start a fourth container.
- **Network alias `travel-app`** in production, because the generated ingress
  routes `http://travel-app:8002`. Changing it here alone produces a 502 with
  both files looking correct.
- **Nothing is published to the host** in `docker-compose.prod.yml`. The tunnel
  is the only ingress.
- **No features.** No packing lists, no trips. A task that adds a domain table
  is out of scope; this plan ends at a deployable empty application.
- **Nothing in git mentions AI**, in any commit message or pull request body.
- The app is `status: planned` in the registry throughout. Going live is the
  next plan, not this one.

---

### Task 1: Configuration and the database session

**Files:**
- Create: `app/__init__.py`, `app/config.py`, `app/database.py`
- Create: `tests/test_config.py`
- Create: `requirements.txt`
- Modify: `requirements-dev.txt`

**Interfaces:**
- Produces: `app.config.settings`, a pydantic-settings object exposing
  `app_env: str`, `postgres_user/password/db/host/port`, and a computed
  `sqlalchemy_database_url: str`. `DATABASE_URL`, when set, is used verbatim.
- Produces: `app.database.SessionLocal`, `app.database.Base`, and
  `app.database.get_db()` yielding a `Session`.

- [ ] **Step 1: Write the failing test**

```python
"""Configuration, and the one rule about it that has bitten this project."""

import importlib


def test_database_url_is_honoured_verbatim_when_set(monkeypatch):
    # A stale DATABASE_URL in a machine's .env wins over the POSTGRES_* parts
    # and breaks that machine. It is honoured deliberately - the surprise is
    # only a surprise to someone who does not know - so it is pinned here.
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@example:5432/db")
    from app import config

    importlib.reload(config)
    assert config.settings.sqlalchemy_database_url == "postgresql://u:p@example:5432/db"


def test_the_url_is_built_from_the_parts_when_it_is_not(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("POSTGRES_USER", "travel")
    monkeypatch.setenv("POSTGRES_PASSWORD", "secret")
    monkeypatch.setenv("POSTGRES_DB", "travel")
    monkeypatch.setenv("POSTGRES_HOST", "db")
    from app import config

    importlib.reload(config)
    assert config.settings.sqlalchemy_database_url == (
        "postgresql://travel:secret@db:5432/travel"
    )
```

- [ ] **Step 2: Run it and watch it fail**

```bash
venv/Scripts/python.exe -m pytest tests/test_config.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.config'`.

- [ ] **Step 3: Write `requirements.txt`**

```
fastapi==0.115.6
uvicorn[standard]==0.34.0
SQLAlchemy==2.0.36
alembic==1.14.0
psycopg2-binary==2.9.10
pydantic-settings==2.7.0
```

And prepend `-r requirements.txt` to `requirements-dev.txt`, so one install
covers both — the media tracker's arrangement.

- [ ] **Step 4: Write `app/config.py`**

```python
"""Every environment variable this app reads, read once, here.

DATABASE_URL is honoured verbatim when set. That is deliberate and it is the
rule most likely to confuse: a leftover value in a machine's .env beats the
POSTGRES_* parts and breaks that machine, with an error that points at the
database rather than at the file.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "production"

    postgres_user: str = "travel"
    postgres_password: str = ""
    postgres_db: str = "travel"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    database_url: str | None = None

    @property
    def sqlalchemy_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
```

- [ ] **Step 5: Write `app/database.py`**

```python
"""The engine, the session factory, and the dependency that hands one out."""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

engine = create_engine(settings.sqlalchemy_database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Every model inherits this; Alembic's autogenerate reads its metadata."""


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 6: Run the tests, then commit**

```bash
venv/Scripts/python.exe -m pytest tests/ -q
git add app/__init__.py app/config.py app/database.py tests/test_config.py requirements.txt requirements-dev.txt
git commit -m "feat: configuration and the database session"
```

---

### Task 2: The health endpoint, and the application itself

The endpoint is the app contract's second clause. It is ported from the media
tracker, whose module docstring explains why each of the three conditions is
there — read `media/app/routers/health.py` before writing this.

**Files:**
- Create: `app/main.py`, `app/routers/__init__.py`, `app/routers/health.py`
- Create: `tests/test_health.py`, `tests/conftest.py`

**Interfaces:**
- Consumes: `app.database.get_db`, `app.config.settings`.
- Produces: `app.main.app`, a FastAPI instance with `/api/health` mounted.
- Produces: `app.routers.health.read_alembic_revision(db) -> str | None` and
  `expected_revision() -> str | None`.

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run it and watch it fail**

Expected: `ModuleNotFoundError: No module named 'app.main'`.

- [ ] **Step 3: Write `app/routers/health.py`**

Port it from `media/app/routers/health.py`, minus the `/detail` route and its
permission dependency — this app has no permissions. Keep `read_alembic_revision`
reading `alembic_version.version_num` and nothing else, keep `expected_revision`
cached with `lru_cache` and returning `None` when there is more than one head,
and keep the explicit `actual is None or expected is None` check.

- [ ] **Step 4: Write `app/main.py`**

```python
"""The application. One process serves the API and, later, the built bundle."""

from fastapi import FastAPI

from app.routers import health

app = FastAPI(title="travel")
app.include_router(health.router)
```

- [ ] **Step 5: Run the tests, then commit**

```bash
venv/Scripts/python.exe -m pytest tests/ -q
git add app/main.py app/routers/ tests/test_health.py tests/conftest.py
git commit -m "feat: a health probe that cannot lie"
```

- [ ] **Step 6: Correct the registry**

`apps.yml` declares this app's `health_path` as `/health`, and it is
`/api/health` — the `/api` prefix is what makes the SPA catch-all in Task 5
structurally unable to shadow it. Open a one-line pull request against
`cg1618-apps/platform` changing `travel`'s `health_path`, and say in the body
that the prefix is load-bearing rather than cosmetic.

---

### Task 3: Alembic, and a chain that provably builds

**Files:**
- Create: `alembic.ini`, `alembic/env.py`, `alembic/script.py.mako`
- Create: `alembic/versions/0001_baseline.py`
- Create: `tests/test_migrations_build_the_schema.py`

**Interfaces:**
- Produces: a single Alembic head. `expected_revision()` from Task 2 reads it.
- Produces: an empty baseline revision, so the chain exists before any table
  does and the from-zero test is meaningful from day one.

- [ ] **Step 1: Write the failing test**

```python
"""The migration chain must build from nothing.

The media tracker ran for 145 revisions with a chain that could not: its
initial revision aborted its transaction on an empty database and rolled back
to zero tables, unnoticed because the test fixtures built their schema with
create_all and never ran Alembic. This test is what makes that impossible here,
and it is written before there is a single table to build.
"""

import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def scratch_database():
    """A database created for this test and dropped afterwards."""
    admin = create_engine(
        "postgresql://postgres:postgres@localhost:5432/postgres",
        isolation_level="AUTOCOMMIT",
    )
    with admin.connect() as conn:
        conn.execute(text("DROP DATABASE IF EXISTS travel_migration_test"))
        conn.execute(text("CREATE DATABASE travel_migration_test"))
    yield "postgresql://postgres:postgres@localhost:5432/travel_migration_test"
    with admin.connect() as conn:
        conn.execute(text("DROP DATABASE IF EXISTS travel_migration_test"))


def test_upgrade_head_runs_against_an_empty_database(scratch_database):
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT,
        env={"DATABASE_URL": scratch_database, "PATH": ""},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_there_is_exactly_one_head():
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "heads"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert len(result.stdout.strip().splitlines()) == 1, result.stdout
```

- [ ] **Step 2: Run it and watch it fail**

Expected: alembic is not configured; the subprocess exits non-zero.

- [ ] **Step 3: Initialise Alembic**

```bash
cd /c/Users/cgent/Documents/cg1618/travel
venv/Scripts/python.exe -m alembic init alembic
```

Then edit `alembic/env.py` to take the URL from `app.config.settings` rather
than from `alembic.ini`, and to point `target_metadata` at
`app.database.Base.metadata`. Copy the shape from `media/alembic/env.py`.

- [ ] **Step 4: Write the baseline revision**

```python
"""baseline

Revision ID: 0001_baseline
Revises:
Create Date: 2026-09-19
"""

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Deliberately empty.

    The chain has to exist before the first table does, so that the from-zero
    test is meaningful from the first commit rather than from whenever someone
    remembers to add it.
    """


def downgrade() -> None:
    """Also empty; there is nothing to reverse."""
```

- [ ] **Step 5: Run the tests, then commit**

---

### Task 4: `deploy/migrations`, the hook the platform calls

**Files:**
- Create: `deploy/migrations`
- Create: `tests/test_migrations_hook.py`

**Interfaces:**
- Produces: an executable with three subcommands, which `bin/deploy` and
  `bin/rollback` in `cg1618-apps/platform` call:
  - `current` — prints the revision the **database** is at
  - `added <from> <to>` — prints the migration files a deploy would add, one
    per line, empty if none
  - `downgrade <target>` — reverses to that revision, non-zero if it refuses

- [ ] **Step 1: Write the failing test**

```python
"""The hook's shape. The platform calls it; a wrong exit code misleads a deploy."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "deploy" / "migrations"


def code() -> str:
    lines = HOOK.read_text(encoding="utf-8").splitlines()
    return "\n".join(line for line in lines if not line.lstrip().startswith("#"))


def test_it_fails_fast():
    assert "set -euo pipefail" in HOOK.read_text(encoding="utf-8")


def test_it_implements_the_three_subcommands():
    body = code()
    for command in ("current", "added", "downgrade"):
        assert f"{command})" in body, command


def test_current_reads_the_database_not_the_files():
    # The revision the DATABASE believes it is at is the only authoritative
    # answer during a rollback; asking the image tells you what that image
    # knows, which is the thing that has just changed.
    assert "alembic_version" in code()


def test_an_unknown_subcommand_exits_non_zero():
    assert "exit 1" in code()
```

- [ ] **Step 2: Run it and watch it fail**

- [ ] **Step 3: Write `deploy/migrations`**

```bash
#!/usr/bin/env bash
# The migration hook the platform's deploy pipeline calls.
#
#   ./deploy/migrations current              the revision the DATABASE is at
#   ./deploy/migrations added <from> <to>    revision files a deploy would add
#   ./deploy/migrations downgrade <target>   reverse to that revision
#
# This exists because a rollback cannot be generic: reading a version table,
# deciding what a deploy adds, and reversing a migration are all specific to
# the tool an app uses. The platform asks these three questions; the answers
# are Alembic's here and something else in an app that uses something else.

set -euo pipefail

cd "$(dirname "$0")/.."

COMPOSE=(env -u COMPOSE_PROJECT_NAME docker compose -f "${PLATFORM_DIR:-${HOME}/cg1618}/docker-compose.prod.yml")

case "${1:-}" in
    current)
        # From alembic_version and nowhere else. Asking the image answers what
        # that image knows, which is exactly what changes during a rollback.
        "${COMPOSE[@]}" exec -T db \
            psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -tA \
            -c "SELECT version_num FROM alembic_version" | tr -d '[:space:]'
        ;;
    added)
        from="${2:?added needs a from-revision}"
        to="${3:?added needs a to-revision}"
        git diff --name-only "${from}" "${to}" -- alembic/versions/
        ;;
    downgrade)
        target="${2:?downgrade needs a target}"
        # From the NEW image: it is the only one holding the revision files
        # being reversed. --entrypoint alembic is not optional - without it the
        # image's entrypoint discards the command and re-runs the upgrade that
        # just failed.
        docker compose -f docker-compose.prod.yml \
            run --rm --entrypoint alembic app downgrade "${target}"
        ;;
    *)
        echo "usage: migrations current | added <from> <to> | downgrade <target>" >&2
        exit 1
        ;;
esac
```

- [ ] **Step 4: Run the tests, shellcheck, commit**

---

### Task 5: The frontend, and serving it from the same process

**Files:**
- Create: `frontend/` — Vite + React, one page that fetches `/api/health`
- Modify: `app/main.py` — serve `frontend_dist/` and a catch-all
- Create: `tests/test_spa_routing.py`
- Modify: `.gitignore` — add `frontend_dist/`

**Interfaces:**
- Consumes: `app.main.app` from Task 2.
- Produces: `npm run build` in `frontend/` writes `../frontend_dist/`.

- [ ] **Step 1: Write the failing test**

```python
"""The catch-all must not shadow the API."""

from fastapi.testclient import TestClient

from app.main import app


def test_an_unknown_api_path_is_404_not_the_spa():
    # If the catch-all is mounted before the API routes, every mistyped
    # endpoint returns the index page with a 200, and a broken frontend call
    # looks like a rendering bug rather than a missing route.
    response = TestClient(app).get("/api/does-not-exist")
    assert response.status_code == 404
```

- [ ] **Step 2: Scaffold the frontend**

```bash
cd /c/Users/cgent/Documents/cg1618/travel
npm create vite@latest frontend -- --template react
cd frontend && npm install
```

Then replace `vite.config.js` with this — the three settings that matter are
the output directory, this app's Vite port, and the proxy that lets the dev
server talk to uvicorn:

```javascript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// outDir is outside frontend/ because uvicorn serves the built bundle from the
// repository root. port 5175 and the 8002 proxy are this app's slots in the
// box-wide allocation: uvicorn = the app's registry port, Vite = 5173 + (port
// - 8000), so all four apps run at once without collisions.
export default defineConfig({
  plugins: [react()],
  build: { outDir: '../frontend_dist', emptyOutDir: true },
  server: {
    port: 5175,
    strictPort: true,
    proxy: { '/api': 'http://localhost:8002' },
  },
})
```

`strictPort` matters: without it Vite quietly takes 5176 when 5175 is busy,
which is `art`'s slot, and two apps end up fighting over one port with nothing
saying so.

- [ ] **Step 3: Serve the bundle, catch-all last**

```python
from pathlib import Path

from fastapi import FastAPI
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
        /api/... and turning a missing endpoint into a 200.
        """
        return FileResponse(DIST / "index.html")
```

- [ ] **Step 4: Build, run the tests, commit**

---

### Task 6: The container, and the production compose file

**Files:**
- Create: `dockerfile`, `entrypoint.sh`, `.dockerignore`
- Create: `docker-compose.prod.yml`
- Create: `tests/unit/test_prod_compose.py`

**Interfaces:**
- Produces: an image serving on 8002, and a compose project of one service
  joined to the external `cg1618` network with the alias `travel-app`.

- [ ] **Step 1: Write the failing test**

Port `media/tests/unit/test_prod_compose.py`, changing the alias to
`travel-app`, the port to 8002, and dropping the bind-mount assertions — this
app has no uploads. Keep: one service only, no published port, `restart:
unless-stopped`, no `container_name`, no `depends_on`, the network `external`,
and the healthcheck probing `/api/health` rather than `/`.

- [ ] **Step 2: Write `entrypoint.sh`**

Port `media/entrypoint.sh` verbatim, including the guard that runs a passed
command instead of the server — without it, `run --entrypoint alembic app
downgrade` silently re-runs the upgrade that just failed, which is what
Task 4's `downgrade` depends on.

- [ ] **Step 3: Write the `dockerfile`**

Multi-stage: node builds `frontend/` into `frontend_dist/`, then
`python:3.13-slim` installs `requirements.txt` and copies both the app and the
built bundle. Copy the shape from `media/dockerfile`.

- [ ] **Step 4: Write `docker-compose.prod.yml`**

```yaml
# Production, on the box. One service: PostgreSQL and the tunnel belong to
# cg1618-apps/platform, whose project runs them on the network this one joins.
#
# At the repository root because compose takes its project directory from the
# compose file's own location and loads .env from there.

services:
  app:
    build:
      context: .
      dockerfile: dockerfile
    image: travel-app:local
    restart: unless-stopped
    env_file:
      - .env
    environment:
      PORT: 8002
    networks:
      cg1618:
        # The generated ingress routes travel.cg1618.com to
        # http://travel-app:8002. Changing this alias without changing apps.yml
        # is a 502 with both files looking correct on their own.
        aliases:
          - travel-app
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8002/api/health', timeout=5)"]
      interval: 30s
      timeout: 10s
      retries: 3
      # Generous: entrypoint.sh runs the migrations before uvicorn binds, and a
      # short start_period would restart a container that is migrating
      # correctly.
      start_period: 120s
    # No depends_on: PostgreSQL is in another compose project and compose
    # cannot order across them. restart: unless-stopped is what covers a cold
    # boot - the container exits when it cannot reach the database, and docker
    # restarts it until it can.

networks:
  cg1618:
    external: true
```

- [ ] **Step 5: Build the image locally and run the tests**

```bash
docker build -t travel-app:local .
venv/Scripts/python.exe -m pytest tests/ -q
```

- [ ] **Step 6: Commit**

---

### Task 7: The development environment

**Files:**
- Create: `dev.ps1`
- Modify: `CLAUDE.md` — the commands section
- Modify: `.env.example` — ports and the local database
- Modify: `docs/README.md`

**Interfaces:**
- Produces: `.\dev.ps1` running uvicorn on 8002 and Vite on 5175 in one window.

- [ ] **Step 1: Create this app's development database**

```bash
docker exec anime_site_postgres_db createdb -U postgres travel
```

One PostgreSQL container, one database per app — the same arrangement as
production, and no fourth container on the laptop.

- [ ] **Step 2: Write `dev.ps1`**

Port `media/dev.ps1`, changing the ports to 8002 and 5175, and keeping the
guard that aborts when a port is already held — a second uvicorn would fail to
bind and surface only as proxy errors from Vite.

- [ ] **Step 3: Prove all four can run at once**

Start `media`'s `dev.ps1` and this one together. Expected: `media` on 8000 and
5173, `travel` on 8002 and 5175, both serving, neither complaining about a
port. This is the constraint the port rule exists for, so it is verified rather
than assumed.

- [ ] **Step 4: Update `CLAUDE.md` and `.env.example`, then commit**

The commands section currently says there is nothing to run. Replace it with
the real commands, the ports, and the one-database-per-app arrangement.

---

## What this plan deliberately does not do

- **No features.** Packing lists are the next plan.
- **No deployment.** `bin/deploy`, the reusable workflow and going live are the
  platform's Step 4 plan, executed after this one. This app stays
  `status: planned` throughout.
- **No uploads.** `travel` needs none; `food` and `art` do, and that is decided
  in the platform's Step 4 plan rather than invented here.
- **No authentication.** Cloudflare Access sits in front of the whole hostname,
  and this app never learns what a password is.
