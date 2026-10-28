# MEMORY.md - Long-term Memory

## CRITICAL: PostgreSQL Only — Never SQLite

All application data lives in `fintech` PostgreSQL at `127.0.0.1:5432`. SQLite is never used.
- User: `postgres`, password via `DB_PASSWORD` env var
- Always: `import psycopg2` — never `import sqlite3`
- If any script or job uses `sqlite3` or creates `.db` files → wrong, fix immediately
- Key tables: `stock_technical`, `discord_trade_signal`, `stock_price`, `stock_watchlist`, `ibd_50_summary`, `jarsy_asset`, `finviz_screener`, `discord_channel`, `discord_message`

---

## CRON JOBS — CRITICAL REMINDER (updated 2026-10-27)

### Disabling system-owned monitor jobs (RESOLVED 2026-10-27)

The weekly **"Skill collection review (main)"** job (id `47710e37-0c9b-4349-92e3-71107174cd20`, declarationKey `skill-collection-review:main`) is a **system-owned monitor job**. These CANNOT be edited or removed via CLI or API — all of these fail with `system-owned monitor jobs cannot be edited by cron clients`:
- `automations(action="update", ...)` 
- `openclaw cron disable <id>`
- `openclaw cron rm <id>`
- `openclaw gateway call cron.update` (needs `jobId` + `patch` schema, but still rejected for system-owned jobs)

**Correct way to disable it:** set config `skills.workshop.autonomous.mode` = `off`
```
skills: { workshop: { autonomous: { mode: "off" } } }
```
The Gateway converges the system-owned job to `enabled: false` on config reload (no restart needed). Modes: `auto` (enabled), `propose`, `off` (both keep it disabled).

**Verification:** `automations(action="get", jobId=...)` → `"enabled": false`.

**CONFIRMED DISABLED 2026-10-27 15:18 EDT.** `skill-collection-review-main` now reports `enabled: false`, `nextRunAt: null`. The hourly watchdog reads `openclaw gateway call cron.list`, and that output now returns **14 jobs instead of 15** — the job is no longer listed at all, so the repeated "🔴 Cron Job Failed: skill-collection-review-main" Telegram alerts (hourly, 2026-10-26 23:03 → 2026-10-27 15:03) have stopped at the source.

**Why it failed originally (root cause, not a code bug):** two runs on Oct 24 in the same weekly review job — run 1 (11:51) timed out after 27 min burning ~4.1M tokens, run 2 (12:19) "Agent couldn't generate a response" after 14 min / ~1.25M tokens. The review prompt is enormous (it reads the full session corpus), so it exhausts the context/timeout budget. `consecutiveErrors` then stayed at 2 and the hourly watchdog re-alerted every hour with a stale error.

Source: `docs/automation/cron-jobs/payloads.md` — "Skill collection review runs every 7 days. It is enabled when `skills.workshop.autonomous.mode` is `auto`; `propose` and `off` keep the system-owned job disabled."

### Automations storage (CORRECTED 2026-10-27)

Live automations DB is `C:\Users\shaowei_l\.openclaw\state\openclaw.sqlite` (NOT the npm path — that one was 0 bytes). Tables: `cron_jobs`, `cron_run_receipts`, `cron_job_scratch`. The `store_key` column points at a `jobs.json` path that may not exist; SQLite is the real store.

`openclaw gateway call cron.list` works for listing (the watchdog uses it). `cron.update` requires `{"jobId": ..., "patch": {...}}` — NOT `{id, enabled}`.

### Watchdog cron job (HARDENED v2, 2026-10-27)

`Cron Job Watchdog` (id `7449b395-fb91-49d0-b4a6-11b49b13330f`) — hourly (`0 * * * *`, stagger 300s), isolated session, `delivery.mode: none`.

**v1 problem:** it re-read `cron.list` every hour and alerted on any job with `lastRunStatus == "error"` + `consecutiveErrors > 0`, with no dedup and no disabled-job filter. A job that failed once and was then disabled kept alerting on stale state forever (the `skill-collection-review-main` case: 16 hourly alerts).

**v2 logic:**
- Reads `openclaw cron list --all --json` (fallback `openclaw gateway call cron.list`)
- Dedup state in `memory/watchdog-state.json` — a job alerts only if its `lastRunAtMs` is GREATER than the previously recorded value; an unchanged `lastRunAtMs` = stale repeat = skip
- Skips disabled jobs, `lastRunStatus` ok/null, and jobs with no state
- Sends its OWN single Telegram message via the `message` tool (telegram → 7923250382); `delivery.mode` was flipped to `none` to avoid double-sending with the old `announce` delivery
- Rewrites the state file each run, preserving still-failing entries and pruning healthy/disabled ones

**Validated:** forced run 2026-10-27 21:41 ET → summary "Watchdog: nothing new", `delivered: false`, state file correctly reduced to `{"alerts": {}}` after purging the disabled job.

## CRON JOBS — REMINDER (2026-10-15)

**All cron job automations are stored in `openclaw.sqlite`** at:
`C:\Users\shaowei_l\AppData\Roaming\npm\node_modules\openclaw\openclaw.sqlite`

**This database was wiped at 11:27 PM on 2026-10-15** (gateway restart caused it to be reset to 0 bytes). ALL cron jobs were lost.

**Before any gateway restart, export the automations:**
1. Run `automations(action="list", includeDisabled=true)` to get all job configs
2. Save the output to `memory/automations-backup-YYYY-MM-DD.json`
3. Commit to GitHub

**Watchdog cron job** — was monitoring all cron jobs and alerting on failures. Was lost in the 2026-10-15 wipe. Must be recreated.

**TODO (deferred, user has no time now):**
1. Fix heartbeat session - it gives false "0 signals" reports when pipeline actually finds signals. The `sessions_spawn` subprocess output may not be captured correctly. Consider either: (a) approving exec for heartbeat session, or (b) removing pipeline work from heartbeat entirely and relying on cron only
2. Recreate all lost cron jobs from memory of what they were
3. Fix `generate_daily_signals.py` to use `--date` parameter (was partially done but not fully tested)
4. Investigate why openclaw.sqlite gets wiped on gateway restart - is there a migration or init that resets it?

### Daily signals file gaps (audited 2026-10-27)

Cross-checked `discord_trade_signal.signal_date` against `C:\Data\Obsidian_root\Obsidian_trading\Ashley_trading\*Daily-Signals.md`.
**Genuinely missing files were 2026-09-29 (4 signals) and 2026-10-02 (1 signal)** - both regenerated with `python Discord\myTrading\generate_daily_signals.py --date YYYY-MM-DD`. Verified written.

**2026-10-16 and 2026-10-21 have no file because there were no signals**: Oct 16 = 0 `discord_message` rows that day; Oct 21 = 1 message, 0 signals. Correct behaviour, not a bug.

### Letter position tracker - "12 of 18 show Entry: n/a" (RESOLVED 2026-10-27)

Heartbeat reported this as a quote-fetch failure. **It is not.** Two separate things:
1. The `Entry:�` was a **console encoding artifact** - the script printed an em-dash and the Windows console is cp1252. Fixed by printing `n/a` instead of `—`.
2. The 12 positions genuinely have `entry_price IS NULL` because **those letters were extracted AFTER their options had already expired**: letter 2 (letter_date 2026-08-09, exp 2026-08-14) was extracted 2026-08-29; letter 3 (letter_date 2026-10-04, exp 2026-10-09) was extracted 2026-10-25. The ITMC runbook step 7 ("Handle already-expired letters") deliberately marks these `expired` with `exit_price=0`, `exit_date=expiration`, `pnl_pct` NULL. See `docs/itmc_extraction_runbook.md`.

**Do not "fix" this by backfilling entry_price** - there was no fill to record.

**yfinance option quoting DOES work** (`yf_opt` returned 147.025 for AAPL 200C, and correctly returns None for expired options and bogus strikes). A symbol built with a wrong expiry format returns bid=0/ask=0 and an empty history - that is the real failure mode to look for.

**Also fixed:** `alpaca_opt` was returning `(avg_entry_price + current_price) / 2` - the average of your cost basis and the current price, which is not a market price. Now returns `current_price` only. And the tracker now imports `DB_CONFIG` from `Discord/myTrading/_db_pw.py` instead of hardcoding the password.

### DeepSeek provider retirement - PERMANENT FIX (2026-10-27)

The recurring "deepseek retired" gateway error came from `models.providers.deepseek` still being configured while the `deepseek` plugin was disabled. **Fix: removed the `deepseek` provider block from `models.providers` in `C:\Users\shaowei_l\.openclaw\openclaw.json`** (backup at `openclaw.json.bak-2026-10-27`). `plugins.entries.deepseek.enabled` stays `false`. Verified via `openclaw gateway call models.list` - only the three MiniMax models remain. Default model is `minimax-portal/MiniMax-M2.7`; there were never any fallbacks referencing DeepSeek.

### Session archive command (confirmed)

```
openclaw sessions archive "<session-key>" [--dry-run] [--json]
```
Keys look like `agent:main:cron:<job-id>` / `agent:main:main`. Archiving keeps the session searchable but out of the active list. Verified by archiving the stale `agent:main:cron:47710e37-...` session for the disabled skill-review job.

### Python 3.14 docstring escape sequences (fixed 2026-10-27)

`"\E"` in a docstring is a SyntaxError on Python 3.14. Use `r"""..."""` for docstrings containing Windows paths like `HKCU:\Environment`. Fixed in `_run_discord_fetch.py` and `Discord/myTrading/_db_pw.py`. Also `backup_critical_files.py` was prose saved with a `.py` extension (never a valid module) - renamed to `backup_critical_files.md`.

## Schaeffer's Investment Research Subscriptions

### Database (fintech PostgreSQL)
- Tables: `subscription`, `subscription_release`
- Script: `save_subscriptions.py`
- 24 release dates stored for 2026

### Subscriptions
1. **Option Advisor (OA)** - 4th Friday of each month
2. **In The Money Countdown (ITMC)** - Sunday before 2nd Friday

### Schaeffer's Login (Windows env vars)
- Email: `SCHAEFERS_EMAIL` = shaowei_l@hotmail.com
- Password: `SCHAEFERS_PASSWORD` = schPineapple0!
- Website: https://myaccount.schaeffersresearch.com/
- Scripts: `extract_schaeffers_letter.py` (manual), `letter_position_tracker.py` (daily EOD tracker)
- Tables: `subscription_letter`, `subscription_letter_position` (both in fintech DB)
- Crons: Letter Tracker (Mon-Fri 4:30 PM ET), ITMC Extraction (Sun 8 PM ET)
- Docs: `docs/schaeffers_letter_tracking.md`
- Note: Browser + image analysis to extract letter data (table is rendered as images on site)
- Current ITMC (Apr 5, exp Fri Apr 10): AKAM 111c, B 45p, CRCL 84c, FLY 37p, NTR 72c, TWLO 125c. Tracking in DB via `letter_position_tracker.py`.
- Target: +150% profit on each. None hit yet as of Apr 8 EOD.

---

## IBD 50 Extraction (updated 2026-09-28)

### Background
- Extracting IBD 50 stock lists from eIBD PDF magazines
- Pure Python/PyMuPDF (no OpenAI API needed) — uses block layout analysis
- Current working script: `extract_ibd50.py` (v26 as of Aug 31)

### Key Scripts
- `extract_ibd50.py` — Main extraction script (v26)
  - Input: PDF at `C:\DolphinShare\IBD\2026\Raw\`
  - Output: CSV at `C:\DolphinShare\IBD\2026\Processed\`
  - Algorithm: LEFT table parsing (new in v26) + tile-proximity fallback
  - Extracts: rank, symbol, company, price, short_note, description
  - Pages: B1 (ranks 1-15), B3 (ranks 16-30), B4 (ranks 31-50)

### v26 Algorithm — LEFT Table Parsing
- Each B-page has TWO regions: LEFT table (x < 300) and RIGHT tiles (x >= 300)
- LEFT table: complete data per row — rank marker + company name + price + metrics + description
- RIGHT tiles: symbol-only headers + short notes in separate tile grid
- Parsing steps:
  1. Extract rank marker y-positions from word-level data (x < 50, ranks 1-50)
  2. For each LEFT block (x < 300, y > 310), assign to nearest unused rank by y-proximity
  3. Parse company/price/description from block's newline-separated lines
  4. Match symbols via index-based lookup: row index i -> column = i % 3, tile position = i // 3
  5. Fall back to old tile-matching if LEFT parsing yields < expected count

### Extraction Results (v26, Aug 31, 2026 run)
- Three files processed: eIBD_081026, eIBD_081726, eIBD_082426
- B1 (ranks 1-15): 15/15 perfect across all 3 files ✓
- B3/B4: 5 missing symbols patched manually (ZETA, LLY, BURL, TSM, INSW)
- 50/50 company descriptions, 50/50 prices (no $ sign)
- CSVs saved to `C:\DolphinShare\IBD\2026\Processed\`
- **Latest extraction: 2026-09-28** — v9 completed for Aug 10/17 files, all 50 symbols verified ✓
- **2026-10-04:** Loaded Jul 13 + Jul 06 (modified b CSVs) → DB (`ibd_50_group`, `ibd_50_new`, `ibd_company`) + Obsidian files. User ran scripts manually (exec broken). Aug 03/Sep 28/Oct 05: Obsidian files existed, DB not loaded.

### Key Algorithm Details (v26)
- Rank marker y-positions: ranks 1-50 at ~27px intervals starting at y~326
- LEFT row assignment: closest-y-rank matching, 40px max distance, one rank per row
- Symbol matching: index-based (col = i % 3, tile_pos = i // 3) — avoids nearest-y heuristics
- `bx < 300` cross-column guard → skips chart labels leaking between columns
- Price extraction: first line with numeric content, prefers $ prefix
- Description: last non-metric line (filters numbers, dots, +/- percentages)

### PDF Page Structure (typical)
- B1: ranks 1-15, B3: ranks 16-30, B4: ranks 31-50
- `skip_pages=14` for finding B1 (was 15 in earlier versions)
- Rank marker x threshold: `x0 < 250` (B4 markers at x=307 needed this adjustment)

### Database: ibd_50 table
- Columns: issue_date, rank, symbol, company, price, industry
- 71 weeks of data (2024-09-02 to 2025-12-22)
- Some weeks have incomplete data (less than 50 stocks)

### Tracking File
- Location: `D:\openclaw_data\app_process\ibd_extraction.json`
- Status: pending -> rendered -> completed/failed

### GitHub
- Repo: **shaoweil9921/myFin** (https://github.com/shaoweil9921/myFin)
- IBD scripts: `ibd/` subfolder
- Files: `extract_ibd50.py` (v9, latest from 2026-09-28), `build_symbol_list.py`, `ibd_symbol_list.csv` (72 unique symbols)
- Workspace git repo: `C:\Users\shaowei_l\.openclaw\workspace\.git` (remote → myFin)

---

### IBD Industry Group Rankings (IGR) — 2026-09-27
- **Table:** `fintech.ibd_industry_group_rankings`
- **Script:** `ibd/extract_groups.py` (two-pass PyMuPDF extraction)
- **CSV:** `ibd/igr_aug03.csv` (142 entries from eIBD_080326.pdf)
- **Columns:** id, issue_date, rank, prev_group_rank, group_name, composite_rating, ytd_pct, wk3_pct
- **Coverage:** Ranks 1-142 (of 197 total groups) — Aug 3, 2026 issue
  - 138 entries with full data (rating + ytd + wk3)
  - 4 entries missing rating (ranks 114, 116, 123, 124) — PDF rendering artifacts
  - Ranks 143-197 not present in this issue's PDF
- **Extraction approach:** Pass 1 = block-level regex on full page text; Pass 2 = secondary regex for entries missing rating
- **GitHub:** Committed to myFin repo (`ibd/extract_groups.py`, `ibd/igr_aug03.csv`)

## fintech DB — Full Table List
- `discord_message` — raw Discord messages
- `discord_trade_signal` — parsed trading signals
- `discord_channel` — tracked channels (id, discord_id, name, category)
- `discord_account` — bot accounts
- `finviz_screener` — screener definitions
- `finviz_screener_scan_result` — screener stock results
- `finviz_screener_scan_result_summary` — scan summary stats
- `scan` — extraction scan metadata
- `jarsy_asset` / `jarsy_asset_live` — Jarsy token data
- `subscription_letter` — Schaeffers letter records
- `subscription_letter_position` — letter option positions
- `market_holidays` — holiday calendar
- `stock_technical` / `stock_technical_intraday` — OHLCV + indicators
- `stock_watchlist` — watched tickers
- `ibd_50_summary` / `ibd_50_new` — IBD 50 data
- `ibd_industry_group_rankings` — IGR data

## fintech DB — Backup System
- **Backup dir:** `C:\Data\postgres_backup\`
- **Schedule:** Saturday 1:00 PM ET (backup), Monday 9:00 AM ET (monitor)
- **Retention:** Last 4 weekly backups (auto-cleanup)
- **Alert:** Telegram message if no backup for current week
- **Scripts:** `backup_fintech.py`, `check_backup.py` (in `Obsidian_trading\database\`)
- **Restore:** `gunzip -c fintech_YYYY-MM-DD.sql.gz | psql -h 127.0.0.1 -p 5432 -U postgres -d fintech`
- **pg_dump path:** `C:\Program Files\PostgreSQL\18\bin\pg_dump.exe`

---

## Stock Data

### Database Tables
- `stock_technical` - Daily OHLCV + indicators (SMA, RSI, MACD, Bollinger)
- `stock_technical_intraday` - Hourly data
- `stock_watchlist` - Watched tickers

### fintech DB Credentials
- Host: 127.0.0.1, Port: 5432
- User: postgres, Password: asdfghjk1234%
- Database: fintech

### Stock Watchlist (as of 2026-03-23)
| Ticker | Added | Ticker | Added |
|---|---|---|---|
| SPY | 2026-03-08 | PLTR | 2026-03-11 |
| AAPL | 2026-03-09 | ORCL | 2026-03-12 |
| NVDA | 2026-03-09 | AMZN | 2026-03-12 |
| TSLA | 2026-03-09 | MSFT | 2026-03-12 |
| ^VIX | 2026-03-09 | GOOG | 2026-03-12 |
| MU | 2026-03-23 | | |

### Cron Jobs
- Stock Data Update: Mon-Fri 10AM-5PM hourly

### Scripts
- `stock_app.py` - Streamlit stock chart app
- `update_stock_data.py` - Incremental data fetcher

---

## Stock Chart: SPX + VIX + Volume Drawdown Chart (2026-03-23)

### What
- 3-panel chart: SPX price+drawdown / VIX panel / Volume
- Identifies drawdown events (>6% entry, -3% recovery threshold)
- Marks peak VIX (highest fear) in each event window + standalone VIX>30 spikes
- Dark background, professional financial chart style

### Key Script
- `spx_vix_volume_chart.py` — single-file, documented
- Output: `Downloads\spx_vix_volume_chart.png`
- Parameters: LOOKBACK_YRS, DD_ENTRY, DD_RECOVER, VIX_SPIKE at top of script

### Key Parameters
- DD_ENTRY = -6.0% (triggers drawdown event)
- DD_RECOVER = -3.0% (closes event — softer threshold prevents merging)
- VIX_SPIKE = 30 (annotate on chart when above this)
- MIN_SEP_DAYS = 5 (prevents double-counting closely-spaced troughs)

### Drawdown Window Fix (Important)
- Original bug: DD_RECOVER = -1% was too strict — events merged across months
- Fix: -3% recovery threshold properly closes each event
- For VIX: use `idxmax()` (peak = highest VIX = peak fear), NOT lowest

### Documentation
- Full methodology: `docs/spx_vix_volume_chart.md`

### Performance
- 2 yfinance API calls per ticker (no key needed)
- Safe for ~20 concurrent; add 0.3s delay for 20-50 stocks
- For 50+: batch with delays or use Finnhub/Polygon.io

### User Prompt Cheatsheet
- Location: `docs/user_prompt_cheatsheet.md`
- Quick-copy prompts for all common tasks: charts, IBD 50, stock research, reminders, scripts, system commands

---

## Trading Learning Path (Started 2026-03-25)

### Goal
Become a solid options trader. Learn the market from scratch — systematic, methodical approach.

### Core Curriculum
1. **Market Fundamentals** — how markets work, order types, exchanges, participants, price discovery
2. **Technical Analysis** — price action, chart patterns, indicators (SMA, RSI, MACD, Bollinger)
3. **Options Mechanics** — Greeks (Delta/Gamma/Theta/Vega), pricing, term structure, skew
4. **Options Strategies** — vertical spreads, iron condors, straddles, strangles, the profiles
5. **Risk Management** — Kelly criterion, position sizing, max loss thinking
6. **Volatility** — IV rank, term structure, VIX, realized vs implied
7. **Fundamental Analysis** — reading financials, sector rotation, macro context
8. **Trading Psychology** — journaling, discipline, handling drawdowns

### Learning Method
- Learn by doing — start with paper trades, real market data
- After each trade: document the thesis, outcome, lessons learned -> .learnings/
- Study in parallel: read/summarize one concept per day
- Build a trading journal in memory/YYYY-MM-DD.md

### Resources Available
- Alpaca paper trading ($200K buying power, Level 3 options)
- options-spread-conviction-engine (Kelly sizing, regime detection)
- options-strategy-advisor (Black-Scholes, P/L simulation)
- option-calculator (Greeks, P&L diagrams)
- QuantDinger (backtesting, strategy development)

---

## Schaeffer's Letter Tracking (2026-04-08)

### New Tables (fintech DB)
- `subscription_letter` — stores each recommendation letter (letter_date, tickers[], raw_text, source_url, status)
- `subscription_letter_position` — tracks each option trade until expiry (ticker, strike, expiration, entry_price, current_price, pnl_pct, status)

### Scripts
- `extract_schaeffers_letter.py` — manual ticker injection + DB save
- `letter_position_tracker.py` — daily EOD tracker: fills entries, updates P&L, checks target/expiry
- Docs: `docs/schaeffers_letter_tracking.md`

### ITMC Apr 5 Positions (exp Fri Apr 10)
All 6 expired Apr 10. None hit +150% target. yf prices unreliable — real fills may differ.
| Ticker | Type | Strike | Entry | Final (yf est) | P&L |
|--------|------|--------|-------|-----------------|-----|
| AKAM | CALL | $111 | $8.00 | ~$0.65 | -92% |
| B | PUT | $45 | $4.95 | ~$2.60 | -47% |
| CRCL | CALL | $84 | $8.00 | ~$2.34 | -71% |
| FLY | PUT | $37 | $5.00 | ~$0.75 | -85% |
| NTR | CALL | $72 | $4.60 | ~$1.16 | -75% |
| TWLO | CALL | $125 | $7.50 | ~$1.42 | -81% |
- Note: yfinance option prices unreliable/delayed. Real market prices may differ significantly.
- Tracker will mark all expired Fri Apr 10 EOD. None hit +150% target.

### Crons
- Letter Tracker: Mon-Fri 4:30 PM ET
- ITMC Extraction: Sun 8 PM ET (browser + image analysis)

## Follow Up / Pending

## PDF Form Filler (2026-08-22)

### Script: `pdf_make_fillable.py`
- Location: `workspace\pdf_make_fillable.py`
- Converts a PDF with blank-line fields into a fillable AcroForm PDF using PyMuPDF
- Detects: underscore text fields + checkbox patterns
- Creates proper interactive PDF form fields (light yellow fill for text, white for checkboxes)

### Usage
```bash
python pdf_make_fillable.py <input.pdf> <output.pdf>
```

### Tested on
- FL-7pages_nologo.pdf → FL-7pages_fillable.pdf (110 fields across 7 pages)

### Output
- `C:\DolphinShare\FL-7pages_fillable.pdf` (110 form fields: text inputs + checkboxes)
- All fields are interactive — open in any PDF reader (Adobe, browser, etc.)

## PDF Logo Removal Tool (2026-08-22)

### Script: `pdf_remove_logos.py`
- Location: `workspace\pdf_remove_logos.py`
- Uses PyMuPDF (fitz) redaction to permanently remove image bytes from PDFs
- Works on any PDF; targets pages with actual images

### Usage
```bash
# Analyze: see what images exist on which pages
python pdf_remove_logos.py <input.pdf> --analyze

# Remove logos from page 1 only (default)
python pdf_remove_logos.py <input.pdf> <output.pdf>

# Remove from specific pages
python pdf_remove_logos.py <input.pdf> <output.pdf> --pages 1,2,3
```

### Tested on
- FL-2pages.pdf (2 logos on page 1) → 0 images remaining, clean white redaction
- FL-7pages.pdf (2 logos on page 1 only, pages 2-7 no images) → confirmed

### How it works
- Uses `page.add_redact_annot()` + `page.apply_redactions()` to permanently strip image data
- NOT just visual covering — bytes are actually removed (garbage collection + deflate)
- White fill over redacted areas

## Condo Sale — 450 NW 20th ST, Unit 212, Boca Raton FL (2026-07-30, STALLED)
- Sellers: Shaowei Luo + Fen Chen (owned since Jan 3, 2005, no mortgage)
- Buyers: Alex Ramirez + Nathalie Vilvandre Ramirez
- Sale price: $230K | Loan policy: $119,600
- Outstanding: HOA approval from Casa Del Rio, Notice of Commencement clearance
- Title company: The Closing Team, (954) 289-1466
- Status ⚠️: HOA approval pending since Jul 30 (~7 weeks, no update). Possibly stalled or fell through. Needs user follow-up.

## Obsidian Vaults (2026-04-12)
- GitHub repos:
  - shaoweil9921/obsidian_trading (renamed from myobsidian_private_root)
  - shaoweil9921/obsidian_life (new, private)
- Local:
  - C:\Data\Obsidian_root\Obsidian_trading\ — Vault 1, trading notes
  - C:\Data\Obsidian_root\Obsidian_life\ — Vault 2, personal notes
- Token: <GITHUB_PAT> (in Windows env vars)
- Each vault has its own .git folder, pushes to own GitHub repo

### Discord Trading Bot — Pipeline (2026-09-20)

### Location
`C:\Users\shaowei_l\.openclaw\workspace\Discord\myTrading\`

### Scripts
- `01_schema_setup.py` — DB schema
- `02_parse_signals.py` — parse signals from Discord messages, insert to DB
- `03_fetch_messages.py` — fetch messages from Discord API

### Database: fintech @ 127.0.0.1:5432, user=postgres

### Bugs Fixed (2026-09-20)
- Cursor bug: was saving oldest msg ID as cursor; fixed to use first/newest ID
- author_posted_at all NULL: regex wasn't matching "TradingWithAshley — 9/15/2026" pattern
- OPTIONS strategy/strike/premium not parsed: parsing was in wrong if/else branch
- Duplicate SOFI signals: FK pointed to wrong table
- Column order bug in INSERT: VALUES had swapped account_id/channel_db_id
- account_id never set on messages: added through entire save_messages call chain
- Channel 2 name wrong: was "new-channel", should be "swl-challenge-trades"
- Channel 2 cursor never set: set to 1551058724251111567
- stock_ticker NULL for OPTIONS: only underlying_ticker was set, backfilled

### Bug Fixed (2026-10-10) — option_type not set from strategy line
**Problem:** Signals like "Wheel cash secured puts" and "Wheel covered calls" were skipped
because `option_type` was not being inferred from the strategy text.
**Root cause:** The regex patterns had trailing `\b` word boundaries:
- `\bcash.?secured.?put\b` — `\b` after `put` fails when text is "puts" (no word boundary after `puts`)
- `\bcovered.?call\b` — same issue with "calls"
**Fix:** Remove trailing `\b` from put/call patterns AND add `wheel.*put` / `wheel.*call` fallback:
```python
# Before (fails on "puts", "calls"):
r'\bcash.?secured.?put\b'
r'\bcovered.?call\b'

# After (matches both singular and plural):
r'\bcash.?secured.?put'   # no trailing \b
r'\bcovered.?call'         # no trailing \b
# Also add wheel strategy matching:
r'wheel.*put'
r'wheel.*call'
```

### generate_daily_signals.py — --date Parameter (2026-10-10)
- `--date YYYY-MM-DD` argument: generates signals file for a specific date
- Query uses `WHERE s.signal_date = %s` (not `created_at`)
- Early exit if no signals found for that date
```bash
python generate_daily_signals.py --date 2026-10-09  # backfill
python generate_daily_signals.py                    # today (default)
```
- Also added to `02_parse_signals.py` — `--date` mode fetches messages where `DATE(created_at AT TIME ZONE 'America/New_York') = specified_date`

### Signals Dashboard — Obsidian DataviewJS (2026-10-11)
- Created `Ashley_trading/Signals-Dashboard.md` with DataviewJS:
  - Active Signals table (all signals from all daily files)
  - By Ticker view / By Coach view
  - Expiring Soon (< 7 days) view
  - Recent Files table
- Template: `templates/Signals-Dashboard-Template.md`
- Requires Obsidian Dataview plugin
- `dv.paragraph()` → use `dv.el("p", ...)` for compatibility

### Current Signals in DB (updated 2026-10-11)
| id | ticker | asset | strategy | strike | premium | notes |
|----|--------|-------|----------|--------|---------|-------|
| 2 | GGLL | STOCK | — | — | — | |
| 3 | SOFI | OPTION | Covered Call | 18.50 | — | |
| 35 | MU | OPTION | Covered Call | 1000 | 2.72 | |
| 36 | NBIS | OPTION | Covered Call | 235 | 1.4 | |
| Oct 9 | MP | OPTION | PUT | $42.5 | $0.55 | exp 2026-10-23, Coach Baylor |
| Oct 9 | TNA | OPTION | CALL | $68.0 | $0.60 | exp 2026-11-06, Coach Baylor |

### Channels
| db_id | discord_id | name | cursor |
|-------|-----------|------|--------|
| 1 | 1550893507118637096 | swl-small-trades | 1550894058820345906 |
| 2 | 1550930741309866065 | swl-challenge-trades | 1551058724251111567 |

### Refactor: removed underlying_ticker
- Dropped from DB and schema — `stock_ticker` used for both STOCK and OPTION signals

## Schwab OAuth Re-auth (2026-09-24, BLOCKED)
- ⚠️ DO NOT restart cloudflared or Python server without user's confirmation first
- User updates callback URL in Schwab portal before each auth attempt
- Refresh token revoked on 2026-09-23. Full OAuth flow needed.
- **BLOCKED**: App in "Modification Pending" state — Schwab hasn't approved the redirect URI change yet.
- cloudflared tunnel works: `cloudflared.exe tunnel --url http://localhost:9876`
- Python redirect server: `workspace/schwab_redirect_server.py` — update `REPLACE_WITH_CURRENT_CLOUDFLARED_URL` with actual URL each time
- Auth URL: `https://api.schwabapi.com/v1/oauth/authorize?client_id=ydIVYBppTj7v8z3KnOfZngGgXNfSWswlwK4HwhVmfC1GURGn&redirect_uri=<cloudflared_url>&response_type=code`
- Token file: `~/.schwab_tokens.json`
- Tailscale serve approach FAILED: daemon on Windows can't reach user-session 127.0.0.1 (network isolation issue)

## OpenClaw Bug: DataCloneError on Isolated Sessions
- **Issue:** https://github.com/openclaw/openclaw/issues/161272
- ALL `sessionTarget: "isolated"` cron jobs fail with `DataCloneError` ( serialization fails in V8 isolate)
- Also: `command` payload hardcodes `sh -lc` — doesn't exist on Windows → `spawn sh ENOENT`
- Gateway V2026.9.9. Workaround: disable → re-enable cycle clears errors temporarily
- Working jobs: `sessionTarget: "main"` (heartbeat, EOD Memory Save)

## OpenClaw Gateway — Event Loop Blocking Issue (2026-10-11)
- **Symptom:** Gateway took ~7 minutes to start (event loop blocked 401 seconds)
- **Root cause:** One of 16 plugins blocked the entire Node.js event loop during `plugins.runtime-post-bind` phase
- **Evidence:** `eventLoopDelayP99Ms=401311`, `eventLoopUtilization=1`
- **Fix applied:** 13 unused plugins disabled to reduce startup load:
  - Disabled: `openai`, `ollama`, `google`, `huggingface`, `alibaba`, `nvidia`, `xai`, `litellm`, `lmstudio`, `openrouter`, `opencode-go`, `sglang`, `vllm`
  - Remaining active: `deepseek`, `tavily`, `anthropic`, `minimax`, `discord`, `telegram`, `browser`, `talk-voice`, `memory-core`, `github` + stock plugins
- **Still not disabled:** `azure-speech`, `elevenlabs`, `deepgram`, `microsoft`, `senseaudio`, `fal`, `kie`, `runway`, `geolocation`, `web-readability`, `document-extract`, `clawrouter`, `copilot-proxy`, `microsoft-foundry`, `linux-node`

## Open Items (updated 2026-10-03)
- **Schwab API**: REFRESH TOKEN REVOKED (2026-09-23). Needs full re-auth. Redirect URI changed to `https://127.0.0.1:9876/schwab`. Docs: `docs/SCHWAB_OAUTH.md`. User wants to re-auth tomorrow.
- **Browser MCP**: restart needed occasionally (Chrome DevTools timeout after screenshots).
- **Telegram heartbeat alerts**: ✅ FIXED 2026-09-28 — target now set to `telegram`, verified working.
- **Condo sale**: HOA approval still pending since Jul 30 (~9+ weeks). Likely stalled.
- **update_stock_data_check.py**: EXISTS and WORKING — checks if stock data already loaded today and skips if so. Mon-Fri market hours.
- **⛔ OpenClaw CRON BROKEN (Windows):** DataCloneError on all isolated-session jobs. `command` payloads use `sh -lc` (doesn't exist on Windows). 14+ jobs affected. Issue: #161272.
- **Memory maintenance**: last done 2026-10-03 ✓


## Jarsy Extraction (2026-04-06, updated 2026-10-11)

### Scripts
- `jarsy_launch_and_login.py` — launches Chrome with `jarsy_profile` on debug port 9222, injects saved cookies, verifies PE content. Checks cookie freshness (max 25 days).
- `jarsy_extract.py` — connects via CDP, extracts presale + live tokens from PE page, saves to JSON. Uses existing Chrome session (leaves it open).
- `jarsy_save.py` — loads JSON files, upserts to DB via `jarsy_asset` (presale) + `jarsy_asset_live` (live)
- `jarsy_check_extracted.py` — verifies JSON files exist and have content
- `jarsy_insert_scan.py` — creates scan_id in DB

### Cookie-Based Login (no OAuth)
- Session cookies captured from logged-in Chrome session → `jarsy_cookies.pkl`
- Chrome profile: `C:\Users\shaowei_l\AppData\Local\Google\Chrome\User Data\jarsy_profile`
- Cookie file: `C:\Users\shaowei_l\.openclaw\workspace\jarsy_cookies.pkl`
- When cookies expire (~25 days): Telegram alert fires → run `save_cookies.py` after one manual login

### Database Tables
- `jarsy_asset` — presale tokens
- `jarsy_asset_live` — live tokens
- Both: issuer, token_ticker, presale_price, currency, round_size,感兴趣吗, status, image_url, description, network, scan_id, created_at

### Cron Job
- **Name:** Jarsy Token List Extraction
- **Schedule:** Mon-Fri 10 AM ET
- **Job ID:** d794a9c9-c4bf-4129-ab37-40d87f6dc30b
- **Session target:** isolated
- ⚠️ **DISABLED 2026-10-11** — Jarsy Chrome profile cache cleaned (144 MB freed). Cron job disabled.

### Real Data (Sep 22, 2026)
- 34 presale + 29 live tokens extracted (scan_id=310).

---

## Schwab Trading (2026-04-01)

### Status: ✅ WORKING (direct REST, NOT schwabdev)
- schwabdev library is BROKEN: tokens.db is empty, OAuth flow requires interactive browser
- **Working approach:** Direct `requests` calls with token refresh via `schwab_refresh.py`
- Tokens in `~/.schwab_tokens.json` — refreshed manually when expired
- Refresh token expires ~weekly — re-auth via `schwab_oauth_manual.py` when needed
- API Base: `https://api.schwabapi.com`

### Key Endpoints (verified working)
- `GET /trader/v1/accounts/accountNumbers` — linked accounts
- `GET /trader/v1/accounts/{accountHash}?fields=positions` — positions with hash
- `GET /marketdata/v1/quotes?symbols=USO,SPY` — real-time quotes (NOTE: ?symbols= NOT /{symbol})
- Quote data: `extended.lastPrice` (NOT `mark`)
- Note: `^VIX` is index, not tradable via quotes endpoint — use yfinance for VIX
- **Stock market check**: NOT RUN recently. Last check was 2026-08-07. `update_stock_data_check.py` doesn't exist — needs to be created or the check script revised.

### Main Trading Account (#12783263)
- Type: MARGIN (Day Trader)
- Market Value: ~$416K
- Key positions (as of 2026-04-07 noon): TSLL 7000 shares, TSLA 400 shares, NVDA 750 shares, UNH 110 shares
- Many active options positions (calls/puts on TSLL, MARA, USO, NVDA, PLTR, etc.)

### Integration Scripts
- `schwab_api.py` — main wrapper (outdated, needs update to match current approach)
- `schwab_refresh.py` — token refresh (works, but refresh token also expires ~weekly)
- `schwab_api_monitor.py` — API health check cron (corrected endpoints, disabled by user)

### Token Refresh
- Tokens in `~/.schwab_tokens.json`
- Refresh via: `python schwab_refresh.py` (direct POST, no schwabdev)
- If refresh fails with "unsupported_token_type": OAuth re-auth required

### Notes
- All 5 linked accounts returned — 4 have $0 balance, main account (#12783263) is active
- Account hash needed for positions endpoint (returned by accountNumbers)

### Schwab API Credentials
- **API Key:** `ydIVYBppTj7v8z3KnOfZngGgXNfSWswlwK4HwhVmfC1GURGn`
- **Redirect URI:** `https://desktop-rntitap.tail4c8778.ts.net/schwab`
- **Token file:** `C:\Users\shaowei_l\.schwab_tokens.json`
- **Token DB (broken):** `C:\Users\shaowei_l\.schwabdev\tokens.db`

## Alpaca Trading (Paper)
- **API Key:** `PK73B3GLW34N4E3URFVCLYKBPS`
- **Secret Key:** `AiDzSFfmAKv64aNyp94jRcE2EbELQqUSFTe5QR2kd7KU`
- **Base URL:** `https://paper-api.alpaca.markets/v2`
- **Account ID:** `0ca18d8c-a23d-407e-a240-7dbca5be04d6`
- **Account Number:** `PA3TTTW7DI9L`
- **Options Trading Level:** 3 (approved)
- **Buying Power:** $200,000 (paper)

### ⚠️ Positions Data Stale (last checked Apr 2026)
- All Apr 2026 positions are long expired/closed
- Positions check in heartbeat is DISABLED — credentials not in env vars during heartbeat runs
- heartbeat-state.json lastChecks.alpaca = 1785422400 (Apr 26, 2026) — very stale
- Needs: verify credentials in environment variables and resume position tracking

---

## YouTube Analysis

### Tools
- yt-dlp - Download subtitles
- reportlab - Generate PDFs

### Output
- PDF summaries saved to Downloads folder

---

## Windows Optimization (2026-03-19, updated 2026-03-20)

### Disabled Services
- AdobeARMservice (Adobe Acrobat Update)
- AdobeUpdateService
- WSearch (Windows Search) - high disk I/O on boot
- Spooler (Print Spooler)
- SysMain (Superfetch) - disk thrashing on boot
- RPCPerformanceService (Intel Remote PC) - high disk I/O on boot

### Quick Disable Commands (run as Admin)
```powershell
# Stop disk thrashing on boot
Set-Service -Name WSearch -StartupType Disabled; Stop-Service -Name WSearch -Force
Set-Service -Name SysMain -StartupType Disabled; Stop-Service -Name SysMain -Force

# Disable Intel Remote PC (if not used)
Set-Service -Name RPCPerformanceService -StartupType Disabled; Stop-Service -Name RPCPerformanceService -Force
```

### Disabled Scheduled Tasks
- BraveSoftwareUpdateTaskMachineCore/UA
- MicrosoftEdgeUpdateTaskMachineCore/UA
- OneDrive Startup/Reporting Tasks (all)
- McAfeeLogon

### Why These Were Disabled
- Redundant with Windows Defender (McAfee)
- High resource usage (Adobe, Windows Search, Superfetch)
- Not used (Print Spooler)
- Unneeded background updates (Brave, Edge, OneDrive)

### To Re-enable If Needed
- Services: `Set-Service -Name <ServiceName> -StartupType Automatic`
- Tasks: `Enable-ScheduledTask -TaskName <TaskName>`

---

## Discord Tracked Channels
| DB id | Discord Channel ID | Name | Category |
|-------|-------------------|------|----------|
| 1 | 1550893507118637096 | swl-small-trades | small-trades |
| 2 | 1551368477846143006 | swl-coach-trades | coach-trades |
| 3 | 1551368575112183808 | swl-coach-weekly | coach-weekly |
| 4 | 1550930741309866065 | swl-challenge-trades | challenge-trades |

## Finviz GapperMid Extraction (2026-03-16)

### Background
- Automated daily extraction of Finviz "GapperMid" screener results
- Uses Chrome browser (via chrome-relay profile) to access user's logged-in session
- Extracts stock table data via screenshot + image analysis

### Database Tables
- `finviz_screener` - Screener definitions (id, name, display_name, url)
- `scan` - Scan records (scan_id, scan_name, scan_time, status, source)
- `finviz_screener_scan_result` - Stock results per scan
- `finviz_screener_scan_result_summary` - Summary stats per scan

### Key Scripts
- `extract_finviz_gappermid.py` - Main extraction & save script
- `finviz_extracted_data.json` - Temp file for extracted data
- `cleanup_finviz_today.py` - Cleanup today's data before re-run
- `fix_constraint.py` - Fixed unique constraint to use (scan_id, ticker)

### GapperMid Screener URL
- https://finviz.com/screener.ashx?v=111&f=cap_midover,sh_curvol_o750,sh_price_o1,sh_relvol_o3&o=-change

### Cron Job
- **Name**: Finviz GapperMid Extraction
- **Schedule**: Mon-Fri 9:05 AM ET
- **Job ID**: 9ebb7955-6464-49c4-88b0-e530c71cb860

### Telegram
- Chat ID: 7923250382
- Message format: Ticker, Change%, Price + summary (total/gainers/losers)

### Important Notes
- Uses user's Chrome session (profile=chrome-relay) - must be logged in
- No stored credentials - relies on existing browser login
- Data saved with scan_id for tracking multiple runs per day
- Constraint updated to UNIQUE(scan_id, ticker) instead of UNIQUE(screener_name, ticker)
- **Sanity-check rows per scan**, not just scan status. A scan can be `completed` with only 2 rows (2026-10-22 scan_id 363) vs normal ~20. Query: `select scan_id, count(*) from finviz_screener_scan_result group by scan_id order by scan_id desc limit 5`. Duplicate scans get marked `skipped` by the same "already loaded today" guard that hides bad extractions.

### `change_pct` Corruption — FIXED 2026-10-26 (commit `6c6844e`)
- Stored `finviz_screener_scan_result.change_pct` values were wildly wrong vs reality (2026-10-23 scan_id 365: STLA -62.9% vs actual -7.3%, RITM +277% vs actual +6.8%, SLM/FLG/INFY/TKC also wrong).
- **Root cause:** Finviz's embedded-JSON `change` field is ALREADY a percentage (prevClose 15.75 → price 23.20 ⇒ change = 47.33). `scrape_finviz.py` treated it as an absolute price delta via `change/(price-change)*100` → garbage like −196%/−237%. **All historical GapperMid `change_pct` values before 2026-10-26 are suspect.**
- **Fix:** derive `change_pct` from prevClose/price, fall back to the raw `change` field; also stopped dropping `PE` (was always ''). Corrected data loaded as a NEW scan_id 369 (20 rows) — old scans preserved.
- This field feeds the Telegram ">5% mover" summary, so the fix removes false alerts.
- **Always sanity-check GapperMid movers against live quotes (Yahoo chart API) before reporting them.**
- Script: `hb_quotes.py` fetches watchlist quotes; extend its WATCH list to include flagged tickers for spot checks.

### Discord Pipeline Health Check (verified 2026-10-26)
- **Do NOT assume the Discord fetch is broken when it returns 0.** Check `discord_channel.last_fetched_at` first — if it is recent, the pipeline is healthy and there genuinely were no new posts.
- Verified 2026-10-26: `last_fetched_at` = 2026-10-26 08:30 ET (coach-trades), 08:00 ET (coach-weekly); `discord_message` max created_at 2026-10-25 22:27 ET; `discord_trade_signal` max signal_date 2026-10-23 (111 rows).
- The 2026-10-25 "stale fetch / expired token" diagnosis was WRONG — it was a cursor/market-hours artifact.
- Column names: `discord_channel` name column is **`channel_name`** (PK `id`); `discord_message` FK is **`channel_id`** → joins `discord_channel.id` (not `channel_db_id`).
- **Signal parser now extracts strike + premium** (2026-10-26, commit `f82b664`). `Discord/myTrading/parse_signals.py` has a unified `_price_pat()` helper for entry/target/stop/**premium**/**strike**, and the price regex handles `$68.00`, `$68`, `68.00`, `68`, and **`$.55` / `.55`** (dollar-sign then bare decimal — the coach's premium format, previously unparseable). Result: `discord_trade_signal` 115 rows, 114 with `strike_price`, 107 with `premium_price`, max signal_date 2026-10-26.
- **Signal-coverage rule:** after a fetch, compare message count vs signal count (`SELECT ... COUNT(s.message_id)`). As of 2026-10-26, 115/132 channel messages produce a signal row; the ~17 without are legitimately non-signals (market commentary, watchlist posts, chat). A message with no signal row is usually a parsing miss, not a market-commentary message.
- **No natural dedup key on `discord_trade_signal`** — only `id` (PK) and `signal_id` (UUID unique). Repeated coach posts of the same trade create near-duplicate rows (e.g. BE 275 PUT existed as both msg 6495 and 6517). Dedupe manually by (stock_ticker, strike_price, expiration_date, premium_price).

### DB Column Name Gotchas (verified 2026-10-22)
- `stock_technical` date column is **`date`** (not `trade_date`); other cols: ticker, open, high, low, close, volume, rsi, macd, macd_signal, sma_20/50/200, bb_*, atr, signals, recommendation, stop_loss, tp1/2/3
- `discord_trade_signal` uses **`stock_ticker`** (not ticker) and `asset_class`, `strategy_type`, `option_type`, `strike_price`, `entry_premium`, `expiration_date`, `author_username`, `signal_date`
- `discord_trade_signal` has 115 rows as of 2026-10-26 (max signal_date 2026-10-26)
- **fintech DB is reachable at `127.0.0.1:5432` from the workspace shell.** Heartbeat logs claiming "DB 10.0.0.10 unreachable (timeout)" refer to a different/legacy host — do not assume the local DB is down.

---

## QuantDinger (2026-09-25)

### Status
- Repo cloned at `C:\QuantDinger` (latest from GitHub)
- Docker Desktop installed (v29.8.0) — WSL2 installed, reboot required
- Docker Desktop unable to start BEFORE reboot (expected — WSL just installed)
- Installer saved at `C:\temp\docker_install.exe`

### What to do after reboot
1. Start Docker Desktop: `Start-Process 'C:\Program Files\Docker\Docker\Docker Desktop.exe'`
2. Wait ~60s for Docker engine to start
3. Verify: `& 'C:\Program Files\Docker\Docker\resources\bin\docker.exe' info`
4. Configure `.env` and `backend.env` in `C:\QuantDinger`
5. Run: `docker compose -f docker-compose.ghcr.yml up -d`
6. Access at http://localhost:8889

### Admin Credentials (from install.ps1)
- Username: quantdinger
- Password: YourSecurePass123!
- Email: shaowei_l.j@hotmail.com

### Docker Containers (from docker-compose.ghcr.yml)
- quantdinger-frontend (port 8889)
- quantdinger-mobile (port 8889 H5)
- quantdinger-backend (port 5000/127.0.0.1)
- quantdinger-db (port 5432/127.0.0.1)
- quantdinger-redis (port 6379/127.0.0.1)
- prometheus (port 9090)
- alertmanager (port 9093)
- grafana (port 3000)

### Database
- Host: 127.0.0.1:5432
- User: quantdinger
- Password: quantdinger123

### Config Files Needed
- `C:\QuantDinger\.env` — orchestration config (set `IMAGE_TAG=v5.3.1`, frontend URL, ports)
- `C:\QuantDinger\backend.env` — runtime secrets (admin credentials, DB password, DeepSeek key)

### Previous Install (2026-03-20, STALE — path was C:\Users\shaow\QuantDinger)
- Username: quantdinger / Password: YourSecurePass123!
- DB: 127.0.0.1:5433

### Project Location
- C:\Users\shaow\QuantDinger
- Config: backend_api_python/.env

---

## User Preferences (2026-03-21)

### Execution Mode
- **Analyze first, execute after confirmation**: When user gives a command, provide feedback on what I understand and wait for "go" or explicit confirmation before executing
- Do NOT execute anything without user's explicit instruction to proceed

### OpenClaw Log & Backup Location
- **Path:** `D:\mylogs\openclaw\` (breakdown by year, e.g. `D:\mylogs\openclaw\2026\`)
- Use this for all future OpenClaw-related backups and logs


- **MiniMax is the default LLM** (currently M2.7)
- If any skill needs to use a **different LLM provider** (e.g., OpenAI, Anthropic, DeepSeek, etc.), always prompt the user for confirmation first
- Exception: MiniMax's own API (api.minimax.io) is fine to use without asking

---

## OpenClaw Upgrades — Procedure (START HERE)

### BEFORE UPGRADING
1. Backup: `D:\mylogs\openclaw_backup_win.ps1` (or `openclaw_backup_mac.sh`)
2. Confirm backup exists before proceeding

### UPGRADE STEPS
1. Check npm latest: `npm view openclaw versions --json | Select-Object -Last 5`
   - GitHub releases may show higher version than npm (check npm first)
2. Kill gateway: `Stop-Process -Id <PID>` (find PID via `Get-Process node`)
   - Don't use `openclaw gateway stop` — it may restart itself
3. Run install: `npm i -g openclaw@latest --no-fund --no-audit`
   - OR specific version: `npm i -g openclaw@2026.X.Y`
4. Start gateway: `openclaw gateway start` (or just wait for it to restart via openclaw tool)
5. Verify: `npm list -g openclaw` and `config.get` -> `meta.lastTouchedVersion`
6. If Control UI shows old version -> hard refresh (Ctrl+Shift+R)

### KNOWN BUGS
- `gateway update.run` fails with EBUSY if gateway is running — kill it first
- `config.patch` and `config.apply` do FULL REPLACE of openclaw.json — always backup first
- After upgrade, if error `Missing workspace template: AGENTS.md`:
  - Copy `C:\Users\shaow\.openclaw\workspace\*.md` -> `C:\Users\shaow\AppData\Roaming\npm\node_modules\openclaw\docs\reference\templates\`
- `openclaw` CLI not in PATH inside PowerShell scripts — use `node (npm root -g)\openclaw\openclaw.mjs`

### RESTORE IF SOMETHING BREAKS
- `D:\mylogs\openclaw_backup_win.ps1 [-ZipPath] <path> [-DryRun]`
- Or manually: extract zip, copy openclaw.json + workspace/ back to `~/.openclaw/`
- Cron jobs: `openclaw cron import --file <cron_jobs.json>`

## OpenClaw / Tailscale Remote Access (RESOLVED 2026-03-27)

### MacMini Control UI — RESOLVED
- **Problem:** Control UI showed "pairing required" on Mac Mini even with token auth + `allowTailscale: true`
- **Root cause:** Control UI has a separate device identity WebSocket check that bypasses token auth
- **Fix:** `"dangerouslyDisableDeviceAuth": true` added to `gateway.controlUi` in openclaw.json
- **Access URL:** `https://desktop-rntitap.tail4c8778.ts.net/` from Mac Mini browser
- **Backup:** `C:\Users\shaow\Downloads\openclaw_backup_macmini_2026-03-27-101045.json`
- **Restore docs:** `C:\Users\shaow\Downloads\OPENCLAW_MACMINI_RESTORE.md`
- **Status:** ✅ Fully resolved

### Config flags for Tailscale access
```json
"gateway": {
  "controlUi": {
    "allowedOrigins": [
      "http://localhost:18789",
      "http://127.0.0.1:18789",
      "https://100.84.39.6:18789",
      "https://desktop-rntitap.tail4c8778.ts.net"
    ],
    "dangerouslyDisableDeviceAuth": true
  },
  "auth": {
    "mode": "token",
    "allowTailscale": true
  },
  "tailscale": {
    "mode": "serve"
  }
}
```

---

## SPY Drawdown + VIX Analysis Method (2026-03-27)

### Scripts
- `spy_drawdown_analysis.py` — identifies drawdowns >6% over 5 years, defensive asset performance
- `spy_bounce_analysis.py` — bounce entry signals after major drawdowns
- `spy_vix_analysis.py` — VIX > 30 periods and entry signals
- `spy_vix_entry_analysis.py` — what happened AFTER VIX peaked
- `spy_vix_charts.py` — generates 4 charts: 5yr SPY+VIX, from peak comparison, current RSI+VIX, bounce trend overlay

### Key Findings (as of 2026-03-27)
- 6 major SPY drawdowns (>6%) in last 5 years
- VIX > 30 periods: Feb 2022, Apr 2022, May 2022, Sep 2022, Feb 2025, and current (Mar 2026)
- Current VIX peaked Mar 20 at 31.2 but VIX still climbing (unusual — normally falls after peak)
- SPY RSI at 23.3 — deeply oversold
- SPY below SMA20 ($666) and SMA50 ($680)
- Bounce trend line: flat at 0%/day — bounce NOT confirmed

### Entry Rules for Bounce Play
1. VIX must have peaked AND be falling (if VIX still climbing, not yet)
2. RSI at trough < 30 (high confidence < 25)
3. Price below SMA50 by > 5%
4. Wait for price to CLOSE above 20-day bounce trend line (primary entry signal)
5. Wait for first pullback 3-7 days after trend break
6. Stop-loss: below trough low

### Historical Results
- Trend line break at days 3-6 returned +2% to +9% over 20 days
- Day-5 pullback entry returned +3.7% to +5.7% over 20 days
- Deep drawdowns (>15%) produced +12-26% over 60 days
- Average bounce: +8-10% over 20 days

### Defensive Assets (during drawdowns)
- UUP (USD): avg +3.3% — most reliable
- GLD (Gold): avg -1.7% — stable but geopolitical risk
- TLT (20yr Bond): avg -8.9% — unreliable (rate-sensitive)
- SLV (Silver): avg -11.9% — worst

### Charts (saved to D:\mylogs\myjournal\2026\03\)
- `spy_vix_5yr.png` — 5-year SPY + VIX overlay
- `spy_vix_from_peak.png` — normalized comparison from VIX peak
- `spy_vix_rsi_current.png` — current drawdown with RSI panel
- `spy_bounce_trend_overlay.png` — bounce trend overlays

### Weekly Analysis Workflow
To run the same analysis next week:
1. `python spy_vix_analysis.py` — check VIX status and entry signals
2. `python spy_bounce_analysis.py` — update bounce trend lines
3. Check: VIX > 30? RSI oversold? Price above bounce trend line?
4. Look at the 4 charts and compare to historical patterns

## QuantDinger Docker Ports (IMPORTANT)
- Docker Desktop occupies port 5432 for its own PostgreSQL → conflicts with fintech DB
- Fix: QuantDinger postgres maps to container port 5432, exposed on host port **5433**
- Connection: `host=127.0.0.1, port=5433, user=quantdinger, password=quantdinger123`
- Frontend: http://localhost:8889 | Backend API: http://localhost:5000 | Redis: 6379

## OpenClaw PATH Fix (2026-03-29)
- Reinstall created only .ps1 wrapper but .PS1 not in PATHEXT
- Fix: create C:\Users\shaow\AppData\Roaming\npm\openclaw.cmd batch wrapper
- Current version: 2026.3.28

## Claude Code Setup (2026-03-29)

### Installation
- Package: @anthropic-ai/claude-code (npm install -g)
- Version: 2.1.87
- Location: C:\Users\shaow\AppData\Roaming\npm\claude.cmd
- Model: MiniMax-M2.7 (via MiniMax API endpoint)

### Config
- Settings: C:\Users\shaow\.claude\settings.json
- MiniMax API endpoint: https://api.minimax.io/anthropic
- MiniMax API key: stored in settings.json env.ANTHROPIC_AUTH_TOKEN

### Integration with OpenClaw
- AGENTS.md has delegation rules: I delegate multi-file coding tasks to Claude Code
- Claude Code workspace: C:\Users\shaow\.openclaw\workspace\
- Key projects: stock_app.py, Finviz scraper, IBD pipeline, QuantDinger
- OpenSpec can be installed: github.com/chyiiiiiiiiiiii/openspec-skills

## Tailscale Serve (2026-03-29)
- Command: tailscale serve --bg 18789 --proxies gateway to Tailscale HTTPS
- URL: https://desktop-rntitap.tail4c8778.ts.net/
- Config persistent across restarts

## Obsidian Vaults (2026-04-12)
- GitHub: shaoweil9921/obsidian_trading + obsidian_life (both private)
- Local: C:\Data\Obsidian_root\Obsidian_trading\ and Obsidian_life\
- Token: <GITHUB_PAT>
- Each vault: own .git, own remote, own GitHub repo

## OpenClaw Version
- Current: **2026.9.9** (2026.9.8 → 2026.9.9 via npm update, 2026-10-10) — npm latest as of 2026-10-27 is **2026.10.8** (installed still trails; upgrade pending user decision)
- Gateway WS URL: `ws://localhost:18789` — use `localhost` NOT `127.0.0.1` (gateway listens on IPv6 only)
- Config: `C:\Users\shaowei_l\.openclaw\openclaw.json`
- Workspace: `C:\Users\shaowei_l\.openclaw\workspace`
- Upgrades via: `npm i -g openclaw@latest --no-fund --no-audit`

## DeepSeek Backup Provider
- API: OpenAI Completions compatible, base URL `https://api.deepseek.com/v1`
- Key: `sk-caf…b368` (DeepSeek chat model)

## Telegram
- Bot token: `863194…Ul-Q`
- My chat ID: `7923250382`
- Gateway heartbeat target: `telegram`

## Discord Bot (guild server IDs)
- `1158828571687669800`
- `1550885500657737748`

## Condo Sale - 450 NW 20th ST Unit 212 Boca Raton (2026-07-31, ongoing)
- Sellers: Shaowei Luo + Fen Chen | Buyers: Alex Ramirez + Nathalie Vilvandre Ramirez
- Sale price: $230K | Loan policy: $119,600
- Outstanding: HOA approval from Casa Del Rio, Notice of Commencement clearance
- Title company: The Closing Team, (954) 289-1466
- Status (as of Jul 31): waiting on HOA approval — no change from prior days

## Alpaca Trading Config Issues (known)
- `alpaca_trade_api` module not available in heartbeat environment
- Alpaca credentials NOT in environment variables
- Positions check disabled until credentials are configured
- Key env vars needed: ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_PAPER_URL

## Telegram Heartbeat — FIXED (2026-09-28)
- Heartbeat was configured with `target: "none"` — silently discarding heartbeats
- Fixed: `openclaw config set agents.entries.main.heartbeat.target telegram`
- Verified: `agents.main.heartbeat.target` now shows `"telegram"` in health response
- Heartbeats should now deliver to Telegram chat 7923250382 every 2h during active hours

## QuantDinger (C:\QuantDinger)

### Startup (after Docker Desktop install/reboot)
Docker Desktop occupies port 5432 for its own PostgreSQL, conflicting with fintech DB on same port.

```powershell
Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
# Wait ~30s
$env:DB_PORT="127.0.0.1:5433"
docker compose -f C:\QuantDinger\docker-compose.yml up -d
```

### URLs (all localhost)
- Frontend (web): http://localhost:8888
- Mobile H5: http://localhost:8889
- Backend API: http://localhost:5000

### Common Commands
```powershell
# Stop: docker compose -f C:\QuantDinger\docker-compose.yml down
# Logs: docker compose -f C:\QuantDinger\docker-compose.yml logs -f backend
# Restart: docker compose -f C:\QuantDinger\docker-compose.yml restart backend
# Full rebuild: $env:DB_PORT="127.0.0.1:5433"; docker compose -f C:\QuantDinger\docker-compose.yml up -d --build
```

### Ports
- 8888: Frontend
- 8889: Mobile H5
- 5000: Backend API
- 5433: QuantDinger postgres (maps to 5432 inside container, avoids fintech DB on 5432)
- 6379: Redis
