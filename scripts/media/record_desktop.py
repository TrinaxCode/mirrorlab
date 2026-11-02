"""Record the desktop app for the README: screenshots and an animated GIF.

    python scripts/media/record_desktop.py                       # drawn scene, Spanish
    python scripts/media/record_desktop.py --lang en --out docs/media
    python scripts/media/record_desktop.py --camera 0            # your own webcam

By default the app is fed a drawn scene, so the pictures contain nobody's face.
Pass ``--camera`` to record with a real camera instead (the result then shows
whoever is in front of it, so look before you commit it).

Needs a display. On Linux it captures with ImageMagick's ``import`` (X11 or
Xvfb); on macOS and Windows it uses Pillow's ImageGrab. Preferences are written
to a throwaway directory, never to your real configuration.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SIZE = (1180, 720)
FRAME_MS = 200  # 5 frames per second keeps the GIF small and still smooth enough


def grab(root, window_id: int):  # type: ignore[no-untyped-def]
    """One screenshot of the app window as a Pillow image."""
    from PIL import Image, ImageGrab

    root.update_idletasks()
    if sys.platform.startswith("linux"):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as handle:
            path = handle.name
        try:
            subprocess.run(["import", "-window", str(window_id), path], check=True, capture_output=True)
            return Image.open(path).convert("RGB").copy()
        finally:
            Path(path).unlink(missing_ok=True)
    x, y = root.winfo_rootx(), root.winfo_rooty()
    return ImageGrab.grab(bbox=(x, y, x + root.winfo_width(), y + root.winfo_height())).convert("RGB")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--lang", choices=("es", "en"), default="es")
    parser.add_argument("--out", default=str(ROOT / "docs" / "media"))
    parser.add_argument("--source", default=str(ROOT / "scripts" / "media" / "scene.png"))
    parser.add_argument("--camera", type=int, help="record with this webcam instead of the drawn scene")
    parser.add_argument("--background", default="off", choices=("off", "blur", "green", "black"))
    args = parser.parse_args()

    config_home = tempfile.mkdtemp(prefix="mirrorlab-media-")
    os.environ["XDG_CONFIG_HOME"] = config_home
    os.environ["APPDATA"] = config_home
    os.environ.setdefault("MIRRORLAB_MODELS", str(Path.home() / ".cache" / "mirrorlab" / "models"))

    import tkinter as tk

    from PIL import Image

    from mirrorlab.desktop.prefs import DesktopPrefs
    from mirrorlab.desktop.window import MirrorLabWindow

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    prefs = DesktopPrefs(
        language=args.lang, background=args.background, output="none", auto_frame=False, studio_light=False
    )
    root = tk.Tk()
    window = MirrorLabWindow(
        root,
        prefs=prefs,
        source=args.camera if args.camera is not None else args.source,
        snapshot_dir=Path(config_home) / "captures",
    )
    root.geometry(f"{SIZE[0]}x{SIZE[1]}+40+40")
    root.update()

    frames: list = []
    stills: dict = {}
    pending: list = []  # (path, process) for Linux captures that run in the background
    scratch = Path(tempfile.mkdtemp(prefix="mirrorlab-frames-"))

    def capture() -> None:
        # `import` takes a moment to start, so on Linux each frame is its own background
        # process: the loop keeps its 200 ms rhythm instead of waiting for every grab.
        if sys.platform.startswith("linux"):
            path = scratch / f"{len(pending):04d}.png"
            pending.append((path, subprocess.Popen(["import", "-window", str(root.winfo_id()), str(path)])))
        else:
            frames.append(grab(root, root.winfo_id()))
        root.after(FRAME_MS, capture)

    def still(name: str) -> None:
        stills[name] = grab(root, root.winfo_id())

    # The story the GIF tells, in milliseconds from the first frame on screen
    # (models can take a while to load, so the clock starts when there is a picture).
    story = [
        (1500, lambda: still("live")),
        (2000, lambda: window.react("thumbs_up")),
        (4500, lambda: window.react("love")),
        (7500, window.toggle_privacy),
        (8800, lambda: still("covered")),
        (11500, window.toggle_privacy),
        (14000, root.quit),
    ]

    def wait_for_picture() -> None:
        if window.runner.has_frame:
            for delay, action in story:
                root.after(delay, action)
        else:
            root.after(100, wait_for_picture)

    root.after(600, lambda: still("idle"))
    root.after(900, window.start_camera)
    root.after(1000, wait_for_picture)
    root.after(0, capture)
    root.mainloop()

    for path, process in pending:
        process.wait()
        frames.append(Image.open(path).convert("RGB").copy())
    shutil.rmtree(scratch, ignore_errors=True)
    window.runner.stop(timeout=5)
    root.destroy()
    shutil.rmtree(config_home, ignore_errors=True)

    names = {"idle": "desktop-idle", "live": "desktop-live", "covered": "desktop-covered"}
    for key, image in stills.items():
        image.save(out / f"{names[key]}-{args.lang}.png", optimize=True)

    # Drop the quiet start-up frames, shrink, and write a looping GIF.
    start = next((i for i, f in enumerate(frames) if i >= 4), 0)
    chosen = [f.resize((900, round(900 * f.height / f.width)), Image.LANCZOS) for f in frames[start:]]
    palette = [
        f.quantize(colors=128, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE) for f in chosen
    ]
    palette[0].save(
        out / f"desktop-demo-{args.lang}.gif",
        save_all=True,
        append_images=palette[1:],
        duration=FRAME_MS,
        loop=0,
        optimize=True,
        disposal=1,
    )
    print(f"wrote {len(stills)} screenshots and a {len(chosen)}-frame GIF to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
