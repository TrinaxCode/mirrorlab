"""``MirrorLab --self-test FILE``: prove an installed or frozen build works, with no window.

A packaged app can be missing a native library, a data file or a hidden import
and still start fine, so the release pipeline runs this against the finished
bundle on every operating system. It writes a JSON report to ``FILE`` (a
windowed app has no console to print to) and returns 0 only if everything the
studio needs was found and it processed frames end to end.
"""

from __future__ import annotations

import importlib
import json
import platform
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List

from ..version import __version__

__all__ = ["run"]

FRAMES = 20


def run(report_path: str) -> int:
    report: Dict[str, Any] = {
        "version": __version__,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "frozen": bool(getattr(sys, "frozen", False)),
        "checks": {},
    }
    problems: List[str] = []

    def check(name: str, probe) -> None:  # type: ignore[no-untyped-def]
        try:
            report["checks"][name] = probe()
        except Exception as exc:
            report["checks"][name] = f"FAILED: {type(exc).__name__}: {exc}"
            problems.append(name)
            report.setdefault("traces", {})[name] = traceback.format_exc(limit=6)

    for module in ("tkinter", "cv2", "numpy", "mediapipe"):
        check(f"import {module}", lambda m=module: getattr(importlib.import_module(m), "__version__", "ok"))

    def icon() -> str:
        path = Path(__file__).resolve().parent / "assets" / "icon.png"
        if not path.is_file():
            raise FileNotFoundError(path)
        return str(path.name)

    check("window icon", icon)

    def pipeline() -> str:
        from ..config import Config
        from ..studio.session import StudioSession
        from ..studio.settings import StudioSettings
        from ..studio.vcam import NullSink

        settings = StudioSettings.from_mapping(
            {"width": 640, "height": 360, "background": "blur", "auto_frame": True, "studio_light": True}
        )
        session = StudioSession(
            settings, Config.load(overrides={"headless": True}), sink=NullSink(), synthetic=True
        )
        result = session.run(max_frames=FRAMES)
        if result.frames < FRAMES:
            raise RuntimeError(f"only {result.frames} of {FRAMES} frames were produced")
        if result.fail_closed_frames:
            raise RuntimeError("person segmentation was unavailable, so frames were blurred whole")
        return f"{result.frames} frames, {result.fps:.1f} fps"

    check("studio pipeline", pipeline)

    def vcam() -> str:
        from ..studio.vcam import probe

        status = probe()
        return "ready" if status.ready else "not ready (" + "; ".join(status.fixes[:1]) + ")"

    check("virtual camera", vcam)  # informational: CI runners have no virtual camera

    report["ok"] = not problems
    report["failed"] = problems
    try:
        Path(report_path).write_text(json.dumps(report, indent=2), encoding="utf-8")
    except OSError as exc:
        print(f"could not write {report_path}: {exc}", file=sys.stderr)
        return 1
    return 0 if report["ok"] else 1
