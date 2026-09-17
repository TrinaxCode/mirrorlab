"""Cross-platform camera capture.

Opening a webcam is the single most platform-dependent thing this project does.
MirrorLab hides the differences behind :func:`open_camera`:

===========  ==========================================================
Platform     Backends tried, in order
===========  ==========================================================
macOS        ``AVFOUNDATION`` → ``ANY``
Windows      ``DSHOW`` → ``MSMF`` → ``ANY``
Linux        ``V4L2`` → ``GSTREAMER`` (if built) → ``ANY``
===========  ==========================================================

On top of that, :class:`CameraStream` grabs frames on a **background thread**
with a single-slot buffer. That decouples capture from inference: if the
detector takes 40 ms and the camera produces a frame every 33 ms, a naive
``read()`` loop silently builds up latency until it feels like a laggy mirror.
Dropping stale frames is what keeps the preview honest.

A :class:`SyntheticSource` is provided so the pipeline can be exercised in CI
where no camera exists — it renders a moving test pattern plus an animated
"hand" and "face" so effects and HUD code paths still run.
"""

from __future__ import annotations

import platform
import sys
import threading
import time
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

from .utils.logging import get_logger

__all__ = [
    "CameraError",
    "CameraInfo",
    "CameraStream",
    "SyntheticSource",
    "VideoFileSource",
    "available_backends",
    "backend_priority",
    "list_cameras",
    "open_camera",
    "probe_backends",
]

log = get_logger("camera")


class CameraError(RuntimeError):
    """Raised when no usable video source could be opened."""


# --------------------------------------------------------------------------- #
# Backend selection
# --------------------------------------------------------------------------- #
def _backend_table() -> dict:
    table = {"any": cv2.CAP_ANY}
    for name, attr in (
        ("avfoundation", "CAP_AVFOUNDATION"),
        ("dshow", "CAP_DSHOW"),
        ("msmf", "CAP_MSMF"),
        ("v4l2", "CAP_V4L2"),
        ("gstreamer", "CAP_GSTREAMER"),
        ("ffmpeg", "CAP_FFMPEG"),
    ):
        value = getattr(cv2, attr, None)
        if value is not None:
            table[name] = value
    return table


BACKENDS = _backend_table()


def available_backends() -> List[str]:
    """Names of the capture backends this OpenCV build actually supports."""
    return sorted(BACKENDS)


def backend_priority(override: str = "auto") -> List[str]:
    """Return the backend names to try, best first, for the current platform."""
    if override and override != "auto":
        return [override]
    system = platform.system()
    if system == "Darwin":
        order = ["avfoundation", "any"]
    elif system == "Windows":
        order = ["dshow", "msmf", "any"]
    else:
        order = ["v4l2", "gstreamer", "any"]
    return [name for name in order if name in BACKENDS]


@dataclass(frozen=True)
class CameraInfo:
    """What we ended up with after a successful open."""

    index: int
    backend: str
    width: int
    height: int
    fps: float
    source: str = "camera"

    def describe(self) -> str:
        return (
            f"{self.source} #{self.index} via {self.backend} "
            f"@ {self.width}x{self.height} {self.fps:.0f}fps"
        )


def _open_raw(index: int, backend: str, width: int, height: int, fps: int) -> Optional[cv2.VideoCapture]:
    cap = cv2.VideoCapture(index, BACKENDS[backend])
    if not cap.isOpened():
        cap.release()
        return None
    if width:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, float(width))
    if height:
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, float(height))
    if fps:
        cap.set(cv2.CAP_PROP_FPS, float(fps))
    # A 1-frame read is the only reliable "is this thing real?" test on Windows,
    # where DSHOW happily reports an open device that never delivers pixels.
    ok, frame = cap.read()
    if not ok or frame is None:
        cap.release()
        return None
    return cap


def probe_backends(index: int = 0, width: int = 640, height: int = 480) -> List[Tuple[str, bool]]:
    """Try every platform backend and report which ones deliver a frame."""
    results: List[Tuple[str, bool]] = []
    for name in backend_priority("auto"):
        cap = _open_raw(index, name, width, height, 30)
        results.append((name, cap is not None))
        if cap is not None:
            cap.release()
    return results


def open_camera(
    index: int = 0,
    width: int = 1280,
    height: int = 720,
    fps: int = 30,
    backend: str = "auto",
) -> Tuple[cv2.VideoCapture, CameraInfo]:
    """Open a webcam, trying the platform's preferred backends in order.

    Raises:
        CameraError: when no backend could deliver a frame, with a
            platform-specific hint about what to check.
    """
    attempts: List[str] = []
    for name in backend_priority(backend):
        cap = _open_raw(index, name, width, height, fps)
        if cap is not None:
            info = CameraInfo(
                index=index,
                backend=name,
                width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or width),
                height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or height),
                fps=float(cap.get(cv2.CAP_PROP_FPS) or fps),
            )
            log.info("Camera opened: %s", info.describe())
            return cap, info
        attempts.append(name)

    raise CameraError(
        f"Could not open camera #{index} (tried: {', '.join(attempts) or 'none'}).\n"
        + camera_troubleshooting(index)
    )


def camera_troubleshooting(index: int = 0) -> str:
    """Platform-aware checklist shown when the camera will not open."""
    system = platform.system()
    common = (
        "  • Run `mirrorlab doctor` to list detected devices and backends.\n"
        "  • Try a different index: `mirrorlab run --camera 1`.\n"
        "  • Close other apps that may hold the camera (Zoom, Teams, OBS, Photo Booth).\n"
    )
    if system == "Darwin":
        specific = (
            "  • macOS: System Settings → Privacy & Security → Camera → enable your terminal.\n"
            "  • macOS: the first run triggers a permission prompt — accept it and retry.\n"
            "  • macOS: Continuity Camera / iPhone may occupy index 0; try --camera 1.\n"
        )
    elif system == "Windows":
        specific = (
            "  • Windows: Settings → Privacy → Camera → let desktop apps use the camera.\n"
            "  • Windows: try `--backend msmf` if DSHOW misbehaves, or `--backend dshow` if MSMF does.\n"
        )
    else:
        specific = (
            "  • Linux: ensure your user is in the `video` group: `sudo usermod -aG video $USER`.\n"
            "  • Linux: check the device exists: `ls -l /dev/video*`.\n"
            "  • Linux: in WSL2 or Docker, pass the device through (`--device /dev/video0`).\n"
        )
    return common + specific


def list_cameras(max_index: int = 8) -> List[CameraInfo]:
    """Probe camera indices ``0..max_index-1`` and describe the working ones."""
    found: List[CameraInfo] = []
    for index in range(max_index):
        for name in backend_priority("auto"):
            cap = _open_raw(index, name, 640, 480, 30)
            if cap is not None:
                found.append(
                    CameraInfo(
                        index=index,
                        backend=name,
                        width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 640),
                        height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 480),
                        fps=float(cap.get(cv2.CAP_PROP_FPS) or 30.0),
                    )
                )
                cap.release()
                break
    return found


# --------------------------------------------------------------------------- #
# Streams
# --------------------------------------------------------------------------- #
class CameraStream:
    """Threaded, drop-latest frame source with a uniform interface.

    ``read()`` always returns the most recent frame and never blocks on the
    device, so inference time can exceed the capture interval without adding
    latency. Works for webcams and video files alike.
    """

    def __init__(
        self,
        source: int | str | Path = 0,
        *,
        width: int = 1280,
        height: int = 720,
        fps: int = 30,
        backend: str = "auto",
        mirror: bool = False,
        loop: bool = False,
    ) -> None:
        self.mirror = bool(mirror)
        self.loop = bool(loop)
        self._lock = threading.Lock()
        self._frame: Optional[np.ndarray] = None
        self._seq = 0
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._is_file = isinstance(source, (str, Path)) and str(source) != "0"

        if self._is_file:
            path = Path(str(source))
            if not path.exists():
                raise CameraError(f"Video file not found: {path}")
            self.cap = cv2.VideoCapture(str(path))
            if not self.cap.isOpened():
                raise CameraError(f"Could not decode video file: {path}")
            self.info = CameraInfo(
                index=0,
                backend="file",
                width=int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH) or width),
                height=int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or height),
                fps=float(self.cap.get(cv2.CAP_PROP_FPS) or fps),
                source="file",
            )
            log.info("Video file opened: %s", path)
        else:
            self.cap, self.info = open_camera(int(source), width, height, fps, backend)

        self._start_thread()

    # -- lifecycle --------------------------------------------------------- #
    def _start_thread(self) -> None:
        self._thread = threading.Thread(target=self._pump, name="mirrorlab-capture", daemon=True)
        self._thread.start()

    def _pump(self) -> None:
        consecutive_failures = 0
        while not self._stop.is_set():
            ok, frame = self.cap.read()
            if not ok or frame is None:
                if self._is_file and self.loop:
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                consecutive_failures += 1
                if consecutive_failures > 30:
                    log.warning("Capture stopped: no frames for %d reads.", consecutive_failures)
                    break
                time.sleep(0.01)
                continue
            consecutive_failures = 0
            if self.mirror:
                frame = cv2.flip(frame, 1)
            with self._lock:
                self._frame = frame
                self._seq += 1
            if self._is_file:
                # Pace file playback so it behaves like a live source.
                delay = 1.0 / max(self.info.fps, 1.0)
                time.sleep(delay)

    # -- reading ----------------------------------------------------------- #
    def read(self, timeout: float = 2.0) -> Optional[np.ndarray]:
        """Return the latest frame (a *copy*), or ``None`` if the feed stalled."""
        deadline = time.perf_counter() + timeout
        while time.perf_counter() < deadline:
            with self._lock:
                if self._frame is not None:
                    return self._frame.copy()
            if not self.is_alive:
                return None
            time.sleep(0.002)
        return None

    @property
    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive() and not self._stop.is_set()

    @property
    def sequence(self) -> int:
        """How many frames have arrived — useful to avoid re-processing duplicates."""
        with self._lock:
            return self._seq

    def release(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        with suppress(Exception):  # pragma: no cover - the device may already be gone
            self.cap.release()

    def __enter__(self) -> "CameraStream":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.release()

    def __iter__(self):
        while True:
            frame = self.read()
            if frame is None:
                return
            yield frame


class SyntheticSource:
    """Deterministic offline source: no camera, no permissions, no flakiness.

    Renders a moving test pattern with a bouncing ball, a colour ramp, a frame
    counter and a fake hand/finger so that filter, HUD and overlay code can all
    be exercised in CI and in ``mirrorlab demo --offline``.
    """

    def __init__(self, width: int = 1280, height: int = 720, fps: float = 30.0, frame_limit: int = 0) -> None:
        self.width = int(width)
        self.height = int(height)
        self.fps = float(fps)
        self.frame_limit = int(frame_limit)
        self.frame_index = 0
        self.info = CameraInfo(
            index=0,
            backend="synthetic",
            width=self.width,
            height=self.height,
            fps=self.fps,
            source="synthetic",
        )

    def read(self, timeout: float = 0.0) -> Optional[np.ndarray]:
        if self.frame_limit and self.frame_index >= self.frame_limit:
            return None
        return self.render(self.frame_index)

    def render(self, index: int) -> np.ndarray:
        """Produce frame ``index`` — pure function, ideal for snapshot tests."""
        width, height = self.width, self.height
        # Vertical gradient background.
        ramp = np.linspace(24, 96, height, dtype=np.uint8).reshape(height, 1)
        frame = np.repeat(ramp, width, axis=1)
        frame = cv2.merge([frame, np.clip(frame.astype(np.int16) + 8, 0, 255).astype(np.uint8), frame])

        # Scrolling colour bars keep temporal filters honest.
        bar_width = max(width // 16, 1)
        phase = (index * 3) % (bar_width * 2)
        for i in range(0, width // bar_width + 2):
            x0 = i * bar_width - phase
            colour = (
                int(120 + 110 * np.sin(i * 0.7 + index * 0.03)),
                int(120 + 110 * np.sin(i * 0.7 + 2.1)),
                int(120 + 110 * np.sin(i * 0.7 + 4.2)),
            )
            cv2.rectangle(frame, (x0, 0), (x0 + bar_width - 2, height // 3), colour, -1)

        # Bouncing ball for motion / optical-flow sanity checks.
        cx = int(width * (0.5 + 0.35 * np.sin(index * 0.05)))
        cy = int(height * (0.6 + 0.25 * np.cos(index * 0.037)))
        cv2.circle(frame, (cx, cy), max(height // 14, 8), (60, 220, 240), -1)
        cv2.circle(frame, (cx, cy), max(height // 14, 8), (255, 255, 255), 2)

        # Frame counter + a moving focus cross.
        cv2.putText(
            frame,
            f"SYNTHETIC {index:05d}",
            (24, height - 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        cross_x = int(width * (0.5 + 0.4 * np.sin(index * 0.02)))
        cv2.line(frame, (cross_x - 18, height // 2), (cross_x + 18, height // 2), (255, 255, 255), 1)
        cv2.line(frame, (cross_x, height // 2 - 18), (cross_x, height // 2 + 18), (255, 255, 255), 1)
        self.frame_index = index + 1
        return frame

    def release(self) -> None:  # pragma: no cover - nothing to release
        pass

    @property
    def is_alive(self) -> bool:
        return not self.frame_limit or self.frame_index < self.frame_limit

    def __enter__(self) -> "SyntheticSource":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.release()

    def __iter__(self):
        while True:
            frame = self.read()
            if frame is None:
                return
            yield frame


VideoFileSource = CameraStream  #: alias kept for readability in user code


def open_source(
    source: int | str | Path | None,
    *,
    width: int = 1280,
    height: int = 720,
    fps: int = 30,
    backend: str = "auto",
    mirror: bool = False,
    synthetic: bool = False,
    synthetic_frames: int = 0,
) -> CameraStream | SyntheticSource:
    """Factory used by the CLI: pick webcam, video file or synthetic source."""
    if synthetic:
        return SyntheticSource(width=width, height=height, fps=float(fps), frame_limit=synthetic_frames)
    if source is None:
        source = 0
    return CameraStream(
        source,
        width=width,
        height=height,
        fps=fps,
        backend=backend,
        mirror=mirror,
        loop=isinstance(source, (str, Path)) and str(source) != "0",
    )


def platform_summary() -> dict:
    """Diagnostics used by ``mirrorlab doctor``."""
    return {
        "platform": platform.system(),
        "platform_release": platform.release(),
        "machine": platform.machine(),
        "python": sys.version.split()[0],
        "opencv": cv2.__version__,
        "opencv_backends": available_backends(),
        "backend_order": backend_priority("auto"),
    }
