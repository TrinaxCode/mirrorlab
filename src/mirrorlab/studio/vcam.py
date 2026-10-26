"""Where finished frames go: a virtual camera, nothing, or memory.

Publishing a frame as a system camera needs an operating-system component that
Python cannot create by itself:

========  ==============================================================
Linux     the ``v4l2loopback`` kernel module (creates a ``/dev/videoN`` device)
macOS     OBS Studio's virtual camera (activated once from inside OBS)
Windows   OBS Studio's virtual camera, or Unity Capture
========  ==============================================================

The Python side is done by `pyvirtualcam <https://github.com/letmaik/pyvirtualcam>`_,
which is **GPL-2.0**. MirrorLab is MIT, so pyvirtualcam is never a hard
dependency: it lives behind the ``vcam`` extra, is imported lazily, and nothing
in this repository copies or vendors its code. Everything else in the studio
works without it, using :class:`NullSink` or :class:`MemorySink`.

:func:`probe` answers "is this machine ready?" without opening any device, and
returns the exact commands to fix whatever is missing.
"""

from __future__ import annotations

import os
import platform
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Protocol

import numpy as np

from ..utils.logging import get_logger

__all__ = [
    "FrameSink",
    "MemorySink",
    "NullSink",
    "OutputError",
    "VCamStatus",
    "VirtualCameraSink",
    "open_sink",
    "probe",
]

log = get_logger("studio.vcam")


class OutputError(RuntimeError):
    """The output could not be opened. The message says how to fix it."""


class FrameSink(Protocol):
    """Anything that can receive finished BGR frames."""

    device: str

    def open(self, width: int, height: int, fps: int) -> None: ...

    def send(self, frame_bgr: np.ndarray) -> None: ...

    def close(self) -> None: ...


class NullSink:
    """Discards frames. Used for benchmarks, tests and ``--output none``."""

    device = "none"

    def __init__(self) -> None:
        self.frames = 0

    def open(self, width: int, height: int, fps: int) -> None:
        self.frames = 0

    def send(self, frame_bgr: np.ndarray) -> None:
        self.frames += 1

    def close(self) -> None:
        pass


class MemorySink:
    """Keeps the most recent frames in memory. Used by tests."""

    device = "memory"

    def __init__(self, keep: int = 8) -> None:
        self.keep = int(keep)
        self.frames: List[np.ndarray] = []
        self.count = 0
        self.size = (0, 0, 0)

    def open(self, width: int, height: int, fps: int) -> None:
        self.size = (width, height, fps)

    def send(self, frame_bgr: np.ndarray) -> None:
        self.count += 1
        self.frames.append(frame_bgr.copy())
        del self.frames[: -self.keep]

    def close(self) -> None:
        pass


class VirtualCameraSink:
    """Publishes frames to a system virtual camera through pyvirtualcam.

    Args:
        device: Explicit device (``/dev/video10`` on Linux, a camera name elsewhere). ``None`` picks the first.
        backend: pyvirtualcam backend (``v4l2loopback``, ``obs``, ``unitycapture``). ``None`` picks automatically.
    """

    def __init__(self, device: Optional[str] = None, backend: Optional[str] = None) -> None:
        self._requested_device = device
        self._backend = backend
        self._camera = None
        self.device = device or ""

    def open(self, width: int, height: int, fps: int) -> None:
        try:
            import pyvirtualcam
        except ImportError as exc:
            raise OutputError(
                "The virtual camera needs pyvirtualcam, which is not installed.\n"
                '  Install it with: pip install "mirrorlab[vcam]"\n'
                "  (pyvirtualcam is GPL-2.0, so MirrorLab keeps it optional.)\n"
                "  Run `mirrorlab doctor` to check the rest of the setup."
            ) from exc
        try:
            self._camera = pyvirtualcam.Camera(
                width=width,
                height=height,
                fps=fps,
                fmt=pyvirtualcam.PixelFormat.BGR,
                device=self._requested_device,
                backend=self._backend,
            )
        except Exception as exc:
            raise OutputError(_explain_open_failure(exc)) from exc
        self.device = str(getattr(self._camera, "device", self._requested_device or "virtual camera"))
        log.info("Virtual camera open: %s (%dx%d @ %d fps)", self.device, width, height, fps)

    def send(self, frame_bgr: np.ndarray) -> None:
        if self._camera is None:
            raise OutputError("send() called before open()")
        self._camera.send(frame_bgr)

    def close(self) -> None:
        camera, self._camera = self._camera, None
        if camera is not None:
            try:
                camera.close()
            except Exception as exc:  # pragma: no cover - device already gone
                log.debug("virtual camera close failed: %s", exc)


# --------------------------------------------------------------------------- #
# Diagnosis
# --------------------------------------------------------------------------- #
@dataclass
class VCamStatus:
    """Result of :func:`probe`."""

    ready: bool
    platform: str
    pyvirtualcam: bool
    backend: str = ""
    details: List[str] = field(default_factory=list)
    fixes: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "ready": self.ready,
            "platform": self.platform,
            "pyvirtualcam": self.pyvirtualcam,
            "backend": self.backend,
            "details": list(self.details),
            "fixes": list(self.fixes),
        }


def _loopback_devices() -> List[str]:
    """``/dev/videoN`` devices that are v4l2loopback (Linux only)."""
    found: List[str] = []
    root = Path("/sys/class/video4linux")
    if not root.is_dir():
        return found
    for entry in sorted(root.iterdir()):
        try:
            name = (entry / "name").read_text(encoding="utf-8", errors="replace").strip().lower()
        except OSError:
            continue
        if "loopback" in name or "dummy" in name or "virtual" in name:
            found.append(f"/dev/{entry.name}")
    return found


def _obs_installed() -> bool:
    system = platform.system()
    if system == "Darwin":
        return Path("/Applications/OBS.app").exists()
    if system == "Windows":
        candidates = [
            Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "obs-studio",
            Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")) / "obs-studio",
        ]
        return any(path.exists() for path in candidates)
    return shutil.which("obs") is not None


def probe() -> VCamStatus:
    """Check, without opening a device, whether a virtual camera can be published."""
    import importlib.util

    system = platform.system()
    has_module = importlib.util.find_spec("pyvirtualcam") is not None
    status = VCamStatus(ready=False, platform=system, pyvirtualcam=has_module)

    if not has_module:
        status.fixes.append('pip install "mirrorlab[vcam]"')

    if system == "Linux":
        status.backend = "v4l2loopback"
        devices = _loopback_devices()
        if devices:
            status.details.append("loopback device(s): " + ", ".join(devices))
        else:
            status.details.append("no v4l2loopback device found")
            status.fixes += [
                "sudo apt install v4l2loopback-dkms   (Debian/Ubuntu; other distros ship it too)",
                'sudo modprobe v4l2loopback devices=1 video_nr=10 card_label="MirrorLab" exclusive_caps=1',
            ]
        status.ready = has_module and bool(devices)
    elif system in {"Darwin", "Windows"}:
        status.backend = "obs"
        if _obs_installed():
            status.details.append("OBS Studio found")
            if system == "Darwin":
                status.details.append(
                    "one-time step: open OBS, click 'Start Virtual Camera', then 'Stop Virtual Camera', and quit OBS"
                )
        else:
            status.details.append("OBS Studio not found (its virtual camera is what apps will see)")
            status.fixes.append("Install OBS Studio from https://obsproject.com, then open it once")
        status.ready = has_module and _obs_installed()
    else:  # pragma: no cover - unsupported platform
        status.details.append(f"unsupported platform: {system}")
    return status


def _explain_open_failure(exc: Exception) -> str:
    text = str(exc)
    system = platform.system()
    lines = [f"Could not open the virtual camera: {text}"]
    if system == "Linux":
        lines += [
            "  Linux needs a v4l2loopback device. Create one with:",
            '    sudo modprobe v4l2loopback devices=1 video_nr=10 card_label="MirrorLab" exclusive_caps=1',
            "  If the module is missing: sudo apt install v4l2loopback-dkms",
        ]
    elif system == "Darwin":
        lines += [
            "  macOS needs OBS 30+ with its virtual camera activated once:",
            "    open OBS -> Start Virtual Camera -> Stop Virtual Camera -> quit OBS",
            "  If OBS is running, close it: only one program can own the camera.",
        ]
    elif system == "Windows":
        lines += [
            "  Windows needs OBS Studio installed (it provides the 'OBS Virtual Camera').",
            "  Close OBS if it is running its own virtual camera: there is only one instance.",
        ]
    lines.append("  Run `mirrorlab doctor` for a full check.")
    return "\n".join(lines)


def open_sink(kind: str, device: Optional[str] = None) -> FrameSink:
    """Build a sink from a CLI name: ``vcam``, ``none`` or ``memory``."""
    kind = kind.lower()
    if kind in {"vcam", "virtual", "auto"}:
        return VirtualCameraSink(device=device)
    if kind in {"none", "null"}:
        return NullSink()
    if kind == "memory":
        return MemorySink()
    raise ValueError(f"unknown output {kind!r}; choose vcam, none or memory")
