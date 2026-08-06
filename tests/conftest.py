# conftest.py
"""Isolate every test from the real ~/.tokstat directory and the live legacy
OpenUsage/tokentop databases.

config.py reads TOKSTAT_DIR / TOKSTAT_SYNC_LEGACY from the environment at import
time, so these must be set before any `tokstat` module is imported (conftest is
imported by pytest before test modules).
"""
import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="tokstat-test-")
os.environ["TOKSTAT_DIR"] = _TMP
os.environ["TOKSTAT_SYNC_LEGACY"] = "0"
