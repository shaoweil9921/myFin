"""One-off migration: remove hardcoded Postgres password from workspace scripts.

Replaces the literal with a call to the canonical resolver (db_pw.py at the
workspace root, re-exported via _db_pw.py shims in finviz/ and ibd/).

Run:  python _migrate_db_creds.py [--dry-run]
"""
import io
import os
import re
import sys

WS = r"C:\Users\shaowei_l\.openclaw\workspace"


def _resolve_secret():
    """Read the current DB password so we can hunt for it without hardcoding it."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment", 0) as key:
            val, _ = winreg.QueryValueEx(key, "DB_PW")
            if val:
                return str(val)
    except Exception:
        pass
    return os.environ.get("DB_PW") or os.environ.get("DB_PASSWORD") or ""


SECRET = _resolve_secret()

# path -> import line to insert
IMPORT_ROOT = "from db_pw import get_db_pw as _db_pw"
IMPORT_SUB = "from _db_pw import get_db_pw as _db_pw"

TARGETS = {
    # root-level scripts
    "jarsy_check.py": IMPORT_ROOT,
    "jarsy_check_extracted.py": IMPORT_ROOT,
    "jarsy_close_scan.py": IMPORT_ROOT,
    "jarsy_cron.py": IMPORT_ROOT,
    "jarsy_db.py": IMPORT_ROOT,
    "jarsy_fail_scan.py": IMPORT_ROOT,
    "jarsy_insert.py": IMPORT_ROOT,
    "jarsy_insert_live.py": IMPORT_ROOT,
    "jarsy_insert_scan.py": IMPORT_ROOT,
    "jarsy_login_120.py": IMPORT_ROOT,
    "jarsy_login_required.py": IMPORT_ROOT,
    "jarsy_login_update.py": IMPORT_ROOT,
    "jarsy_query.py": IMPORT_ROOT,
    "jarsy_save.py": IMPORT_ROOT,
    "jarsy_set_login.py": IMPORT_ROOT,
    "jarsy_update_login.py": IMPORT_ROOT,
    "process_ibd.py": IMPORT_ROOT,
    "load_finviz_data.py": IMPORT_ROOT,
    "update_stock_data_check.py": IMPORT_ROOT,
    # finviz/
    "finviz/cron_finviz_step1.py": IMPORT_SUB,
    "finviz/finviz_browser.py": IMPORT_SUB,
    "finviz/finviz_complete.py": IMPORT_SUB,
    "finviz/finviz_gappermid.py": IMPORT_SUB,
    "finviz/finviz_pipeline.py": IMPORT_SUB,
    "finviz/finviz_status.py": IMPORT_SUB,
    "finviz/run_finviz_scan.py": IMPORT_SUB,
    # ibd/
    "ibd/load_all.py": IMPORT_SUB,
    "ibd/load_aug10_aug17.py": IMPORT_SUB,
    "ibd/save_to_obsidian.py": IMPORT_SUB,
    "ibd/update_groups.py": IMPORT_SUB,
    # Discord
    "Discord/myTrading/parse_signals.py": IMPORT_SUB,
    "Discord/myTrading/save_to_postgres.py": IMPORT_SUB,
    "Discord/myTrading/setup_table.py": IMPORT_SUB,
}

DRY = "--dry-run" in sys.argv


def add_import(src, import_line):
    """Insert the import after the module docstring / first import block."""
    if import_line in src:
        return src
    lines = src.splitlines(keepends=True)
    # find end of docstring
    idx = 0
    if lines and lines[0].lstrip().startswith(('"""', "'''")):
        q = lines[0].lstrip()[:3]
        if lines[0].strip().endswith(q) and len(lines[0].strip()) > 3:
            idx = 1
        else:
            for i in range(1, len(lines)):
                if q in lines[i]:
                    idx = i + 1
                    break
    lines.insert(idx, f"\n{import_line}\n")
    return "".join(lines)


def migrate(rel, import_line):
    path = os.path.join(WS, rel)
    with io.open(path, "r", encoding="utf-8") as f:
        src = f.read()
    orig = src

    # 1. dict entries:  "password": "<literal>",   /   'password': '<literal>',
    src = re.sub(r"(['\"])password\1\s*:\s*['\"]" + re.escape(SECRET) + r"['\"]",
                 r"\1password\1: _db_pw()", src)

    # 2. keyword args:  password='<literal>'   /   password="<literal>"
    src = re.sub(r"password\s*=\s*['\"]" + re.escape(SECRET) + r"['\"]",
                 "password=_db_pw()", src)

    # 3. module-level constant: DB_PWD = "<literal>"  /  DB_PASSWORD = "..."
    src = re.sub(r"^(DB_PWD|DB_PW|DB_PASSWORD)\s*=\s*['\"]" + re.escape(SECRET) + r"['\"]",
                 r"\1 = _db_pw()", src, flags=re.M)

    # 4. empty password literal (jarsy_query.py)
    src = re.sub(r"password\s*=\s*['\"]['\"]", "password=_db_pw()", src)
    src = re.sub(r"(['\"])password\1\s*:\s*['\"]['\"]", r"\1password\1: _db_pw()", src)

    # 5. env fallback carrying the literal
    src = re.sub(r"os\.environ\.get\(\s*['\"]DB_PASSWORD['\"]\s*,\s*['\"]" +
                 re.escape(SECRET) + r"['\"]\s*\)",
                 "os.environ.get('DB_PASSWORD', '')", src)

    if SECRET in src:
        print(f"  !! {rel}: literal still present, needs manual review")
        return False

    if src != orig:
        src = add_import(src, import_line)
        if not DRY:
            with io.open(path, "w", encoding="utf-8", newline="") as f:
                f.write(src)
        print(f"  OK {rel}")
        return True
    print(f"  -- {rel}: no change")
    return False


def main():
    print(f"=== migrating hardcoded DB password (dry_run={DRY}) ===")
    changed = 0
    for rel, imp in TARGETS.items():
        p = os.path.join(WS, rel)
        if not os.path.exists(p):
            print(f"  ?? {rel}: MISSING, skipped")
            continue
        if migrate(rel, imp):
            changed += 1
    print(f"=== {changed} file(s) migrated ===")

    # verify
    print("\n=== residual literal scan (tracked files) ===")
    os.system(
        f'cd /d "{WS}" && git ls-files "*.py" | findstr /B /C:"{SECRET}" >nul 2>&1'
    )
    import subprocess
    out = subprocess.run(
        ["git", "ls-files", "*.py"], cwd=WS, capture_output=True, text=True
    ).stdout.split()
    hits = []
    for rel in out:
        fp = os.path.join(WS, rel)
        try:
            with io.open(fp, "r", encoding="utf-8", errors="replace") as f:
                if SECRET in f.read():
                    hits.append(rel)
        except Exception:
            pass
    print("files still containing the literal:")
    for h in hits:
        print("   ", h)
    if not hits:
        print("    (none)")


if __name__ == "__main__":
    main()
