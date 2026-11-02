"""The MirrorLab Studio desktop app: a window around the same virtual camera the CLI runs.

``tkinter`` is imported lazily by :func:`main` so that ``import mirrorlab.desktop``
works on a Python without Tk (a headless server, a minimal Linux install).
"""

from __future__ import annotations

import sys
from typing import List, Optional

from .prefs import DesktopPrefs
from .runner import StudioRunner

__all__ = ["DesktopPrefs", "StudioRunner", "main"]


def main(argv: Optional[List[str]] = None) -> int:
    """Open the MirrorLab Studio window and block until it is closed."""
    args = list(sys.argv[1:] if argv is None else argv)
    if "--self-test" in args:
        index = args.index("--self-test")
        if index + 1 >= len(args):
            print("usage: --self-test REPORT.json", file=sys.stderr)
            return 2
        from .selftest import run

        return run(args[index + 1])
    try:
        from .window import main as run_window
    except ImportError as exc:  # no tkinter on this Python
        from .strings import STRINGS, detect_language

        language = detect_language()
        print(f"{STRINGS[language]['error.tk']}\n({exc})", file=sys.stderr)
        return 1
    return run_window(args)
