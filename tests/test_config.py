"""Configuration, and the one rule about it that has bitten this project."""

import importlib

import pytest


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


def test_defaults_are_intact_for_a_test_that_patches_nothing():
    # Ordered after the two patching tests in this file. Under the leak this
    # sees postgres_host == "db" from the previous test and fails, which is
    # the whole point of asserting it here rather than trusting the fixture.
    from app import config

    assert config.settings.postgres_host == "localhost"


def test_a_misspelt_app_env_is_refused():
    """`APP_ENV=prod` is not production, and must not be read as one.

    The failure this prevents is silent in both directions. Read as a real
    environment it hardens a development machine; read as a development one it
    softens a real one - and the only visible symptom either way is the log
    format being wrong, months later.
    """
    from app.config import Settings

    with pytest.raises(ValueError, match="APP_ENV must be one of"):
        Settings(app_env="prod")


@pytest.mark.parametrize("value", ["development", "production"])
def test_the_known_environments_are_accepted(value):
    """The mirror. Without it, a validator refusing everything passes above."""
    from app.config import Settings

    assert Settings(app_env=value).app_env == value


def test_is_development_is_the_narrow_predicate():
    """There is no is_production, deliberately.

    Any environment name added later is treated as a real one by default and
    gets the careful behaviour, rather than escaping it by not being named.
    """
    from app.config import Settings

    assert Settings(app_env="development").is_development is True
    assert Settings(app_env="production").is_development is False
