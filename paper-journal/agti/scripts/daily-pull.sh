#!/bin/bash
# AGTI daily-pull cron entrypoint.
#
# Chain:
#   1. daily-pull.py    -- fetch latest report, save raw, mark + exit + fill open positions
#   2. extract-signals.py -- extract structured signals from the new raw via `claude -p`,
#                            update positions.json with new entries / direction flips
#   3. notify-telegram.py -- push the day's summary to Chad's Telegram via the bot
#
# Logs all stdout + stderr to /tmp/cron-agti-daily-pull.log. Cron-friendly:
# steps 2 and 3 are guarded so a failure in either does not break the next.

set -uo pipefail
export PATH=/home/ubuntu/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
cd /home/ubuntu/puc-trading/paper-journal/agti

LOGFILE=/tmp/cron-agti-daily-pull.log
echo "=== $(date -u +%FT%TZ) AGTI daily-pull starting ===" >> "$LOGFILE"

# Step 1: pull report + mark/exit/fill open positions
/usr/bin/python3 scripts/daily-pull.py >> "$LOGFILE" 2>&1
PULL_EXIT=$?
echo "  pull exit: $PULL_EXIT" >> "$LOGFILE"

# Step 2: signal extraction (best-effort; do not block subsequent steps)
if [ $PULL_EXIT -eq 0 ]; then
    /usr/bin/python3 scripts/extract-signals.py >> "$LOGFILE" 2>&1
    echo "  extract exit: $?" >> "$LOGFILE"
else
    echo "  extract skipped (pull failed)" >> "$LOGFILE"
fi

# Step 3: telegram push (best-effort)
/usr/bin/python3 scripts/notify-telegram.py >> "$LOGFILE" 2>&1
echo "  notify exit: $?" >> "$LOGFILE"

echo "=== $(date -u +%FT%TZ) AGTI daily-pull complete ===" >> "$LOGFILE"
