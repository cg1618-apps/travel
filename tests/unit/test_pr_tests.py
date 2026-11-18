"""What a pull request into `dev` runs in its own CI run (scripts/pr_tests.py).

Pure: the changed paths and the files' text are handed in, so no git and no
PostgreSQL. The merge queue runs the full suite; these pin what the pull
request's own, faster run may leave to it.
"""

from scripts.pr_tests import MIGRATION_GUARDS, select, unit_tier

TESTS = [
    "tests/test_config.py",
    "tests/test_health.py",
    "tests/unit/test_leg_types.py",
    "tests/api/test_trip_router.py",
    "tests/api/test_notes.py",
    "tests/api/test_migrations_build_the_schema.py",
    "tests/api/test_migration_round_trip.py",
    "tests/api/test_trip_backups.py",
]

FILES = {
    "alembic/versions/t7rip0000007_something.py": 'revision: str = "t7rip0000007"\n',
    "tests/api/test_trip_backups.py": 'migrate(db, "upgrade", previous("t7rip0000007"))\n',
    "tests/api/test_migrations_build_the_schema.py": 'previous("k1ind0000001")\n',
    "tests/api/test_notes.py": "# mentions t7rip0000007 unquoted, in prose\n",
}

UNIT = ["tests/unit", "tests/test_config.py", "tests/test_health.py"]


def _select(*changed):
    return select(list(changed), FILES.get, TESTS)


def test_the_unit_tier_is_everything_outside_tests_api():
    assert unit_tier(TESTS) == UNIT


def test_a_route_change_runs_the_unit_tier_and_the_tests_it_touches():
    assert _select("app/routers/trip.py", "tests/api/test_trip_router.py") == [
        *UNIT,
        "tests/api/test_trip_router.py",
    ]


def test_an_edited_unit_test_is_not_named_twice():
    assert _select("tests/unit/test_leg_types.py", "tests/test_config.py") == UNIT


def test_a_frontend_change_runs_the_unit_tier_alone():
    assert _select("frontend/src/App.jsx") == UNIT


def test_a_new_revision_runs_the_guards_and_its_own_tests_only():
    """The mirror is in the same assertion: test_notes.py names the revision
    only unquoted, and the build file names another one - neither is picked
    for this revision beyond what the guards already add."""
    assert _select("alembic/versions/t7rip0000007_something.py") == [
        *UNIT,
        *MIGRATION_GUARDS,
        "tests/api/test_trip_backups.py",
    ]


def test_a_model_change_runs_the_migration_guards():
    assert _select("app/models/trip.py") == [*UNIT, *MIGRATION_GUARDS]


def test_a_change_to_the_harness_runs_everything():
    for path in (
        "tests/conftest.py",
        "tests/databases.py",
        "tests/api/conftest.py",
        "requirements-dev.txt",
        "alembic/env.py",
        ".github/workflows/ci.yml",
        "scripts/pr_tests.py",
    ):
        assert _select(path, "app/routers/trip.py") is None, path


def test_an_empty_diff_runs_everything():
    assert _select() is None
