#!/bin/bash
# refresh-mispricing.sh
#
# Daily orchestration of the mispricing-screen pipeline:
#   1. Refresh option chains for all 108 convergence tickers
#   2. Run the mispricing detector against the catalyst calendar
#   3. Shape candidates into income + lottery buckets
#   4. Write today's ticket markdown
#   5. Settle the paper-executor (evaluate exits, mark positions)
#   6. Send morning brief to Telegram
#
# Env:
#   DEPLOY_PUSH         1 = git push puc-trading after the run (default 0)
#   PREFER_SOURCE       ib | yfinance (default ib; falls back per-ticker)
#   LIVE_PUSH           1 = place real IB orders (default 0; gated 30-day)
#
# Output:
#   /tmp/refresh-mispricing.log
#   ~/puc-trading/options-cache/<ticker>-<DATE>.json (chain snapshots)
#   ~/puc-trading/mispricing/screens/screen-<DATE>.json
#   ~/puc-trading/paper-journal/mispricing/daily/<DATE>.md
#   ~/puc-trading/paper-journal/mispricing/{positions,closed}.json
#   ~/puc-trading/paper-journal/mispricing/tracker.md

set -uo pipefail

PUC_TRADING_DIR="${PUC_TRADING_DIR:-$HOME/puc-trading}"
PREFER_SOURCE="${PREFER_SOURCE:-ib}"

log() { printf "[%s] %s\n" "$(date -u +%FT%TZ)" "$*"; }

cd "$PUC_TRADING_DIR"

log "phase 1: refresh chains (prefer=$PREFER_SOURCE)"
python3 -c "
import json
from pathlib import Path
from mispricing import ib_chain

cv = json.loads(Path('$PUC_TRADING_DIR/corpus/convergence-latest.json').read_text())
tickers = sorted({r['ticker'] for r in cv.get('scores', []) if r.get('ticker')})
print(f'pulling chains for {len(tickers)} tickers (prefer=$PREFER_SOURCE)')
summary = ib_chain.refresh_universe(tickers, prefer='$PREFER_SOURCE')
ok = sum(1 for s in summary.values() if s.get('contracts', 0) > 0)
print(f'chain pull: {ok}/{len(tickers)} with contracts')
"

log "phase 2: detector"
python3 -c "
from mispricing import detector
rows = detector.screen(prefer_source='$PREFER_SOURCE')
path = detector.write_screen(rows)
print(f'screen rows: {len(rows)} -> {path}')
"

log "phase 3+4: shaper + tickets"
python3 -c "
import datetime as dt, json
from pathlib import Path
from mispricing import detector, shaper, tickets, paper_executor

screen_path = sorted(Path('$PUC_TRADING_DIR/mispricing/screens').glob('screen-*.json'))[-1]
data = json.loads(screen_path.read_text())
rows = [detector.MispricingRow(**r) for r in data['rows']]
held = paper_executor.held_positions_for_shaper()
candidates = shaper.shape(rows, held_positions=held)
text = tickets.build_daily(screen_rows=rows, candidates=candidates,
                            held_positions=held, closes=[])
ticket_path = tickets.write_daily(text)
print(f'ticket: {ticket_path}')
print(f'candidates: income={sum(1 for c in candidates if c.bucket==\"income\")} '
      f'lottery={sum(1 for c in candidates if c.bucket==\"lottery\")}')
# Open paper positions for the candidates we just emitted.
new = paper_executor.open_paper(candidates)
print(f'opened {len(new)} paper positions')
"

log "phase 5: executor settle"
python3 -c "
from mispricing import paper_executor
positions = paper_executor._load_positions()
just_closed = paper_executor.evaluate_exits(positions)
summary = paper_executor.settle()
print(f'closed_today={summary[\"closed_today\"]} open={summary[\"open\"]} '
      f'closed_total={summary[\"closed_total\"]}')
"

log "phase 6: morning brief"
python3 -c "
from mispricing import morning_brief
sent = morning_brief.send_brief(dry_run=False)
print(f'morning_brief sent={sent}')
"

if [ "${DEPLOY_PUSH:-0}" = "1" ]; then
    log "DEPLOY_PUSH=1: committing journal + tracker"
    cd "$PUC_TRADING_DIR"
    git add paper-journal/mispricing/ mispricing/screens/ options-cache/
    if ! git diff --cached --quiet; then
        git commit -m "mispricing: refresh at $(date -u +%FT%TZ)"
        git push origin main || true
    fi
fi

log "done"
