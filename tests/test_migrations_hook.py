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
