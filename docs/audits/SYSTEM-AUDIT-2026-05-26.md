# Permanent Upper Class System Audit - 2026-05-26

Audit scope: local repos under `/home/ubuntu`, user crontab, local runtime processes, current artifacts, local git state, and non-secret configuration patterns. Secret values were not copied into this report.

## 1. System Map

### End-to-end flow

```text
Signals
  public sector sources in /home/ubuntu/trend-corpus/trends/*
  private/sanitized theme intelligence in /home/ubuntu/trend-intel-private/themes/*
  health/consumer events in /home/ubuntu/swell-checker/db.sqlite
  XRPL/PFTL chain events in /home/ubuntu/.pf-scout/chain-index.db
  editorial issue actions in /home/ubuntu/editorial/{issues,outbox,queue}

Corpus / runtime layer
  trend-corpus validates public schemas and public theme objects.
  trend-intel-private emits per-theme scanner seeds:
    /home/ubuntu/trend-intel-private/themes/*/artifacts/opportunity-rows.json
  puc-trading merges those seeds into:
    /home/ubuntu/puc-trading/corpus/convergence-latest.json
  puc-trading mispricing runtime reads convergence + catalysts and writes:
    /home/ubuntu/puc-trading/options-cache/*.json
    /home/ubuntu/puc-trading/mispricing/screens/screen-YYYY-MM-DD.json
    /home/ubuntu/puc-trading/paper-journal/mispricing/{positions.json,closed.json,tracker.md,daily/*.md}
  pf-scout-bot indexer writes chain runtime state:
    /home/ubuntu/.pf-scout/chain-index.db

Surfaces
  pft-validator public scanner:
    /home/ubuntu/pft-validator/scanner/scan-results.json
    /home/ubuntu/pft-validator/scanner/index.html
  pft-validator Herald/lens/subs:
    /home/ubuntu/pft-validator/lens/{graph,audit,health,auth,subs,herald}.json
    /home/ubuntu/pft-validator/herald/latest.json
  editorial:
    /home/ubuntu/editorial/queue/proposed-issues/*
    /home/ubuntu/editorial/queue/archive/YYYY-MM-DD/*
    /home/ubuntu/editorial/outbox/YYYY-MM-DD/*/{issue.json,beehiiv.html,substack.html,PUBLISH.md}
  audience-corpus:
    /home/ubuntu/audience-corpus/corpus/cohorts/*.yaml
    /home/ubuntu/audience-corpus/corpus/brand_voices/*.yaml
  business-guy:
    /home/ubuntu/business-guy/pipeline/crm.sqlite

Revenue / monetization hooks
  SUBS service registry and Herald subscription delivery via pf-scout-bot.
  Editorial Beehiiv/Substack manual publish packages.
  business-guy opportunity research / outreach CRM.
  Paper mispricing book with 30-closed-trade go-live gate.
```

### Cron jobs that move data

User crontab currently contains:

| Schedule | Command | Moves / effect |
|---|---|---|
| `*/10 * * * *` | `/home/ubuntu/pf-scout-bot/deploy/ping-bot.sh` | Heartbeat ping for lens bot via `/tmp/register-bot-mcp.json`. |
| `*/10 * * * *` | `/home/ubuntu/pf-scout-bot/deploy/ping-subs.sh` | Heartbeat ping for SUBS bot via `/tmp/register-subs-mcp-fresh.json`. |
| `*/5 * * * *` | `/home/ubuntu/pf-scout-bot/deploy/ping-subs-bot.sh` | Restarts `bot/src/subs-bot.ts` if not running. |
| `0 * * * *` | `/home/ubuntu/pf-scout-bot/deploy/hourly-pipeline.sh >> /tmp/cron-hourly.log 2>&1` | Crawls PFTL chain, exports `pft-validator/lens/*.json`, Herald JSON, SUBS registry, commits/pushes `pft-validator`. Last seen successful at `2026-05-26T22:10:32Z`. |
| `5 0 * * *` | `deliver-herald.sh` with env from `/home/ubuntu/pf-scout-bot/.env` | Sends Herald to subscribers on-chain. `/tmp/herald-delivery.log` absent at audit time. |
| `10 0 * * *` | `send-expiry-reminders.sh` with env from `/home/ubuntu/pf-scout-bot/.env` | Sends subscription expiry reminders. `/tmp/expiry-reminders.log` absent at audit time. |
| `@reboot` | `/home/ubuntu/pf-scout-bot/deploy/regen-mcp-configs.sh` | Rebuilds `/tmp/register-bot-mcp.json` and `/tmp/register-subs-mcp-fresh.json`. Last log `2026-05-26 01:33`. |
| `0 */2 * * *` | `/home/ubuntu/pf-scout-bot/deploy/check-heartbeats.sh >> /tmp/heartbeat-check.log 2>&1` | Self-healing heartbeat monitor. Last state at `2026-05-26T22:00:26Z`: healthy. |
| `@reboot` | IB Gateway via `/home/ubuntu/ibc/gatewaystart.sh` | Starts paper IB Gateway. Port `4002` is listening. |
| `*/10 * * * *` | `/home/ubuntu/ibc/watchdog-ib-gateway.sh` | IB Gateway watchdog. |
| `55 13 * * *` | `DEPLOY_PUSH=1 bash /home/ubuntu/trend-corpus/scripts/refresh-convergence.sh >> /tmp/refresh-convergence.log 2>&1` | Regenerates `trend-intel-private/themes/*/artifacts/opportunity-rows.json`, merges into `puc-trading/corpus/convergence-latest.json`, commits/pushes. Last run: `scores=123 themes=15`, generated `2026-05-26T13:55:03Z`. |
| `0 14 * * *` | `/home/ubuntu/puc-trading/paper-journal/agti/scripts/daily-pull.sh` | AGTI paper-journal pull. Last artifacts: `/home/ubuntu/puc-trading/paper-journal/agti/daily/2026-05-26.md`. |
| `15 21 * * *` | `DEPLOY_PUSH=1 PREFER_SOURCE=yfinance bash /home/ubuntu/puc-trading/scripts/refresh-mispricing.sh >> .../cron-refresh.log` | Runs mispricing orchestrator, updates paper book, pushes `puc-trading`, deploys scanner book to `pft-validator`. Last run succeeded: `20260526T211501Z`. |
| `45 21 * * *` | `python3 scripts/daily_assessment.py --badge-repo /home/ubuntu/puc-github >> .../cron-assessment.log` | Broken: runs from `/home/ubuntu`, so Python cannot open `/home/ubuntu/scripts/daily_assessment.py`. |
| `0 13 * * *` | `cd /home/ubuntu/swell-checker && ./cron-wrap.sh run ./run.sh >> .../run.log` | Intended local swell run. `run.log` absent, but `db.sqlite` has fetches through `2026-05-26 20:52:36` and events through `21:13:16`. |
| `0 14 * * 1` | `cd /home/ubuntu/swell-checker && ... watchlist.py --snapshot | notify.py stdin >> digest.log` | Weekly swell digest. `digest.log` absent at audit time. |
| `30 14 * * *` | `cd /home/ubuntu/editorial && ./workflow/nightly.sh convergence_daily >> .../nightly.log` | Intended Convergence Daily draft generation. `nightly.log` absent; current `outbox/2026-05-26` appears manual/local, not cron-logged. |
| `0 15 * * 1` | `cd /home/ubuntu/editorial && ./workflow/nightly.sh foreshore >> .../nightly.log` | Intended Foreshore weekly generation. Depends on remote `city-worker-peptides` / `/home/foreshore/foreshore-checker`. |

## 2. Per-Repo Rundown

### `/home/ubuntu/trend-corpus`

Purpose: public sector decision-corpus, schemas, validator, and convergence refresh driver.

Health:
- Running: no daemon; cron `/home/ubuntu/trend-corpus/scripts/refresh-convergence.sh` runs daily at `13:55 UTC`.
- Latest artifact movement: `/tmp/refresh-convergence.log` shows `scores=123 themes=15`, pushed to `puc-trading` at `2026-05-26T13:55:05Z`.
- Tests/validation: `make validate` passed; `pytest tests packages/corpus-validator/tests` passed `27 passed in 2.73s`.
- Git: `8c43e01 2026-05-26 20:45:59 +0000 trend-corpus refresh-convergence: also commit+push trend-intel-private artifacts daily`.
- Worktree: dirty before audit: `M ops/runbooks/install.md`.

Risks / gaps:
1. `scripts/refresh-convergence.sh` hides `git pull` failures with `git -C "$TREND_CORPUS_DIR" pull --quiet --rebase || true`; a stale public corpus checkout can still generate and publish artifacts.
2. `refresh-convergence.sh` treats `trend-intel-private` push failure as a logged warning and continues; artifact backup can silently fail unless `/tmp/refresh-convergence.log` is reviewed.
3. Public theme coverage is mostly complete, but `cicadas` has no `trend-corpus/trends/cicadas` directory; the merge consumes a pre-placed private artifact instead.

### `/home/ubuntu/trend-intel-private`

Purpose: private/semi-private sanitized intelligence graph and per-theme scanner seed artifacts.

Health:
- Running: no daemon; driven by `trend-corpus/scripts/refresh-convergence.sh`.
- Artifacts: `themes/*/artifacts/opportunity-rows.json` exist for 15 themes.
- Freshness: 14 generated at `2026-05-26T13:55:01-02Z`; `themes/cicadas/artifacts/opportunity-rows.json` is from `2026-05-19T03:45:35Z`.
- Tests/validation: `scripts/validate_mirror.py themes` passed; pytest passed `24 passed in 0.38s`.
- Git: `13fd5a6 2026-05-26 20:45:19 +0000 trend-intel track all themes' opportunity-rows.json (private repo)`.
- Worktree: clean.

Risks / gaps:
1. Cicadas is stale by design path: the refresh script logs `skip cicadas: no theme directory` but still merges the private artifact. That artifact has 15 rows and is now the oldest convergence input.
2. The repo stores live scanner seed artifacts in git now, which is good for backup, but the generator/push path is only cron-log-observed; no alert fires on failed artifact push.
3. `scripts/sync-peptides-mirror.sh` remains a documented rsync/stub path to `city-worker-peptides`; actual live synchronization depends on remote host/export availability.

### `/home/ubuntu/puc-trading`

Purpose: private convergence consumer, readonly scanner, mispricing detector, paper book, scanner deploy glue, AGTI paper journal, and daily system assessment.

Health:
- Running: IB Gateway paper mode is up on port `4002`; no persistent `puc-trading` daemon.
- Mispricing cron: latest run `/home/ubuntu/puc-trading/run-state/20260526T211501Z/manifest.json` has `success=true` across `chains,detect,shape,ticket,commit,brief,push`.
- Paper book: `/home/ubuntu/puc-trading/paper-journal/mispricing/positions.json` has 13 open positions; `/home/ubuntu/puc-trading/paper-journal/mispricing/closed.json` has 21 closed rows via public scanner book.
- Convergence: `/home/ubuntu/puc-trading/corpus/convergence-latest.json` validates with 123 scores, generated `2026-05-26T13:55:03Z`.
- Tests: corpus unittest passed `17 tests`; mispricing pytest passed `21 passed`; `scripts/deploy-scanner-results.test.sh` failed.
- Deploy test failure: stale-scan test does not reach freshness validation because the fixture omits `scripts/merge-book-into-scan.py`; output: `ERROR: book merge failed` then `[FAIL] stale-scan did not fail freshness check`.
- Git: `758ed33 2026-05-26 21:17:01 +0000 0xzoz mispricing: refresh at 2026-05-26T21:17:01Z run_id=20260526T211501Z`.
- Worktree: pre-existing untracked `CODEX-REVIEW-2026-05-26.md`.

Risks / gaps:
1. Daily assessment cron is broken: `/home/ubuntu/puc-trading/logs/cron-assessment.log` contains `python3: can't open file '/home/ubuntu/scripts/daily_assessment.py'`. The crontab entry lacks `cd /home/ubuntu/puc-trading` or an absolute script path.
2. Public scanner options data is stale: `/home/ubuntu/pft-validator/scanner/scan-results.json` has `scan_meta.scanned_at = 2026-04-28 21:48:06 UTC`, but the file mtime is fresh because `merge-book-into-scan.py` rewrites the `book` block. `daily_assessment.py` checks file mtime only, so it would report "scanner book fresh" while the options rows are a month old.
3. Cron uses `scripts/deploy-scanner.sh`, not the stricter `scripts/deploy-scanner-results.sh`; the live cron path does not run dashboard shape validation, scan freshness validation, or the `.gitignore` hardening in the newer deploy script.
4. Paper book source of truth is ignored local state: `.gitignore` excludes `paper-journal/mispricing/{positions.json,closed.json}` and `run-state/`. The public scanner JSON contains a copy of the book, but the canonical local paper state has no obvious daily backup beyond GitHub side effects.

### `/home/ubuntu/pft-validator`

Purpose: public GitHub Pages site for validator dashboard, scanner, Herald, SUBS, lens, and public alpha artifacts.

Health:
- Running: static GitHub Pages repo; refreshed by `pf-scout-bot` hourly pipeline and `puc-trading` scanner deploy.
- Latest hourly pipeline: `/tmp/cron-hourly.log` completed at `2026-05-26T22:10:32Z`.
- Latest Herald: `/home/ubuntu/pft-validator/herald/latest.json`, `edition_id=herald-2026-05-26`, `published_at=2026-05-26T22:10:31Z`.
- Scanner JSON: `/home/ubuntu/pft-validator/scanner/scan-results.json`, mtime `2026-05-26T21:17:02Z`, but `scan_meta.scanned_at=2026-04-28 21:48:06 UTC`.
- Tests: `scanner/llm_options_scanner.py --test` passed all 10 inline tests using fixture fallback because it tried `127.0.0.1:7497`, not the live `4002` port.
- Git: `084a0b44 2026-05-26 22:10:31 +0000 pft_chad Herald latest.json v1.1.0: per-section methodology, integrity block, lead, section_order, previews`.
- Worktree: dirty with untracked `jts.ini`, `launcher.log`, `xmlopt.dat`, browser-extension-like directory, `research/`, and alpha/research folders. `.gitignore` currently only contains `.keystone-api-key`.

Risks / gaps:
1. Public scanner frontend handles stale options rows (`scanner/index.html` suppresses results if scan is older than 3 days), but the JSON still exposes stale `results` to other consumers.
2. `.gitignore` is incomplete. `puc-trading/scripts/deploy-scanner-results.sh` would add IB Gateway junk patterns, but the cron path uses `deploy-scanner.sh`, so the public repo remains dirty.
3. Several `pf-scout-bot/deploy/export-*.sh` scripts embed a GitHub PAT pattern directly in source and temporarily rewrite `pft-validator` origin for pushes. The report does not include the token value.

### `/home/ubuntu/swell-checker`

Purpose: consumer/health trend-emergence detector and Foreshore source system.

Health:
- Running: no persistent process found. User crontab has local daily run and weekly digest entries.
- Local DB: `/home/ubuntu/swell-checker/db.sqlite`, size 679,936 bytes; latest fetch `2026-05-26 20:52:36`, latest event `2026-05-26 21:13:16`, latest score date `2026-05-26`.
- Status: `25` candidates, `77` sources, `76` fetches, `26` unprocessed fetches, `354` events, `24` score snapshots, `0` router events.
- Tests: unittest passed `21 tests`.
- Git: `dd7e5ed 2026-05-22 01:22:28 +0000 Chad docs: link parked unified discovery + categorization plan`.
- Worktree: clean.

Risks / gaps:
1. Documentation and runtime disagree. `STATUS.md` says the live state is on `city-worker-301`/`/home/swell/swell-checker`, cron was removed, and the source-of-truth DB was not included. The local `/home/ubuntu/swell-checker/db.sqlite` is active as of today and has fewer events (354) than the documented 703-event city-worker snapshot.
2. Cron log files named in crontab are absent: `/home/ubuntu/swell-checker/run.log` and `digest.log` do not exist, despite local DB activity.
3. Provider discovery is degraded: `provider_state` shows Google related `429`, TikTok Creative Center `404`, and Reddit subscriber delta `403` failures from `2026-05-20`; core ingest sources have no current source errors, but discovery providers are not healthy.
4. Foreshore still depends on remote `city-worker-peptides` / `foreshore-checker` in `editorial/workflow/source_to_issue.py`, not this local DB.

### `/home/ubuntu/editorial`

Purpose: Foreshore and Convergence Daily issue generation, queueing, render packages, and manual publishing layer.

Health:
- Running: no daemon. Crontab has daily Convergence Daily and weekly Foreshore jobs, but `/home/ubuntu/editorial/nightly.log` is absent.
- Current output: `/home/ubuntu/editorial/outbox/2026-05-26/convergence-daily-2026-05-26-cross-sector-brief/` exists with `issue.json`, `beehiiv.html`, `substack.html`, and `PUBLISH.md`.
- Queue archive: `/home/ubuntu/editorial/queue/archive/2026-05-26/` has four manifests; two queued successfully, one `claude_error`, one `structured_render`.
- Canonical `issues/`: newest file is `2026-05-21`; today's `outbox/2026-05-26` issue is not copied to `/home/ubuntu/editorial/issues`.
- Tests: pytest passed `24 passed in 1.22s`.
- Git: `d8ad02e 2026-05-26 22:53:02 +0000 editorial editorial cadence: per-product generation + claude-renderer fixes`.
- Worktree: untracked `outbox/2026-05-26/` and `queue/`.

Risks / gaps:
1. Foreshore source acquisition is a single point of failure: `workflow/source_to_issue.py` shells to `ssh ... city-worker-peptides ... /home/foreshore/foreshore-checker`. `workflow/nightly.sh` explicitly warns that Foreshore fails when the city-worker source is offline.
2. Convergence Daily reads the correct scanner path (`/home/ubuntu/pft-validator/scanner/scan-results.json`) and corpus root (`/home/ubuntu/trend-corpus/trends`), but `load_scanner_state()` does not mark stale scans degraded. Today's issue correctly says scanner results reflect `2026-04-28`, but that is generated content discipline, not a hard contract.
3. Daily assessment checks `/home/ubuntu/editorial/issues` only, so it misses today's generated `outbox/2026-05-26` issue and would report editorial stale even while drafts are ready.
4. Publishing is manual by design; there is no evidence that `site/dist/api/latest.json` has been updated since `2026-05-21`.

### `/home/ubuntu/audience-corpus`

Purpose: private cohort-level audience intelligence corpus with CLI/REST/MCP surfaces for editorial and business-guy.

Health:
- Running: no daemon or cron found.
- Corpus: 3 cohorts and 3 brand voices:
  - `corpus/cohorts/business_guy_outreach_target_v1.yaml`
  - `corpus/cohorts/convergence_daily_operator_reader_v1.yaml`
  - `corpus/cohorts/us_glp1_cleanup_economy_buyer_v1.yaml`
  - `corpus/brand_voices/{business_guy,convergence_daily,foreshore}.yaml`
- Validation/tests: `make validate-corpus` passed `3 cohorts, 3 brand voices`; pytest passed `20 passed in 0.73s`.
- Git: `293c2e0 2026-05-22 00:15:01 +0000 Chad audience-corpus v0: cohort-level audience-intelligence corpus (Codex)`.
- Remote/upstream: no `origin` configured.
- Worktree: clean.

Risks / gaps:
1. No remote backup configured. This repo has no upstream tracking branch.
2. Live-layer integration is not active; docs say Phase 2 should reuse swell-checker, but there is no cron or runtime writer into `corpus/changelog`.
3. MCP layer is a lightweight in-repo abstraction; no MCP server process was found.

### `/home/ubuntu/business-guy`

Purpose: opportunity research, outreach CRM, optional audience-corpus buyer-context seam, and future revenue operations surface.

Health:
- Running: no daemon or cron found.
- CRM: `/home/ubuntu/business-guy/pipeline/crm.sqlite` exists, but has `0` prospects, DMs, replies, calls, deals; `idea_briefs=1`.
- Current CRM row: `foreshore-2026-05-21-issue-1`, verdict `watch`, brief path `/tmp/bg-briefs2/foreshore-2026-05-21-issue-1.md`.
- That brief path is missing at audit time, so the DB points at an ephemeral/nonexistent artifact.
- Tests: unittest passed `22 tests`.
- Git: `9ca2a55 2026-05-22 11:33:41 +0000 Chad Phase 3: fill audience-corpus buyer seam in bg research (Codex)`.
- Remote/upstream: `main` is ahead of `origin/main` by 4 commits. Latest remote ref is `2026-05-17`.
- Worktree: clean.

Risks / gaps:
1. Live output is not durable: `idea_briefs.brief_path` points to `/tmp/bg-briefs2/...`, which no longer exists.
2. No scheduler is installed for scrape/dispatch/reply/digest; this is currently manual despite docs describing cron-driven loops.
3. CRM SQLite is gitignored local state with no evident backup.

### `/home/ubuntu/pf-scout-bot`

Purpose: PF Scout API, XRPL/PFTL indexer, bots, heartbeats, SUBS/Herald delivery, and pft-validator deploy scripts.

Health:
- Running:
  - `python3 -m uvicorn scout-api.main:app --host 127.0.0.1 --port 8420` is listening; `/health` returns `{"status":"ok",...,"version":"0.1.0"}`.
  - `bot/src/subs-bot.ts` is running.
  - PFTL RPC on `5015` is listening.
  - Hourly indexer/export pipeline is active; `/tmp/cron-hourly.log` completed at `2026-05-26T22:10:32Z`.
- Chain DB: `/home/ubuntu/.pf-scout/chain-index.db` is about 5.77 GB, with `1135` accounts, `380192` transactions, `41690` edges, `769` sybil rows, `last_crawl_at=2026-05-26T22:00:01.557Z`.
- Heartbeats: `/tmp/heartbeat-check.log` last says `lens=active subs=active state=healthy`.
- Tests:
  - `pf-scout-bot/indexer`: `vitest` passed `2 files, 33 tests`.
  - `pf-scout-bot/bot`: `npm run lint` failed TypeScript (`chain.ts`, `index.ts`, `send-outreach-wave2.ts`, `subs-followup.test.ts`).
  - `scout-api/main.py` and `scout-api/routes/chain.py` compiled.
- Git: `d28d54a 2026-05-22 13:07:18 +0000 Chad deploy: regen-mcp-configs.sh - rebuild bot/subs heartbeat MCP configs on reboot`.
- Remote/upstream: local `main` ahead of `origin/main` by 5 commits; latest remote ref is `2026-03-19`. Worktree has many modified/untracked bot/deploy/indexer/scout-api files.

Risks / gaps:
1. GitHub is stale relative to production. The live runtime is heavily changed locally; remote `0xzoz/pf-scout-bot` is months behind and local is ahead/uncommitted.
2. Deploy scripts contain embedded GitHub PAT patterns and temporarily rewrite `pft-validator` remote URLs. This report only records the pattern, not token values.
3. `.env` contains many high-value secrets (`BOT_SEED`, `SUBS_SEED`, API keys, IBKR credentials). File is local and ignored, but cron extracts secrets inline into process environments.
4. Bot TypeScript no longer typechecks. The running process may be ahead of typed/tested source.
5. `~/.pf-scout/chain-index.db` is the largest critical local state file; current backups found are from `2026-05-08` (`*.preswap` and `*.corrupt`), not a current rolling backup.

## 3. Cross-Cutting Risks, Ranked

1. Broken observability: `puc-trading` daily assessment cron is currently dead.
   - Evidence: `/home/ubuntu/puc-trading/logs/cron-assessment.log` says Python cannot open `/home/ubuntu/scripts/daily_assessment.py`.
   - Impact: the one job intended to catch stale scanner data, IB outage, bot heartbeat issues, stale corpuses, and paper-book bugs is not running.

2. Public scanner options rows are stale, but freshness checks can still appear green.
   - Evidence: `/home/ubuntu/pft-validator/scanner/scan-results.json` has `scan_meta.scanned_at = 2026-04-28 21:48:06 UTC`; `book.generated_at = 2026-05-26T21:17:02Z`.
   - `puc-trading/scripts/merge-book-into-scan.py` rewrites the file and leaves `scan_meta` unchanged.
   - `puc-trading/scripts/daily_assessment.py` checks scan file mtime only.
   - `pft-validator/scanner/index.html` suppresses stale rows, but `editorial` and other JSON consumers still read the stale `results`.

3. Secrets are embedded in operational surfaces.
   - Credential-bearing git remotes: `trend-corpus`, `trend-intel-private`, `puc-trading`, `swell-checker`, `editorial`.
   - PAT patterns in deploy scripts: especially `pf-scout-bot/deploy/export-*.sh` and `puc-trading/scripts/deploy-scanner.sh` token extraction from `pf-scout-bot/deploy/export-graph.sh`.
   - Secret-bearing local files: `/home/ubuntu/pf-scout-bot/.env`, `/home/ubuntu/pf-scout-bot/bot/.keystone-api-key`, `/home/ubuntu/swell-checker/.env`, `/home/ubuntu/editorial/.env`, `/home/ubuntu/pft-validator/.keystone-api-key`.

4. Single points of failure around off-box / temporary state.
   - Foreshore generation shells to `city-worker-peptides` and `/home/foreshore/foreshore-checker`; if that host/source is down, Foreshore generation fails.
   - Heartbeat MCP configs live in `/tmp` and are rebuilt on reboot; this has a self-healing job now, but the design is still tmp-file dependent.
   - `pf-scout-bot` live state depends on `/home/ubuntu/.pf-scout/chain-index.db`.

5. Critical runtime state is gitignored or outside repos with weak backup signals.
   - `puc-trading`: `run-state/`, `options-cache/`, `paper-journal/mispricing/{positions.json,closed.json}`, AGTI `cron-runs/`, extracted JSONs.
   - `swell-checker`: `db.sqlite`.
   - `business-guy`: `pipeline/crm.sqlite`.
   - `pf-scout-bot`: `/home/ubuntu/.pf-scout/chain-index.db`, subscriber JSON logs, delivery logs.
   - Some artifacts are mirrored into public JSON or git commits, but canonical runtime state is still local-first.

6. Local production is ahead of GitHub in multiple places.
   - `pf-scout-bot`: local `main` ahead 5, many uncommitted/untracked files, remote last seen `2026-03-19`.
   - `business-guy`: local `main` ahead 4, remote last seen `2026-05-17`.
   - `audience-corpus`: no remote configured.
   - These repos can be alive locally while looking stale or incomplete on GitHub.

7. Tests do not fully cover the deployed path.
   - `puc-trading/scripts/deploy-scanner-results.test.sh` currently fails before its stale freshness assertion because the fixture lacks `merge-book-into-scan.py`.
   - Cron uses `deploy-scanner.sh`, not the tested `deploy-scanner-results.sh`.
   - `pft-validator/scanner/llm_options_scanner.py --test` passes with fixture fallback and attempts `127.0.0.1:7497`, while the live IB Gateway is on `4002`.

8. Editorial generated state is split across `issues`, `queue`, `outbox`, and `site/dist`.
   - Today's Convergence Daily output exists in `outbox/2026-05-26`, but `/home/ubuntu/editorial/issues` and `site/dist/api/latest.json` remain at May 20/21-era state.
   - Daily assessment watches only `editorial/issues`.

## 4. Interconnection Integrity

### Contracts that are consistent

- `trend-corpus/scripts/refresh-convergence.sh` writes the expected `trend-intel-private/themes/*/artifacts/opportunity-rows.json` and merges them into `/home/ubuntu/puc-trading/corpus/convergence-latest.json`.
- `puc-trading/corpus/convergence-latest.json` validates through `puc-trading` scanner validation: `123 scores from 2026-05-26T13:55:03Z`.
- `puc-trading/scanner/run_live_scan.py` default convergence path is `/home/ubuntu/puc-trading/corpus/convergence-latest.json`.
- `puc-trading/scripts/merge-book-into-scan.py` writes book state into `/home/ubuntu/pft-validator/scanner/scan-results.json`.
- `pft-validator/scanner/index.html` fetches `/scanner/scan-results.json`.
- `editorial/workflow/source_to_issue.py` reads:
  - `/home/ubuntu/puc-trading/paper-journal/mispricing/positions.json`
  - `/home/ubuntu/puc-trading/paper-journal/mispricing/closed.json`
  - `/home/ubuntu/trend-corpus/trends`
  - `/home/ubuntu/pft-validator/scanner/scan-results.json`
- `business-guy` calls `audience-corpus` through its CLI with `PYTHONPATH=/home/ubuntu/audience-corpus/src`; the CLI supports `route`, `lookup`, `render`, `validate-corpus`, and `compare`.

### Contract mismatches / weak spots

- Scanner freshness semantics are inconsistent:
  - Public frontend treats stale scan rows as paused.
  - `daily_assessment.py` treats fresh file mtime as fresh scanner.
  - `editorial` reads stale scanner rows without a hard stale/degraded flag.

- Deployed scanner script is not the validated deploy script:
  - Cron path: `refresh-mispricing.sh` -> `deploy-scanner.sh`.
  - Better path exists: `deploy-scanner-results.sh`, with shape/freshness/secret checks and `.gitignore` hardening.
  - The better path's shell test currently fails due fixture setup.

- Daily assessment paths are wrong/incomplete:
  - Crontab does not `cd /home/ubuntu/puc-trading` and uses relative `scripts/daily_assessment.py`.
  - Assessment checks `editorial/issues`, not `editorial/outbox` or `queue/archive`.
  - Assessment checks scanner file age, not `scan_meta.scanned_at`.

- Foreshore source contract is remote-only:
  - `swell-checker` local DB is active, but `editorial` Foreshore fetch does not read it.
  - It shells to `city-worker-peptides` and `/home/foreshore/foreshore-checker`.

- `business-guy` durable artifact contract is broken:
  - CRM row exists, but `idea_briefs.brief_path` points to a missing `/tmp/bg-briefs2/...` file.

## 5. Top 5 Recommendations

1. Fix observability first.
   - Change crontab entry to use an absolute path or `cd /home/ubuntu/puc-trading && python3 scripts/daily_assessment.py ...`.
   - Update `daily_assessment.py` to check `scan_meta.scanned_at`, not scanner file mtime.
   - Include `editorial/outbox/*/issue.json` and `queue/archive/*/manifest-*.json` in the editorial freshness check.

2. Move the live scanner deploy onto the validated path.
   - Either replace `deploy-scanner.sh` with `deploy-scanner-results.sh` or have `deploy-scanner.sh` call the same shape/freshness/secret checks.
   - Fix `deploy-scanner-results.test.sh` by copying/stubbing `scripts/merge-book-into-scan.py` into the temp fixture so the stale-scan test reaches the freshness assertion.
   - Make cron fail/alert if scanner data is stale rather than publishing a book-only mtime refresh.

3. Remove embedded GitHub credentials from remotes and deploy scripts.
   - Replace credential-bearing repo origins with normal HTTPS or SSH remotes.
   - Move PAT use to a single protected credential source (`gh` auth, deploy key, or env-injected token) and stop committing PAT patterns in shell scripts.
   - Keep reporting at the file/pattern level; do not print secret values.

4. Add backup/restore discipline for local runtime state.
   - Daily snapshot: `puc-trading` paper book + run manifests, `swell-checker/db.sqlite`, `business-guy/pipeline/crm.sqlite`, `/home/ubuntu/.pf-scout/chain-index.db` plus small `.pf-scout/*.json` logs.
   - Store encrypted backups outside the live repos, with a restore drill.
   - For small JSON state (`business-guy` briefs, paper book summaries), prefer durable repo paths over `/tmp`.

5. Reconcile GitHub/live drift.
   - `pf-scout-bot`: decide what local changes are production, get TypeScript green, commit/push or split experimental files out.
   - `business-guy`: push the four ahead commits after checking the missing `/tmp` brief path issue.
   - `audience-corpus`: add an origin/upstream.
   - `pft-validator`: apply the intended ignore patterns for IB/browser runtime junk and keep the public repo clean.
