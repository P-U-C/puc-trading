#!/bin/bash
# install.sh - sync ops/cron.d/puc-trading.cron into the user crontab.
#
# Idempotent. Replaces any existing puc-trading-related lines based on
# a sentinel comment; appends fresh ones from the source. Diff before
# install prints what's about to change.

set -euo pipefail

SOURCE="$(dirname "$0")/puc-trading.cron"
SENTINEL_HEAD="# BEGIN puc-trading cron-as-code"
SENTINEL_TAIL="# END puc-trading cron-as-code"

strip_existing_block() {
    awk -v head="$SENTINEL_HEAD" -v tail="$SENTINEL_TAIL" '
        BEGIN {skip = 0}
        $0 == head {
            if (skip == 1) {
                print "nested puc-trading cron sentinel block" > "/dev/stderr"
                exit 42
            }
            skip = 1
            next
        }
        $0 == tail {
            if (skip == 0) {
                print "tail sentinel without matching head" > "/dev/stderr"
                exit 42
            }
            skip = 0
            next
        }
        skip == 0 {print}
        END {
            if (skip == 1) {
                print "missing tail sentinel for puc-trading cron block" > "/dev/stderr"
                exit 42
            }
        }
    '
}

if [ "${1:-}" = "--strip-existing-for-test" ]; then
    strip_existing_block
    exit $?
fi

if [ ! -f "$SOURCE" ]; then
    echo "FATAL: $SOURCE missing" >&2
    exit 1
fi

# Build the new block: sentinel + cron lines only (strip comments + blanks).
NEW_BLOCK=$(printf '%s\n' "$SENTINEL_HEAD"
            grep -vE '^\s*(#|$)' "$SOURCE"
            printf '%s\n' "$SENTINEL_TAIL")

# Pull current crontab; strip any existing puc-trading sentinel block.
CURRENT=$(crontab -l 2>/dev/null || true)
if ! STRIPPED=$(printf '%s\n' "$CURRENT" | strip_existing_block); then
    echo "FATAL: existing crontab has a malformed puc-trading sentinel block; refusing to install." >&2
    exit 1
fi

# Stitch: stripped current + new block.
NEW_CRONTAB=$(printf '%s\n\n%s\n' "$STRIPPED" "$NEW_BLOCK")

echo "--- diff (current -> proposed) ---"
diff <(echo "$CURRENT") <(echo "$NEW_CRONTAB") || true
echo "--- end diff ---"

echo
read -rp "install this crontab? [y/N] " ans
case "$ans" in
    y|Y|yes|YES) echo "$NEW_CRONTAB" | crontab - && echo "installed." ;;
    *) echo "aborted." ;;
esac
