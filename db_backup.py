r"""
db_backup.py
Backup the fintech PostgreSQL database to C:\Data\postgres_backup\
Usage: python db_backup.py
Cron: Saturdays at 1 PM ET
"""
import os, sys, gzip, subprocess, shutil
from datetime import datetime
from pathlib import Path

BACKUP_DIR = Path(r"C:\Data\postgres_backup")
DB_NAME = "fintech"
DB_USER = "postgres"
PG_BIN = r"C:\Program Files\PostgreSQL\18\bin"


def get_pg_password():
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment", 0)
        try:
            val, _ = winreg.QueryValueEx(key, "DB_PW")
            return val
        finally:
            winreg.CloseKey(key)
    except Exception:
        pass
    return os.environ.get("DB_PW", "")


def run():
    password = get_pg_password()
    if not password:
        print("[ERROR] DB_PW not found in registry HKCU\\Environment")
        sys.exit(1)

    env = os.environ.copy()
    env["PGPASSWORD"] = password

    ts = datetime.now().strftime("%Y-%m-%d")
    out_sql = BACKUP_DIR / f"fintech_{ts}.sql"
    out_gz  = out_sql.with_suffix(".sql.gz")

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    pg_dump = shutil.which("pg_dump", path=PG_BIN) or "pg_dump"

    print(f"[1/2] Running pg_dump for {DB_NAME}...")
    result = subprocess.run(
        [pg_dump, "-h", "127.0.0.1", "-p", "5432", "-U", DB_USER, "-f", str(out_sql), DB_NAME],
        env=env, capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"[ERROR] pg_dump failed:\n{result.stderr}")
        sys.exit(1)

    print(f"[2/2] Gzipping to {out_gz.name}...")
    with open(out_sql, "rb") as f_in, gzip.open(out_gz, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
    out_sql.unlink()

    size_mb = out_gz.stat().st_size / 1e6
    print(f"[OK] Backup saved: {out_gz.name} ({size_mb:.1f} MB)")

    # Cleanup: keep only last 8 weekly backups
    existing = sorted(BACKUP_DIR.glob("fintech_*.sql.gz"), key=lambda p: p.name)
    for old in existing[:-8]:
        print(f"  [CLEANUP] Removing old backup: {old.name}")
        old.unlink()

    print("[DONE]")


if __name__ == "__main__":
    run()
