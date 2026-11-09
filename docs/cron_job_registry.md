# Cron Job Registry

Authoritative list of OpenClaw automations on this host. Verified 2026-11-08 via
`openclaw cron list --all --json`. The live store is the CLI/gateway, not this file —
use `openclaw cron list --all --json` to get current IDs and state.

**Hard rule (from the workspace skill):** no enabled job may use
`payload.kind: systemEvent` + `sessionTarget: main`. That combination enqueues into the
main session's in-memory event queue (cap 20) and fails with
`System event queue is full (20 pending)` once the queue saturates. As of 2026-11-08
**zero** enabled jobs remain on that shape.

<!-- project: github.com/shaoweil9921/myFin -->

## Enabled jobs

| Name | Schedule (ET) | Script / Payload | Pattern | Status 2026-11-08 |
|------|---------------|-----------------|---------|-------------------|
| Cron Job Watchdog | `0 * * * *` (stagger 300s) | monitors other jobs | `agentTurn` + `isolated` | ok |
| heartbeat-main | every 2h | heartbeat lane | `heartbeat` + `main` | ok / skipped quiet-hours |
| Memory Dreaming Promotion | `0 3 * * *` | built-in | `agentTurn` + `isolated` | ok |
| Morning Heartbeat - 7:30AM ET | `30 7 * * 1-5` | heartbeat lane | `agentTurn` + `isolated` | ok |
| discord-fetch-signals | `*/15 8-17 * * 1-5` | `_run_discord_fetch.py` | `command` + `isolated` | ok |
| Obsidian Trading Vault - Daily Git Push | `30 8 * * 1-5` | git push of Obsidian vault | `agentTurn` + `isolated` | ok |
| fintech-db-backup-monitor | `0 9 * * 1` | agent checks `C:\Data\postgres_backup\` | `agentTurn` + `isolated` | ok |
| Stock Data Update | `0 10-17 * * 1-5` | `update_stock_data_check.py` | `agentTurn` + `isolated` | ok |
| Finviz GapperMid - Morning Extraction | `5 13 * * 1-5` | `scrape_finviz.py` + `load_finviz_data.py` | `agentTurn` + `isolated` | ok |
| Letter Position Tracker - Daily EOD | `30 16 * * 1-5` | `letter_position_tracker.py` | `command` + `isolated` | ok |
| Stock Technical Backfill | `15 17 * * 1-5` | `backfill_stock_technical.py` | `agentTurn` + `isolated` | ok |
| EOD Memory Save | `0 22 * * 1-5` | memory save | `agentTurn` + `isolated` | ok |
| Ashley Discord - Daily Signals File Generator | `0 23 * * 1-5` | `_run_daily_signals.py` | `command` + `isolated` | ok |
| fintech-db-backup | `0 13 * * 6` | `db_backup.py` | `command` + `isolated` | ok |
| ITMC Letter Extraction | `0 20 * * 0` | agent turn reading `docs/itmc_extraction_runbook.md` | `agentTurn` + `isolated` | ok |

## Disabled jobs

IBD 50 Extract, Jarsy Token List Extraction, Daily Trading Study,
Schwab API Monitor.

## IDs (2026-11-08)

| Job | ID |
|-----|-----|
| Cron Job Watchdog | `7449b395-fb91-49d0-b4a6-11b49b13330f` |
| Letter Position Tracker - Daily EOD | `fc414b43-3514-4562-9759-306b8f05de47` |
| Ashley Discord - Daily Signals File Generator | `3a3fcfed-09c1-41e8-9e91-ea918be5e367` |
| fintech-db-backup | `46f8450f-ff84-42fb-893a-04976da8ed00` |
| fintech-db-backup-monitor | `4c124fed-84c6-4a3e-93f0-6367ab693e43` |
| ITMC Letter Extraction | `4abcd3c1-b9e6-4b3d-af45-efe1421e018d` (recreated 2026-11-08; the old `c125cd06-…` was removed) |

## Changes made 2026-11-08

- Converted 5 jobs off `systemEvent` + `main`: `fc414b43`, `3a3fcfed`,
  `46f8450f`, `4c124fed` to `isolated` (`command` for pure scripts, `agentTurn` for
  work that needs a model), and the ITMC job to `agentTurn` + `isolated`.
- The ITMC job's old ID `c125cd06-97d9-4685-9d41-4891c2fd6916` was stuck in
  `status: running` with a stale in-memory reservation. `openclaw cron rm` reported
  `activeRunCancellationRequested: true`, and the job was recreated under a new ID
  (`4abcd3c1-b9e6-4b3d-af45-efe1421e018d`) so it starts clean.
- Verified each converted job with `openclaw cron run <id> --wait` — all returned
  `status: ok`, `exitCode: 0`, and produced their real artifacts (DB backup file,
  Obsidian signals file, letter tracker output).
