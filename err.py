from __future__ import annotations
import sys


def log_exception(e: Exception) -> None:
    print(str(e).replace("'", "'\\''"), file=sys.stderr)
