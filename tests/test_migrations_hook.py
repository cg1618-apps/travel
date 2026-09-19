"""The hook's shape. The platform calls it; a wrong exit code misleads a deploy."""

import shutil
import subprocess
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


def test_an_unknown_subcommand_exits_non_zero_and_says_so():
    # The other tests read the script's text, which cannot tell a working
    # branch from an empty one. This runs it: bash is available here and the
    # usage path touches neither docker nor the database.
    # Try to find bash in common locations
    bash_candidates = [
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files (x86)\Git\bin\bash.exe",
        shutil.which("bash"),
    ]
    bash_exe = next((b for b in bash_candidates if b and Path(b).exists()), None)
    if not bash_exe:
        bash_exe = shutil.which("bash") or "bash"

    result = subprocess.run(
        [bash_exe, str(HOOK), "nonsense"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0, result.stdout
    assert "usage:" in result.stderr.lower(), result.stderr
    assert result.stdout.strip() == "", "usage belongs on stderr, not stdout"
