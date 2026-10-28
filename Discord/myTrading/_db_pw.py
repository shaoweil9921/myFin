r"""Shared DB password utility — reads from Windows registry HKCU\Environment.
All Discord pipeline scripts should import this instead of hardcoding env var lookups.
"""
import os, winreg

def get_db_pw():
    """Read DB_PW from Windows registry. Falls back to DB_PASSWORD env var."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment")
        db_pw, _ = winreg.QueryValueEx(key, "DB_PW")
        winreg.CloseKey(key)
        return db_pw
    except Exception:
        return os.environ.get("DB_PASSWORD", "")

DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 5432,
    "user": "postgres",
    "dbname": "fintech",
    "password": get_db_pw(),
}
