# LEARNINGS.md

## 2026-10-04

### Write tool corrupts `os.getenv('DB_PASSWORD')` — use `DB_PW` instead

**What:** The `write` tool consistently replaces `os.getenv('DB_PASSWORD')` with `***` (SecretRef mask syntax) in Python files, producing invalid syntax every time. The corruption also sometimes injects the wrong content (command text instead of code).

**Workaround that works:** 
1. Use env var name `DB_PW` instead of `DB_PASSWORD` — doesn't trigger the mask
2. For complex Python files: write a `.ps1` script using `Out-File -Encoding utf8` with a here-string `@'...'@` containing the Python code, then run the PS1 to write the Python file

**Best approach for future IBD loaders:**
- Write Python loader to `.ps1` via `Out-File` with here-string
- Use `DB_PW` env var (not `DB_PASSWORD`)
- User runs: `$env:DB_PW = '<password>'; python <script.py>`

### Consolidated IBD loader

**Script:** `_load_ibd_paths.py` — takes IBD-50 CSV path, group CSV path, and issue date as 3 args:
```
python _load_ibd_paths.py <ibd50_csv> <ibd_grp_csv> <issue_date>
```
This is the right approach — generic, reusable for any date.

**For dates auto-detected from filename patterns:** use `_load_ibd.py` which takes just the date.

### OpenClaw exec still broken

**What:** `tools.exec.safeBins: ["python", "pwsh"]` and `mode: "auto"` are correctly set in `openclaw.json` and confirmed by `openclaw config get`, but session context shows "Approved executables: none" — all exec calls fail with `SYSTEM_RUN_DENIED`. Gateway restart does not fix it.

**Impact:** All scripts had to be run manually by user in PowerShell.

**Root cause:** Unknown — schema-level config correct but session-level enforcement not picking it up.

### IBD Loading Pipeline (done)

- **Jul 13:** CSV → DB (`ibd_50_group` 142 rows, `ibd_50_new` 50 rows) + Obsidian file written ✓
- **Jul 06:** CSV → DB + Obsidian file already existed ✓  
- **Aug 03, Sep 28, Oct 05:** Obsidian files exist; DB not loaded (user declined)

### Key files

- `_load_ibd_paths.py` — generic loader taking file paths + date (DB_PW env var)
- `_load_ibd.py` — date-only loader with auto file detection (DB_PASSWORD env var)
- `_jul13_groups.ps1` — PS1 that worked for writing scripts (Out-File approach)

## 2026-10-23

### Never append JSON with PowerShell `Out-File -Append` — use Python json

**What:** Appending a JSON object block to `memory/heartbeat-state.json` via
`@'...'@ | Out-File -Append -Encoding utf8` produced `}{` in the middle of the file,
making it invalid JSON (`Extra data` error). The file was then rewritten by a
Python repair script (parse head + new key, re-dump with `json.dumps(indent=2)`).

**How to apply:** For JSON state files, always read + `json.load` + mutate + `json.dump`
in a single Python step. Never text-append JSON.
Also note: PowerShell `Out-File -Encoding utf8` mangles non-ASCII (em dash, arrows)
when read back — prefer `write` tool for markdown files containing unicode.

## 2026-11-01

### `openclaw cron add` with multiple channels configured: use `--no-deliver`, not `--announce`

**What:** `openclaw cron add --cron "15 17 * * 1-5" ... --announce` fails with
`cron announce delivery requires an explicit channel when multiple channels are configured (discord, telegram)`.
`--announce` and `--no-deliver` are mutually exclusive — passing both errors with
`Choose at most one of --announce, --no-deliver, or --webhook`.

**How to apply:** For a silent background job (no Telegram/Discord push), use
`--session isolated --no-deliver`. Only use `--announce` together with an explicit
`--channel <id>` and `--to <dest>`.

### PowerShell + Python quoting: don't pass SQL through `python -c` inline

**What:** `python -c "... select count(*) from stock_technical ..."` through PowerShell
broke on both the `*` and the nested quotes (`SyntaxError: unterminated string literal`).

**How to apply:** For any multi-line/SQL Python work, write a temp `.py` file with the
`write` tool and run it, then delete it. Also: `openclaw gateway call cron.list` output
starts with a `Gateway call: cron.list` line, so `json.load` fails — strip the first
line before parsing, and note `Out-File -Encoding utf8` adds a BOM (read with `utf-8-sig`).

### `stock_technical` / `stock_price` had no writer script — data went ~1 month stale

**What:** Both tables had lost their writer (`update_stock_data.py` was gone from the
workspace), so `stock_technical` froze at 2026-09-29 and `stock_price` at 2026-03-06.
Nothing alerted; the heartbeat just reported stale data.

**How to apply:** When a table is read by heartbeat/watch scripts, confirm a *writer*
exists, not just readers. Fix pattern used: new `backfill_stock_technical.py`
(Yahoo Finance → `stock_technical` + `stock_price` upsert on `(ticker, date)`,
2y history so `sma_200` is populated, NaN-safe, `recommendation` ≤ 20 chars /
`signals` ≤ 200 chars) plus a new cron `Stock Technical Backfill`
(`15 17 * * 1-5` America/New_York, session isolated, `--no-deliver`).

### Schaeffer's ITMC: subscription_release.status='extracted' does not mean extracted

**What:** 5 ITMC release rows (2026-09-06, 07-05, 06-07, 05-03, 03-08) were marked
extracted with **zero** rows in subscription_letter. The status flag was seeded,
not earned. Real schema quirk: subscription_release uses subscription_release_id
(not elease_id), and subscription uses subscription_name (not 
ame).

**How to apply:** Never trust the release status flag alone. The only reliable check
is a JOIN: subscription_release LEFT JOIN subscription_letter on elease_id
and count rows. Any release with 0 letters but status extracted is a backfill
candidate. Conversely, a release with 0 letters may be a *future* scheduled release
(2026-11-08, 2026-12-06) or pre-subscription backfill (2026-01-04, 2026-02-08) —
those are normal, keep them pending, don't treat as errors.

### Schaeffer's message center only exposes ~11 recent messages

**What:** The message center lists 11 messages and stops at 2026-03-08. The
Load More Messages button does NOT fetch older rows (clicking it re-renders the
same 11). Letters older than that are unrecoverable from the site.

**How to apply:** For any backfill, work from the newest visible message downward and
stop when you hit the oldest visible date. Save the table image to disk
(itmc_<date>/img1.*) so a future backfill has a local source.

### Schaeffer's ITMC table image = the FIRST bulletin_images, not the widest

**What:** The runbook says "the image from cdn.schaeffersresearch.com/bulletin_images/
with the largest width (~1430px)". That is wrong for most letters — the widest images
are the per-trade charts (up to 2765px). The recommendation **table** is the *first*
bulletin_images URL in document order, and it is always a .jpg or .png of roughly
800-1024 x 320-400 natural size.

**How to apply:** Take document.images filtered to ulletin_images in DOM order
and use index 0 as the table. Confirm by the natural dimensions (width ~800-1030,
height ~300-400) before running OCR. Always do two independent iew_image passes
and require exact agreement.

### Finviz GapperMid returns near-zero rows pre-market - it is not a parser bug

**What:** The Finviz GapperMid screener URL
(`screener.ashx?v=111&f=cap_midover,sh_curvol_o750,sh_price_o1,sh_relvol_o3&o=-change`)
returns HTTP 200 with a valid embedded-JSON payload, but the row count depends on
the session clock:
- 08:00 ET -> 1-4 rows (screener not yet populated)
- 09:09 ET -> 4 rows
- `cap_midover` alone -> 2026 results / 20 rows per page
- adding `sh_relvol_o3` -> 7 rows
- adding `sh_curvol_o750` -> 4 rows

**How to apply:** Do not diagnose "HTTP 200 + 0 rows" as a Finviz layout change
without re-running the scrape at a later hour first. Run `python scrape_finviz.py`
and compare the row count to the filter probe before touching the parser. The
`extract_screener_json` embedded-JSON approach is still valid.

### `scrape_finviz.py` guards against EMPTY results but not SMALLER results

**What:** The 2026-11-01 fix makes the script exit 1 without writing when the row
list is empty. But a partial result (e.g. 4 rows) still overwrites the committed
`finviz_extracted_data.json` (20 rows), shrinking the working snapshot.

**How to apply:** After any manual `scrape_finviz.py` run, check the row count
before keeping it:
`python -c "import json;print(len(json.load(open('finviz_extracted_data.json'))))"`.
If it dropped, restore with `git checkout -- finviz_extracted_data.json`.
Better: make the script only write when `len(rows) >= previous file's row count`.

### Finviz same-day dedup locks in partial scans

**What:** `update_stock_data_check.py` -> `check_already_loaded()` and the loader
both skip if ANY `finviz_screener_scan_result` row exists for today. An 08:02 ET
1-row scan therefore blocks every later same-day fuller scan.

**How to apply:** To refresh a partial day, use `force_load_finviz_data.py`
(bypasses the dedup guard and inserts a new scan). Consider treating a
same-day count below ~20 as incomplete rather than "already done".

### MEMORY.md can drift from the actual backup scripts

**What:** MEMORY.md's "fintech DB - Backup System" section names
`backup_fintech.py` / `check_backup.py` under `Obsidian_trading\database\` - neither
file exists. The real scripts are `db_backup.py` (workspace root) and the
`fintech-db-backup` / `fintech-db-backup-monitor` crons. MEMORY.md also says
"Retention: Last 4 weekly backups" while `db_backup.py` keeps the last **8**.

**How to apply:** Before trusting MEMORY.md for a script path, verify the file
exists (`Get-ChildItem -Recurse -Include <name>`). Fix the docs when the drift is
found.

### Yahoo v8 chart: meta.previousClose is NOT the prior session close

**What:** `https://query2.finance.yahoo.com/v8/finance/chart/{sym}?range=5d&interval=1d`
returns `meta.previousClose` / `meta.chartPreviousClose` that sometimes refer to a much
older bar. On 2026-11-04 this made MU read -15.18% and GOOG -9.17% when the real moves
were -2.27% and +5.25%.

**How to apply:** compute the prior close from the daily close series itself
(`closes[-2]`), and print the last 4 dated closes alongside the % so the reference
bar is visible. Cross-check against CNBC's `previous_day_closing` (quote.cnbc.com
restQuote) before reporting any move. `hb_quotes.py` already uses closes[-2] and is
correct; `meta.previousClose` is not.

### stooq.com CSV endpoints are gone (404)

**What:** `stooq.com/q/l/?s=aapl.us&f=sd2t2ohlcv&h&e=csv` and `/q/d/l/?s=aapl.us&i=d`
now 404 (the /q/d/l path returns an HTML challenge page, not CSV).

**How to apply:** don't use stooq as a quote cross-check. Use CNBC
`quote.cnbc.com/quote-html-webservice/restQuote/...` (primary, gives
`last` + `previous_day_closing` + session status) and Yahoo chart v8 (secondary).

### Yahoo chart: includePrePost=true corrupts the daily close series

**What:** `?range=5d&interval=1d&includePrePost=true` injects extended-hours bars into
the daily series, so `closes[-2]` is no longer the prior session close. On 2026-11-04
this made SPY read -0.67% (true +1.80%), MU -15.18% (true -2.27%), GOOG -9.17% (true
+5.25%). Without `includePrePost`, `meta.previousClose` matched `closes[-2]` exactly for
NVDA/MU/AMD/AVGO.

**How to apply:** use `range=1d&interval=5m&includePrePost=true` only for live
extended-hours prints (read `meta.regularMarketPrice`), and use plain
`range=5d&interval=1d` (no includePrePost) for the prior close and % change. Always
cross-check against CNBC `previous_day_closing` before reporting a move.
