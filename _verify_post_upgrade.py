"""Post-upgrade verification for the 2026-10-31 OpenClaw upgrade (2026.9.9 -> 2026.10.9).

Run this AFTER the gateway comes back from /update.
    python _verify_post_upgrade.py
Checks, in priority order:
  1. version + gateway health
  2. exec policy (tools.exec.mode) and exec-approvals.json presence
  3. cron jobs: count, IDs vs the pre-upgrade backup, argv shape, skill-review disabled
  4. models + plugins (no deepseek provider block)
Nothing here mutates state. Read-only.
"""
import json
import os
import subprocess
import sys

WORKSPACE = r"C:\Users\shaowei_l\.openclaw\workspace"
CONFIG = r"C:\Users\shaowei_l\.openclaw\openclaw.json"
STATE_DB = r"C:\Users\shaowei_l\.openclaw\state\openclaw.sqlite"
BACKUP = os.path.join(WORKSPACE, "memory", "automations-backup-2026-10-31.json")
TARGET = "2026.10.9"

fails, warns = [], []


def check(cond, label, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}" + (f" - {detail}" if detail else ""))
    if not cond:
        fails.append(label)
    return cond


def warn(cond, label, detail=""):
    print(f"  [{'OK  ' if cond else 'WARN'}] {label}" + (f" - {detail}" if detail else ""))
    if not cond:
        warns.append(label)


def run(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=90,
                           shell=isinstance(cmd, str),
                           encoding="utf-8", errors="replace")
        return (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        return f"<error: {e}>"


print("=" * 70)
print("POST-UPGRADE VERIFICATION - 2026-10-31")
print("=" * 70)

# ---------------------------------------------------------------- 1. version
print("\n1. VERSION & GATEWAY HEALTH")
ver = run("openclaw --version").strip()
print(f"  reported: {ver}")
check(TARGET in ver, "version is 2026.10.9", ver.splitlines()[0] if ver else "no output")

status = run("openclaw status")
check("reachable" in status, "gateway reachable")
check("2026.10.9" in status, "status banner shows 2026.10.9")
warn("Scheduled Task installed" in status or "Scheduled Task" in status,
     "Scheduled Task still registered")
if "update failed" in status.lower():
    fails.append("update-failure banner still present")
    print("  [FAIL] update-failure banner still present")
else:
    print("  [PASS] no update-failure banner")

# ---------------------------------------------------------------- 2. exec
print("\n2. EXEC POLICY")
try:
    with open(CONFIG, encoding="utf-8") as f:
        cfg = json.load(f)
except Exception as e:
    cfg = {}
    print(f"  [FAIL] could not read openclaw.json: {e}")
    fails.append("openclaw.json unreadable")

tools_cfg = cfg.get("tools", {})
exec_cfg = tools_cfg.get("exec", {}) if isinstance(tools_cfg, dict) else {}
mode = exec_cfg.get("mode")
print(f"  tools.exec.mode = {mode!r}")
warn(mode in ("full", "all"), "exec mode permissive", f"mode={mode}")
safe = exec_cfg.get("safeBins")
print(f"  tools.exec.safeBins = {safe}")

approvals = r"C:\Users\shaowei_l\.openclaw\exec-approvals.json"
exists = os.path.exists(approvals)
warn(exists, "exec-approvals.json present",
     "" if exists else "absent (known) — reapply via openclaw tool if exec denied")

# ---------------------------------------------------------------- 3. cron
print("\n3. CRON JOBS")
jobs = []
try:
    out = run("openclaw cron list --all --json")
    i = out.find("{")
    data = json.loads(out[i:])
    jobs = data.get("jobs", [])
except Exception as e:
    print(f"  [FAIL] could not read cron list: {e}")
    fails.append("cron list unreadable")

backup_jobs = []
if os.path.exists(BACKUP):
    try:
        with open(BACKUP, encoding="utf-8-sig") as f:
            backup_jobs = json.load(f)["jobs"]
    except Exception as e:
        print(f"  [WARN] backup unreadable: {e}")

check(len(jobs) == 19, "19 jobs present", f"found {len(jobs)}")
if backup_jobs:
    before = {j["id"] for j in backup_jobs}
    after = {j["id"] for j in jobs}
    missing = before - after
        check(not missing, "no job IDs lost",
          f"missing={sorted(missing)}" if missing else "all 19 IDs intact")

    # argv shape: command jobs must use cmd /c on Windows
    bad_argv = []
    for j in jobs:
        p = j.get("payload") or {}
        if p.get("kind") == "command":
            argv = p.get("argv") or []
            if not argv or str(argv[0]).lower() != "cmd":
                bad_argv.append((j["name"], argv[:3]))
    check(not bad_argv, "command jobs use cmd /c argv",
          "; ".join(f"{n}:{a}" for n, a in bad_argv) if bad_argv else "all correct")

    # enabled/disabled parity
    b_en = {j["id"] for j in backup_jobs if j.get("enabled")}
    a_en = {j["id"] for j in jobs if j.get("enabled")}
    check(b_en == a_en, "enabled/disabled set unchanged",
          f"diff={sorted(b_en ^ a_en)}" if b_en != a_en else "identical")

# skill-collection-review must stay disabled (system-owned, spams Telegram if enabled)
skr = [j for j in jobs if "skill-collection" in (j.get("name") or "")]
if skr:
    check(not skr[0].get("enabled"), "skill-collection-review-main still disabled",
          f"enabled={skr[0].get('enabled')}")
else:
    print("  [OK  ] skill-collection-review-main not in list (fine — system-owned)")

# ---------------------------------------------------------------- 4. models
print("\n4. MODELS & PLUGINS")
try:
    out = run("openclaw gateway call models.list")
    i = out.find("{")
    models = json.loads(out[i:]).get("models", [])
    ids = [f"{m.get('id')}({m.get('provider')})" for m in models]
    print(f"  models: {ids}")
    check(all("deepseek" not in (m.get("id") or "") for m in models),
          "no deepseek model exposed")
    check(any(m.get("provider") == "minimax-portal" for m in models),
          "minimax-portal models present")
except Exception as e:
    print(f"  [FAIL] models.list failed: {e}")
    fails.append("models.list failed")

providers = (cfg.get("models", {}) or {}).get("providers", {}) or {}
check("deepseek" not in providers, "no models.providers.deepseek block",
      f"providers={list(providers.keys())}")

entries = (cfg.get("plugins", {}) or {}).get("entries", {}) or {}
ds = entries.get("deepseek")
warn(not (ds and ds.get("enabled")), "deepseek plugin disabled",
     f"deepseek={ds}")

print("\n" + "=" * 70)
if fails:
    print(f"RESULT: {len(fails)} FAILURE(S): {fails}")
else:
    print("RESULT: ALL CHECKS PASSED")
if warns:
    print(f"WARNINGS: {warns}")
print("=" * 70)
sys.exit(1 if fails else 0)
