"""Start the packaged app, wait for its first frame, then close it.

    python packaging/gui_smoke.py dist/MirrorLab/MirrorLab[.exe]

Runs with the built-in test pattern and no virtual camera, so it needs a display
but no webcam. Exit code 0 means a window opened and the studio pipeline put a
frame in it; anything else prints the app's own output to help debug the bundle.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import time
from pathlib import Path

TIMEOUT_SECONDS = 150


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    exe = Path(sys.argv[1])
    with tempfile.TemporaryDirectory() as folder:
        ready = Path(folder) / "ready"
        log = Path(folder) / "output.log"
        with log.open("wb") as sink:
            process = subprocess.Popen(
                [
                    str(exe),
                    "--synthetic",
                    "--output",
                    "none",
                    "--autostart",
                    "--geometry",
                    "1120x700",
                    "--ready-file",
                    str(ready),
                ],
                stdout=sink,
                stderr=subprocess.STDOUT,
            )
            deadline = time.monotonic() + TIMEOUT_SECONDS
            try:
                while time.monotonic() < deadline:
                    if ready.exists():
                        print("ok: the window showed its first frame")
                        return 0
                    if process.poll() is not None:
                        print(f"the app exited early with code {process.returncode}")
                        break
                    time.sleep(0.5)
                else:
                    print(f"no frame after {TIMEOUT_SECONDS} s")
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(10)
                    except subprocess.TimeoutExpired:
                        process.kill()
        print("--- app output ---")
        print(log.read_text(errors="replace")[-4000:])
    return 1


if __name__ == "__main__":
    sys.exit(main())
