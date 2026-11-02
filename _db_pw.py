"""Thin shim: re-export the canonical workspace-level db_pw helpers.

The canonical implementation lives at <workspace>/db_pw.py. This shim keeps
existing `from _db_pw import DB_CONFIG` imports working without every
project carrying its own copy of the resolver.
"""
import os
import sys

_d = os.path.dirname(os.path.abspath(__file__))
if _d not in sys.path:
    sys.path.insert(0, _d)

from db_pw import get_db_pw, require_db_pw, DB_CONFIG  # noqa: E402,F401
