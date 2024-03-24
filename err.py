from __future__ import annotations
import subprocess
import sys
import traceback


def log_exception(e: Exception) -> None:
    print(str(e), file=sys.stderr)


def alert_exception(e: Exception) -> None:
    log_exception(e)
    print(traceback.format_exc())
    e_str = str(e).replace("'", "'\\''")
    subprocess.call(f"alert 'light: {e_str}'", shell=True)
