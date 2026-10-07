#!/usr/bin/env bash
# Install the nightly Google Sheets backup on the box, with sudo. It is the
# only part of the backup that needs root. Read it before you run it.
#
#   sudo ./deploy/backup/install.sh
#
# The units in /etc/systemd/system are rendered from deploy/backup/units/,
# with User= set to the user who ran sudo and every @REPO@ replaced by the
# checkout this script is run from. Nothing is hardcoded, so the units point
# at wherever the repository actually is.
#
# RE-RUNNING IS SUPPORTED, and is how the installed units are refreshed after
# they change or the checkout moves: the installed files are copies, and a
# deploy never touches them. Run history in /var/lib/systemd/timers survives.
#
# Enabling the timer does NOT run the job. Persistent=true only catches up a
# run missed by a timer that has run before, so the first backup is 04:20
# tomorrow unless ./deploy/backup/sheets.sh is run by hand once - which also
# arms the Healthchecks check, if HC_SHEETS_URL is set in .env.backup.

set -euo pipefail

[ "$(id -u)" -eq 0 ] || { echo "Run with sudo." >&2; exit 1; }

REAL_USER="${SUDO_USER:?run via sudo, not as root directly}"
REPO="$(cd "$(dirname "$0")/../.." && pwd -P)"
UNITS="${REPO}/deploy/backup/units"

# The path goes into sed's replacement and into ExecStart, and both misread
# anything outside this set (an & or | in sed; a space in ExecStart).
case "${REPO}" in
    *[!A-Za-z0-9._/-]*)
        echo "Refusing: ${REPO} contains characters the units cannot carry." >&2
        exit 1
        ;;
esac

echo "==> Installing units for ${REAL_USER} at ${REPO}"
for unit in travel-sheets.service travel-sheets.timer; do
    sed -e "s|@USER@|${REAL_USER}|g" -e "s|@REPO@|${REPO}|g" \
        "${UNITS}/${unit}" > "/etc/systemd/system/${unit}"
    chmod 644 "/etc/systemd/system/${unit}"
done
systemctl daemon-reload

echo "==> Enabling the timer"
systemctl enable --now travel-sheets.timer

systemctl list-timers travel-sheets.timer --no-pager
echo
echo "Check the path took:  systemctl cat travel-sheets.service | grep ExecStart"
