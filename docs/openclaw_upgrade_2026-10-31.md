# OpenClaw Upgrade Runbook — 2026-10-31

**Status:** PREPARED — awaiting owner confirmation to execute
**Prepared:** 2026-10-31 11:48 ET
**Owner approval to execute:** ☐ NOT YET GRANTED

---

## 1. Current vs Target

| | Version |
|---|---|
| Installed (running now) | `2026.9.9` (bcfc888) |
| npm latest | `2026.10.9` |
| Gap | 10 minor releases |

Gateway is currently **healthy** — running as a Windows Scheduled Task, pid 7808, listening on
`ws://127.0.0.1:18789`, reachable. There is no partial/failed install on disk: the previous update
attempt failed at the *service handoff* step (`managed-service-handoff-helper-failed`), not during
npm install, so the running version is a clean `2026.9.9`.

---

## 2. Pre-Execution Backup (DONE — 2026-10-31 11:48 ET)

### 2a. Automations export

`memory/automations-backup-2026-10-31.json` — full `cron list --all --json` dump.

Verified: **19 jobs** (14 enabled, 5 disabled), every job has `id` / `name` / `schedule` / `payload`.

> Note: PowerShell `>` redirection writes UTF-16 and corrupts JSON. Use
> `| Out-File -Encoding utf8 -NoNewline` and read with `encoding="utf-8-sig"`.

### 2b. File + database backup

Location: `C:\Users\shaowei_l\.openclaw\backup\2026-10-31_pre-upgrade\`

| File | Size | Integrity |
|---|---|---|
| `openclaw.json` | 12,386 | parses OK |
| `MEMORY.md` | 58,914 | — |
| `USER.md` | 2,126 | — |
| `SOUL.md` | 1,999 | — |
| `AGENTS.md` | 13,273 | — |
| `HEARTBEAT.md` | 1,888 | — |
| `automations-backup-2026-10-31.json` | 50,927 | 19 jobs, all fields present |
| `openclaw.sqlite` (state) | 34,684,928 | `PRAGMA integrity_check = ok` · 111 tables · `cron_jobs` 19 rows · `cron_run_receipts` 503 rows |
| `openclaw-agent.sqlite` (sessions) | 199,618,560 | `PRAGMA integrity_check = ok` · 69 tables |

Config sanity at backup time: `providers = [minimax-portal]`, default model
`minimax-portal/MiniMax-M2.7`, `plugins.entries.deepseek.enabled = false`,
`skills.workshop.autonomous.mode = off`.

**Not found (not backed up, do not exist on this host):**
- `exec-approvals.json` — no longer present at `C:\Users\shaowei_l\.openclaw\`. Last copy is the
  stale `backup\2026-05-07_09-07\exec-approvals.json`. **If exec is denied after the upgrade,
  that file must be recreated from scratch — see §6.**
- `TOOLS.md` — does not exist as a file. Its content was migrated into `AGENTS.md`
  (`### Local notes (migrated from TOOLS.md)`). `AGENTS.md` is backed up.

### 2c. Backup committed to GitHub — see §7

---

## 3. Execution Steps

### Step 1 — Upgrade the npm package

```
npm install -g openclaw@2026.10.9 --no-fund --no-audit
```

Expect: OpenClaw 2026.10.9. The gateway is **still running the old 2026.9.9 code** until restart.

### Step 2 — Restart the gateway (gateway-aware path only)

**Do NOT** `taskkill` by port/PID, do NOT run `openclaw update`, `npm install -g openclaw`, or
`openclaw gateway start` through exec or a detached job. Those bypass the gateway's own upgrade
path and leave the Windows Scheduled Task service unmanaged — which is exactly what produced
`managed-service-handoff-helper-failed` last time.

Use instead, in order of preference:
1. **In chat:** owner sends `/update` (works when `commands.restart` is enabled, the default).
2. **Via the `openclaw` tool:** request a gateway update/restart through it.

Both coordinate the restart and emit the completion notice. If starting manually for any reason,
run `openclaw gateway run` in the foreground — **`openclaw gateway start` times out on this host**
and leaves the service in an unclear state.

Identify the live process by its listening port, not by process name (several `node.exe` run here).

### Step 3 — Confirm the gateway came back

Ready when it reports listening on `ws://127.0.0.1:18789`.

```
openclaw status
```

Verify: gateway reachable, version reports `2026.10.9`, Scheduled Task still `registered · running`.

### Step 4 — Re-verify exec

Test `echo test` in a fresh message. If denied, reapply:

```
Set tools.exec.mode to "full" and tools.exec.safeBins to ["python", "pwsh"]
```

then re-test. If `exec-approvals.json` is genuinely required and absent, it must be recreated —
see §6.

### Step 5 — Re-verify cron jobs (MOST IMPORTANT)

**This is the step that failed on 2026-10-15**, when a gateway restart wiped `openclaw.sqlite` and
destroyed every cron job. Do not skip it.

```
openclaw cron list --all --json
```

Compare against `memory/automations-backup-2026-10-31.json`:
- 19 jobs present (14 enabled, 5 disabled)
- Job **IDs unchanged**
- `command`-payload jobs still carry the `cmd /c` argv form — **the `sh` → `cmd /c` fix does not
  survive an upgrade.** Verify `discord-fetch-signals` (id `e1e338d4`) and every other
  `command` job still uses `["cmd","/c","python ..."]`.
- `skill-collection-review-main` (id `47710e37`) still **disabled** — it is system-owned and must
  stay off, or it will re-raise hourly "Cron Job Failed" alerts.

If the job store was wiped, restore from the backup JSON and recreate the jobs.

### Step 6 — Re-verify plugins and config

```
openclaw plugins list
openclaw gateway call models.list
```

Expect: only `MiniMax-M2.7 / M2.1 / M2.5` under `minimax-portal`; `deepseek` plugin still
`enabled: false`; **no** `models.providers.deepseek` block (removed 2026-10-27).

If the upgrade re-adds a `deepseek` provider block, remove it again — that is what caused the
recurring "deepseek retired" gateway error.

### Step 7 — Re-verify the Discord signal pipeline

```
openclaw cron runs e1e338d4-3dc8-4ade-b570-5e92ecf8c14c
```

Confirm the last run is `ok`. Watch the next scheduled `*/15 8-17 * * 1-5` run for a real insert.

### Step 8 — Post-upgrade health check

```
openclaw status
```

Confirm no `⚠️ OpenClaw update failed` banner remains, and the version reads `2026.10.9`.

---

## 4. Rollback Plan

If the upgrade leaves the gateway broken:

1. `npm install -g openclaw@2026.9.9 --no-fund --no-audit`
2. Restore `C:\Users\shaowei_l\.openclaw\backup\2026-10-31_pre-upgrade\openclaw.json`
3. Restore `openclaw.sqlite` into `C:\Users\shaowei_l\.openclaw\state\openclaw.sqlite`
   **while the gateway is stopped** — restoring a live SQLite file corrupts it.
4. Restore `openclaw-agent.sqlite` into
   `C:\Users\shaowei_l\.openclaw\agents\main\agent\openclaw-agent.sqlite`
5. Restart the gateway via the gateway-aware path.

The sqlite files were verified `integrity=ok` at backup time, so this is a clean restore path.

---

## 5. Risk Register

| Risk | Severity | Mitigation |
|---|---|---|
| Cron job store wiped on restart (happened 2026-10-15) | **High** | Full automations JSON exported + committed; §3 Step 5 verification is mandatory, not optional |
| `cmd /c` argv shape lost on `command` jobs | High | Verify each `command` job's argv after restart; known non-persistent fix |
| Exec denied because `exec-approvals.json` is absent | Medium | Reapply via `openclaw` tool; recreate file if required (§6) |
| Gateway Scheduled Task left unmanaged | Medium | Use `/update` or the `openclaw` tool — never raw `taskkill`/`gateway start` |
| `deepseek` provider block re-added by the upgrade | Low | Re-check `models.list`; remove block if it returns |
| Update fails again at service handoff | Low | Gateway stays on the clean old version; rollback in §4 is straightforward |
| Session/history loss | Low | `openclaw-agent.sqlite` backed up (199 MB, integrity ok) |

---

## 6. Note on the Missing `exec-approvals.json`

This file is **not present** on the host. It was last seen in the stale
`backup\2026-05-07_09-07\` copy. If post-upgrade exec is denied and the `openclaw` tool's
"reapply exec config" path does not recreate it, the config must be written directly with a
`tools.exec.mode: "full"` and `tools.exec.safeBins: ["python","pwsh"]` block in
`C:\Users\shaowei_l\.openclaw\openclaw.json`. Do not fabricate approval IDs.

---

## 7. Post-Execution Checklist

- [ ] npm package reports `2026.10.9`
- [ ] Gateway restarted via gateway-aware path, reachable on `:18789`
- [ ] `openclaw status` shows version `2026.10.9`, no update-failure banner
- [ ] Exec works (`echo test`)
- [ ] 19 cron jobs present, IDs unchanged, `cmd /c` argv intact, skill-review still disabled
- [ ] `models.list` shows only MiniMax models, no DeepSeek provider
- [ ] Discord pipeline last run `ok`
- [ ] `MEMORY.md` updated with the new version + procedure outcome
- [ ] Changes committed to `github.com/shaoweil9921/myFin`
