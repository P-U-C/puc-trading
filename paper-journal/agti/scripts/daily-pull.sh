#!/bin/bash
# AGTI daily-pull cron entrypoint.
#
# Wires the Python script with a clean env (cron does not source ~/.bashrc).
# Logs stdout + stderr to /tmp/cron-agti-daily-pull.log.

set -euo pipefail
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
cd /home/ubuntu/puc-trading/paper-journal/agti

LOGFILE=/tmp/cron-agti-daily-pull.log
echo "=== $(date -u +%FT%TZ) AGTI daily-pull starting ===" >> "$LOGFILE"
/usr/bin/python3 scripts/daily-pull.py >> "$LOGFILE" 2>&1
echo "=== $(date -u +%FT%TZ) AGTI daily-pull complete (exit $?) ===" >> "$LOGFILE"
