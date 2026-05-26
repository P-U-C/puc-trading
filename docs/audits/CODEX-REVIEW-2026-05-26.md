# Correctness Review - 2026-05-26

Scope reviewed: `git log --oneline f948ee6~1..HEAD`, `git diff f948ee6~1..HEAD`, plus `mispricing/remark.py` and `scripts/daily_assessment.py`.

## Findings

### MEDIUM - `mispricing/remark.py:63`

`_years()` clamps every interval to at least one day, so the `T <= 0` intrinsic-value branch in `bs_call()` is effectively unreachable for the live re-mark path. If a run is missed and a position remains open on or after expiry, `remark_position()` still prices it with one day of time value, then `evaluate_exits()` closes it as "expiry week" using that stale model mark. Example: an expired OTM spread can retain a positive mark instead of zero.

Concrete fix: use separate time helpers. Keep entry tenor positive only for sigma inversion, but compute current tenor as `max((expiry_d - today).days, 0) / 365.0` so expired positions mark to intrinsic. Add tests for `today == expiry` and `today > expiry`.

### MEDIUM - `mispricing/orchestrator.py:181` / `mispricing/remark.py:152`

`_spot_price()` accepts any truthy float from yfinance, and `remark_positions()` only rejects falsey or `<= 0` values. `float("nan")` passes both checks, which produces `{"mark": NaN, "pct_pnl": NaN}` and then persists non-standard JSON into the staged paper book. Once a position has NaN P&L, all exit comparisons are false, so stops/targets can silently stop firing for that position.

Concrete fix: validate with `math.isfinite()` in `_spot_price()` and again before pricing in `remark_position()`/`remark_positions()`. Return `None` or preserve the old mark for non-finite spot, cost, strikes, or computed mark.

### MEDIUM - `mispricing/remark.py:53` / `mispricing/remark.py:154`

`remark_positions()` re-marks every open position, but the model ignores `structure` and the view passed to `remark_position()` does not include it. Any position with no `strike_upper` is treated as a plain long call, and the volatility inversion always assumes the call-spread entry formula `cost = straddle * 30`. That is correct for current call-spread positions, but it is wrong for shaper-supported `straddle` trades (`cost = straddle_mid * 100`) and approximate `leaps` trades (`cost = spot * 0.10 * 100`). A down move that should help a long straddle is currently marked as a large loss.

Concrete fix: branch by `structure`. Either skip unsupported structures and leave their marks unchanged, or implement separate BS models: call spread, long call/LEAPS, and straddle (`call + put`) with the matching entry-cost inversion.

### MEDIUM - `scripts/daily_assessment.py:256`

`main()` catches individual check failures, but the optional `--badge-repo` path is not protected. `_git()` can raise `FileNotFoundError` or `subprocess.TimeoutExpired`, which would bypass `return 0` and let the assessment fail the cron chain. The commit return code is also ignored; if commit fails but push is a no-op success, `update_badge()` can report success while leaving the README change uncommitted.

Concrete fix: wrap the `update_badge()` call, or all of `update_badge()`, in `try/except Exception` and return `False` on any git exception. Check every git command return code before proceeding, especially `add`, `commit`, and `push`.

### LOW - `mispricing/orchestrator.py:397`

Dropping `mispricing/screens/` fixes the ignored-pathspec failure, but `git add` is now run with `check=False`. If `git add paper-journal/mispricing/` fails for a real reason, the phase continues and may commit whatever was already staged in the index.

Concrete fix: restore checked handling for this narrower pathspec. If the intent is only to tolerate ignored files, inspect `returncode` and stderr, and fail the push phase for non-advisory git-add errors.

## Checked And OK

- `remark.py`: `_norm_cdf()` and the Black-Scholes call formula are mathematically correct for finite positive inputs. The `cost / 30` inversion matches the current call-spread shaper formula `atm_straddle_mid / 2 * 0.6 * 100`, and day-one anchoring works for valid call spreads unless the paid cost already exceeds max spread width.
- `paper_executor.evaluate_exits()`: the date comparison suppresses income/lottery loss stops only while `event_date > today`; +50% target, 1-day-pre-catalyst income exit, and expiry-week exit still fire because they are evaluated independently.
- `orchestrator.py`: the re-marked staged positions are saved before `evaluate_exits()`, and `settle()` reloads the same staged paths, so re-marked values persist through the staged publish.
- `detector._pick_expiry()`: returning `None` for an income chain that cannot clear `event_date + 5d` is handled downstream: the row becomes `no_market`, and the shaper skips it. Lottery expiry selection is unchanged except for seeing more expiries.
- `scripts/daily_assessment.py`: the status-marker regex is appropriate for a single `STATUS:START` / `STATUS:END` block, and the normal `--no-send` path exits 0.
- `mispricing/tests/test_smoke.py`: the new `evaluate_exits()` tests monkeypatch `POSITIONS_PATH`, `CLOSED_PATH`, `TRACKER_PATH`, and `JOURNAL_DIR` to `tmp_path`, so they cannot write the real paper book. The re-mark tests are in-memory only.

## Verification

- `python3 -m pytest mispricing/tests/test_smoke.py -q` -> 19 passed.
- `python3 scripts/daily_assessment.py --no-send` -> exit code 0.
