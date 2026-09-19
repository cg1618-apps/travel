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


@pytest.fixture(autouse=True)
def restore_config_defaults():
    yield
    from app import config

    importlib.reload(config)
