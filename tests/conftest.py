"""Test-wide fixtures.

`app.config.settings` is a module-level object built from the environment at
import time, so a test that monkeypatches the environment and reloads the
module leaves the reloaded object behind for every later test in the session.

The reload has to happen AFTER monkeypatch has undone its changes. Fixture
teardown is LIFO, and an autouse fixture is set up before the function-scoped
monkeypatch it shares a test with — so this fixture's teardown runs last, with
the real environment restored, which is exactly the window the reload needs.
"""

import importlib
from pathlib import Path

import pytest

from app.config import settings


def admin_url(database: str) -> str:
    """`settings.sqlalchemy_database_url` with only the trailing db name swapped.

    Both the from-zero migration test and the API fixtures need an
    administrative connection, and neither may assume the shared PostgreSQL's
    superuser password — that value is per-machine and not something a test
    should hardcode. Deriving it from the app's own settings means the tests
    work wherever the app itself would.

    It lives here rather than in either caller because two copies of this rule
    is two places to get it wrong.
    """
    base = settings.sqlalchemy_database_url
    return base.rsplit("/", 1)[0] + f"/{database}"


VERSIONS = Path(__file__).resolve().parents[1] / "alembic" / "versions"


def _revision_pairs() -> list[tuple[str, str | None]]:
    """(revision, down_revision) read from the revision FILES.

    Deliberately not via Alembic's own ScriptDirectory. These helpers exist to
    check what the application reports about its chain, and checking that
    against Alembic would be comparing the code to a reimplementation of
    itself - green whether or not either one is right.
    """
    pairs = []
    for path in sorted(VERSIONS.glob("*.py")):
        revision = down = None
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("revision ="):
                revision = line.split("=", 1)[1].strip().strip("\"'")
            elif line.startswith("down_revision ="):
                value = line.split("=", 1)[1].strip().strip("\"'")
                down = None if value == "None" else value
        if revision:
            pairs.append((revision, down))
    return pairs


def revision_ids() -> set[str]:
    """Every revision id this repository ships."""
    return {revision for revision, _ in _revision_pairs()}


def head_revision() -> str:
    """The one revision nothing else claims as its parent."""
    pairs = _revision_pairs()
    parents = {down for _, down in pairs if down}
    heads = [revision for revision, _ in pairs if revision not in parents]
    assert len(heads) == 1, f"expected one head, found {heads}"
    return heads[0]


@pytest.fixture(autouse=True)
def restore_config_defaults():
    yield
    from app import config

    importlib.reload(config)


@pytest.fixture(autouse=True)
def _no_real_google_sheets():
    """Make building a real gspread client fail, in every test.

    The developer's `.env` holds the real service-account key and the real
    sheet id, and the test database is EMPTY or nearly so. A test that reached
    the real sheet through the backup would overwrite the owner's only
    off-box copy with test rows - media lost 16,774 rows to exactly that shape
    on 2026-09-12. Tests hand `SheetClient` a `FakeSpreadsheet` instead.

    Blocked at `gspread.Client` itself, not at this app's helper, so no path
    to Google - `gspread.authorize`, `service_account`, a future helper - gets
    round it. `tests/unit/test_no_real_sheets_in_tests.py` proves it is armed:
    without that, deleting this fixture would break nothing visible.

    Patched by hand rather than through `monkeypatch`: an autouse fixture that
    requests `monkeypatch` sets it up early, so its undo would run AFTER
    `restore_config_defaults` reloads the config - and a test's patched
    environment would be read into the reloaded settings.
    """
    import gspread

    def _blocked(self, *args, **kwargs):
        raise AssertionError(
            "A test tried to build a real gspread client. Its writes would land "
            "on the owner's real sheet; hand SheetClient a FakeSpreadsheet instead."
        )

    original = gspread.Client.__init__
    gspread.Client.__init__ = _blocked
    try:
        yield
    finally:
        gspread.Client.__init__ = original
