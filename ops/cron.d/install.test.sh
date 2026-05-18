#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL="$SCRIPT_DIR/install.sh"
HEAD="# BEGIN puc-trading cron-as-code"
TAIL="# END puc-trading cron-as-code"

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

assert_strip() {
    local name="$1"
    local input="$2"
    local expected="$3"
    local got
    got="$(printf '%s' "$input" | bash "$INSTALL" --strip-existing-for-test)"
    [ "$got" = "$expected" ] || fail "$name: expected [$expected], got [$got]"
}

assert_rejects() {
    local name="$1"
    local input="$2"
    if printf '%s' "$input" | bash "$INSTALL" --strip-existing-for-test >/tmp/puc-cron-test.out 2>/tmp/puc-cron-test.err; then
        fail "$name: malformed block was accepted"
    fi
}

assert_strip "block at start" \
    "$HEAD
old
$TAIL
user" \
    "user"

assert_strip "block in middle" \
    "before
$HEAD
old
$TAIL
after" \
    "before
after"

assert_strip "block at end" \
    "user
$HEAD
old
$TAIL" \
    "user"

assert_strip "manual edit inside block" \
    "before
$HEAD
manual edit
$TAIL
after" \
    "before
after"

assert_rejects "missing tail" \
    "before
$HEAD
manual edit
after"

assert_rejects "tail without head" \
    "before
$TAIL
after"

echo "install.test.sh: ok"
