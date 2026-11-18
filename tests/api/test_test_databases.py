"""The test databases are the run's own, and what a crashed run leaves is swept.

Two runs collide only through a shared database NAME. These pin the three
things that keep the name unshared and the server clean: the run's database
is minted, not fixed; a leftover nobody is using goes; and a database
somebody IS using - or has only just created - stays.
"""

import time

import sqlalchemy as sa
from sqlalchemy import text

from tests import databases


def _exists(name: str) -> bool:
    admin = sa.create_engine(databases.server_url("postgres"))
    try:
        with admin.connect() as conn:
            return bool(
                conn.execute(
                    text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": name}
                ).scalar()
            )
    finally:
        admin.dispose()


def _old_name() -> str:
    """A name minted as if by a run that started long before LEFTOVER_AGE."""
    stamp = int(time.time()) - databases.LEFTOVER_AGE - 60
    unique = databases.new_name().rsplit("_", 1)[1]
    return f"{databases.PREFIX}_{stamp}_{unique}"


def test_the_runs_database_is_minted_not_fixed(migrated_database):
    name = sa.engine.url.make_url(migrated_database).database
    assert name != "travel_test"
    assert databases._NAME.match(name), name
    assert name != databases.new_name()


def test_an_old_leftover_with_no_connections_is_dropped(_leftovers_swept):
    name = _old_name()
    databases.create(name)
    try:
        assert name in databases.drop_leftovers()
        assert not _exists(name)
    finally:
        databases.drop(name)


def test_an_old_database_with_a_connection_is_left_alone(_leftovers_swept):
    """The mirror on the same kind of row: old enough to sweep, but in use."""
    name = _old_name()
    databases.create(name)
    holder = sa.create_engine(databases.server_url(name))
    try:
        with holder.connect():
            assert name not in databases.drop_leftovers()
            assert _exists(name)
    finally:
        holder.dispose()
        databases.drop(name)


def test_a_young_database_with_no_connections_is_left_alone(_leftovers_swept):
    """A run between CREATE DATABASE and its first connection looks unused."""
    with databases.scratch() as name:
        assert name not in databases.drop_leftovers()
        assert _exists(name)


def test_nothing_but_a_test_database_name_is_ever_dropped():
    for name in ("travel", "travel_test", "postgres", "media_test_1_ab"):
        try:
            databases.drop(name)
        except AssertionError:
            continue
        raise AssertionError(f"drop() accepted {name!r}")
