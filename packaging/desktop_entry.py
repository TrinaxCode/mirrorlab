"""Entry point of the frozen desktop app (PyInstaller).

Kept outside the package so the spec has a plain script to freeze; all behaviour
lives in ``mirrorlab.desktop``.
"""

import sys

from mirrorlab.desktop import main

if __name__ == "__main__":
    sys.exit(main())
