#!/bin/sh
set -e  # Exit immediately if a command fails

# A command passed to the container runs INSTEAD of the server, rather than
# being silently discarded.
#
# Without this, `docker compose run app <anything>` ignored its arguments and
# ran the migrate-then-serve path below. That is how deploy/rollback.sh's
# `run app alembic downgrade <target>` re-ran the upgrade it was trying to
# reverse, on the box, during a rollback - the command vanished and the failure
# looked like the migration failing twice.
#
# `docker compose up` passes no arguments, so the normal path is unchanged.
# rollback.sh also passes --entrypoint explicitly and does not rely on this;
# both exist because the failure mode was silence, and one guard against
# silence is not enough.
if [ "$#" -gt 0 ]; then
    exec "$@"
fi

echo "🚀 Running Alembic Migrations..."
alembic upgrade head

echo "✨ Starting Uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers --forwarded-allow-ips='*'
