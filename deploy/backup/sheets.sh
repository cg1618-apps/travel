#!/usr/bin/env bash
# Nightly: copy the travel database into the owner's Google Sheet.
#
#   ./deploy/backup/sheets.sh
#
# Started by deploy/backup/units/travel-sheets.{service,timer} at 04:20, and
# runnable by hand on the box. It runs the backup INSIDE the running app
# container, so it uses exactly the code and the GOOGLE_* settings the app
# itself has; scripts/backup_sheet.py is also the manual CLI.
#
# The repository directory is resolved from this script's own location, never
# from a hardcoded home path: media's lib.sh assumes ~/media, which is wrong
# the moment the checkout lives anywhere else.
#
# Healthchecks is optional. When <repo>/.env.backup exists and sets
# HC_SHEETS_URL, the run pings /start, then success or /fail - so a nightly
# failure is seen rather than silent. .env.backup is kept apart from .env
# because docker-compose.prod.yml hands everything in .env to the app.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd -P)"
cd "${REPO_DIR}"

HC_SHEETS_URL="${HC_SHEETS_URL:-}"
if [ -f .env.backup ]; then
    # shellcheck disable=SC1091  # per-machine and never committed.
    . ./.env.backup
fi

# hc_ping [suffix] [body]
# A failed ping never fails the job it reports on: the dead-man's switch
# catches a missing ping by itself. But it says so on stderr, which systemd
# puts in the journal - a WRONG url would otherwise report to nowhere without
# a trace. The url is redacted because anyone holding it can post a success.
hc_ping() {
    local suffix="${1:-}" body="${2:-}" err="" rc=0
    [ -n "${HC_SHEETS_URL}" ] || return 0
    err="$(curl -fsS -m 10 --retry 3 --retry-delay 5 --data-raw "${body}" \
        "${HC_SHEETS_URL}${suffix}" 2>&1 >/dev/null)" || rc=$?
    [ "${rc}" -eq 0 ] && return 0
    echo "WARNING: Healthchecks ping failed (curl rc=${rc}): ${HC_SHEETS_URL%/*}/<redacted>${suffix}" >&2
    [ -n "${err}" ] && echo "WARNING:   ${err}" >&2
    return 0
}

# One run at a time. Persistent=true fires a missed run at boot, and a hand
# run can coincide with the timer; two backups writing the same tabs at once
# is the thing to prevent. The app also refuses a second backup through its
# own lock, but failing here first keeps that refusal out of the alerts.
LOCK_FILE="${HOME}/.cache/travel-sheets.lock"
mkdir -p "$(dirname "${LOCK_FILE}")"
exec 200>"${LOCK_FILE}"
if ! flock -w 3600 200; then
    echo "Lock ${LOCK_FILE} held for over an hour; giving up." >&2
    hc_ping /fail "lock held for over an hour"
    exit 1
fi

hc_ping /start
echo "==> travel-sheets starting $(date --iso-8601=seconds)"

# -f is required: the production file is not compose's default name. The
# project name comes from the .env beside it, the same as for a deploy.
rc=0
docker compose -f docker-compose.prod.yml exec -T app \
    python -m scripts.backup_sheet || rc=$?

if [ "${rc}" -eq 0 ]; then
    echo "==> done $(date --iso-8601=seconds)"
    hc_ping "" "ok"
else
    echo "==> FAILED rc=${rc} $(date --iso-8601=seconds)" >&2
    hc_ping /fail "backup_sheet exited ${rc}"
fi
exit "${rc}"
