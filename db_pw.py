r"""Canonical PostgreSQL password resolver for the fintech database.

The password lives in the Windows user environment (HKCU\Environment\DB_PW).
Scripts should never hardcode it. Resolution order:

  1. HKCU\Environment\DB_PW   (registry — source of truth, survives shell restarts)
  2. DB_PW                     (process environment)
  3. DB_PASSWORD               (process environment, legacy name)

Usage:
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from db_pw import get_db_pw, DB_CONFIG

    conn = psycopg2.connect(**DB_CONFIG)
"""
import os
import winreg

_REG_NAME = "DB_PW"
_REG_PATH = r"Environment"


def get_db_pw() -> str:
    """Resolve the fintech DB password. Returns "" if it cannot be found."""
    # 1. Windows user environment registry
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_PATH, 0) as key:
            val, _ = winreg.QueryValueEx(key, _REG_NAME)
            if val:
                return str(val)
    except Exception:
        pass

    # 2/3. Process environment fallbacks
    return os.environ.get(_REG_NAME) or os.environ.get("DB_PASSWORD") or ""


def require_db_pw() -> str:
    """Like get_db_pw() but raises if the password cannot be resolved."""
    pw = get_db_pw()
    if not pw:
        raise RuntimeError(
            "DB password not found. Set HKCU\\Environment\\DB_PW "
            "(or the DB_PW / DB_PASSWORD environment variable)."
        )
    return pw


# Standard connection kwargs for the fintech database.
DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 5432,
    "user": "postgres",
    "dbname": "fintech",
    "password": get_db_pw(),
}


if __name__ == "__main__":
    pw = get_db_pw()
    print(f"resolved from registry/env: {bool(pw)} (length={len(pw)})")
