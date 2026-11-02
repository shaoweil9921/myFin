"""Thin shim: re-export the canonical workspace-level db_pw helpers.

The canonical implementation lives at <workspace>/db_pw.py so that every
project (finviz/, ibd/, Discord/myTrading/, root scripts) resolves the
password the same way instead of each copy-pasting a literal.
"""
import os
import sys

# Walk up from this file until we find the canonical db_pw.py
_d = os.path.dirname(os.path.abspath(__file__))
while True:
    if os.path.exists(os.path.join(_d, "db_pw.py")):
        if _d not in sys.path:
            sys.path.insert(0, _d)
        break
    _nd = os.path.dirname(_d)
    if _nd == _d:
        break
    _d = _nd

from db_pw import get_db_pw, require_db_pw, DB_CONFIG  # noqa: E402,F401
