# mispricing-screen paper-trade exit rules

Owner: Chad
Effective: 2026-05-17
Status: ACTIVE for paper book; **not live until 30-trade / 30-day go-live gate is cleared**.

These rules apply to every position the shaper opens. They are
deterministic so `paper_executor.evaluate_exits()` can run them without
judgment calls.

---

## 1. Profit target (default exit)

- **+50% gain on entry cost → close at next mark.**
- Applies to both income and lottery buckets.
- Why: gives back enough upside to keep the heavy-tail thesis bets
  intact (the +50% is a small fraction of the lottery's expected
  maximum) while compounding the income book.

## 2. Catalyst stop (income bucket only)

- If the position is tied to a dated catalyst, close 1 day before the
  catalyst date.
- Why: theta accelerates into the catalyst, and the gamma payoff has
  largely played out at this point if the move is going to happen.
- Lottery bucket does NOT close pre-catalyst -- the catalyst is a
  reprice trigger, not the resolution.

## 3. Stop loss

- **Income bucket: -50% loss on entry cost → close.**
- **Lottery bucket: -70% loss on entry cost → close.**
- Why: income trades have small expected-value asymmetry; cut losses
  fast. Lottery trades expect higher implied loss probability and
  more time to recover.
- **Catalyst-pending exception (added 2026-05-26):** the loss-stop is
  SUPPRESSED while a position's dated catalyst is still in the future.
  A dated thesis trade is betting on that event; a pre-catalyst drawdown
  is mostly theta and an un-played-out move, so stopping out early would
  kill the thesis before its trigger (the inverse of the original paper
  book's flaw, where trades expired *before* their catalyst and all
  resolved at 0%). The +50% target (rule 1), the 1-day-pre-catalyst exit
  (rule 2), and the expiry-week stop (rule 4) still apply, so risk is
  capped at the event regardless. Once the catalyst date has passed, the
  loss-stop re-activates.

## 4. Expiry stop

- Any position with expiry within 7 days → close at next mark.
- Why: theta in the last week is brutal; avoid pin risk + assignment.
  Lottery positions effectively "roll" by being closed at expiry-week
  and re-opened on the next refresh if the thesis still scores.

## 5. Thesis-break stop (manual, not automated)

- If the trend-corpus claim backing a position transitions from
  `status: active` to `status: superseded`, the operator manually
  flags the position for close on the next daily review.
- The shaper will surface this as a `THESIS_BREAK` row on the daily
  ticket; the executor logs it but does not auto-close (the operator
  decides whether to close immediately or hold to expiry).

## 6. Position sizing safeguards (pre-entry, enforced by shaper)

- Per income trade: max 1-2% of book ($100-200 on a $10k book).
- Per lottery ticket: $200-$400.
- Total per-ticker exposure (sum of all open positions on a single
  ticker, both buckets): max 5% of book ($500 on a $10k book).
- Max concurrent: 15 income + 20 lottery.

## 7. Cadence

The executor runs daily at 16:30 ET as part of `refresh-mispricing.sh`.
Exits are evaluated against the day's chain snapshot mark. Stops trip
at the daily-close mark; no intraday stop logic in v1.
