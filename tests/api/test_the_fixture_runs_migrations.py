"""The fixture's own discipline, asserted rather than assumed.

A fixture that builds its schema with `create_all` tests the models against
themselves and says nothing about the migrations - which is how the media
tracker shipped 145 revisions on a chain that could not build from zero. These
are the tests that would go red if someone "simplified" conftest.py back to
create_all, which is the whole reason they exist.
"""

from sqlalchemy import text


def test_the_test_database_is_stamped_at_head(db_session):
    # create_all leaves no alembic_version row at all. This one assertion is
    # the entire difference between the two ways of building the fixture.
    stamped = db_session.execute(
        text("SELECT version_num FROM alembic_version")
    ).scalar()
    assert stamped is not None


def test_a_row_written_in_one_test_is_rolled_back(db_session):
    # Paired with the test below, and it has to come first in the file:
    # pytest runs a module's tests in definition order. DDL is transactional
    # in PostgreSQL, so the table goes away with everything else.
    db_session.execute(text("CREATE TABLE rollback_probe (id integer)"))
    db_session.execute(text("INSERT INTO rollback_probe VALUES (1)"))
    assert db_session.execute(text("SELECT count(*) FROM rollback_probe")).scalar() == 1


def test_and_is_not_visible_to_the_next_one(db_session):
    # If the transaction above had committed, this table would exist. The
    # rollback is silent when it breaks - every test still passes individually
    # and the suite starts failing in whatever order it happens to run in.
    assert db_session.execute(text("SELECT to_regclass('rollback_probe')")).scalar() is None
