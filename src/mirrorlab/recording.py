"""Capturing output: snapshots, video recording and GIF export.

Recording must never stall the preview. Writing an MP4 is fast, but flushing a
GIF or a slow disk is not, so the writer runs on a daemon thread fed by a
bounded queue: if the encoder falls behind, frames are **dropped** rather than
queued. A recording with a skipped frame is fine; a preview that freezes is not.
"""

from __future__ import annotations

import queue
import threading
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

from .utils.logging import get_logger

__all__ = ["Recorder", "SaveResult", "save_gif", "save_snapshot", "snapshot_path"]

log = get_logger("recording")


@dataclass
class SaveResult:
    """Outcome of a save operation."""

    path: Path
    bytes: int
    width: int
    height: int
    frames: int = 1

    def describe(self) -> str:
        size = self.bytes / 1024.0
        unit = "KB" if size < 1024 else "MB"
        value = size if size < 1024 else size / 1024.0
        return f"{self.path.name} · {self.width}×{self.height} · {value:.1f} {unit}"


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def snapshot_path(directory: str | Path, extension: str = "png", prefix: str = "mirrorlab") -> Path:
    """Build a collision-free output path inside ``directory``."""
    folder = Path(directory)
    folder.mkdir(parents=True, exist_ok=True)
    candidate = folder / f"{prefix}_{_timestamp()}.{extension.lstrip('.')}"
    counter = 1
    while candidate.exists():
        candidate = folder / f"{prefix}_{_timestamp()}_{counter}.{extension.lstrip('.')}"
        counter += 1
    return candidate


def save_snapshot(
    frame: np.ndarray,
    directory: str | Path = "captures",
    extension: str = "png",
    jpeg_quality: int = 95,
) -> SaveResult:
    """Write a single frame to disk and return what was written."""
    path = snapshot_path(directory, extension)
    params: List[int] = []
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        params = [cv2.IMWRITE_JPEG_QUALITY, int(jpeg_quality)]
    elif suffix == ".webp":
        params = [cv2.IMWRITE_WEBP_QUALITY, int(jpeg_quality)]
    if not cv2.imwrite(str(path), frame, params):
        raise OSError(
            f"Could not write {path}. Check that the directory exists and is writable, "
            f"and that the extension {suffix!r} is supported by your OpenCV build."
        )
    return SaveResult(
        path=path,
        bytes=path.stat().st_size,
        width=int(frame.shape[1]),
        height=int(frame.shape[0]),
    )


def save_gif(
    frames: List[np.ndarray],
    path: str | Path,
    fps: float = 12.0,
    max_width: int = 640,
) -> SaveResult:
    """Encode frames into a looping GIF.

    GIFs are for sharing: 12 fps at 640 px is the sweet spot where a webcam clip
    stays legible and lands under a few megabytes.
    """
    if not frames:
        raise ValueError("save_gif needs at least one frame")
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("GIF export needs Pillow. Install it with `pip install pillow`.") from exc

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    images: List["Image.Image"] = []
    for frame in frames:
        height, width = frame.shape[:2]
        if width > max_width:
            scale = max_width / width
            frame = cv2.resize(frame, (max_width, max(1, int(height * scale))), interpolation=cv2.INTER_AREA)
        images.append(Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))

    duration = round(1000.0 / max(fps, 1.0))
    images[0].save(
        target,
        save_all=True,
        append_images=images[1:],
        duration=duration,
        loop=0,
        optimize=True,
    )
    return SaveResult(
        path=target,
        bytes=target.stat().st_size,
        width=images[0].width,
        height=images[0].height,
        frames=len(images),
    )


class Recorder:
    """Threaded video writer with a bounded, drop-oldest queue.

    Args:
        path: Output file. The container is inferred from the extension.
        fps: Playback frame rate.
        size: ``(width, height)``; frames are resized if they differ.
        codec: FourCC. ``mp4v`` is the most portable; ``avc1`` gives smaller
            files where the OpenCV build supports H.264 encoding.
        max_queue: How many frames may wait before the oldest is dropped.
        gif: Also buffer frames for a GIF export on :meth:`stop`.

    Example:
        >>> recorder = Recorder("clip.mp4", fps=30, size=(1280, 720))  # doctest: +SKIP
        >>> recorder.start()                                          # doctest: +SKIP
        >>> recorder.write(frame)                                     # doctest: +SKIP
        >>> result = recorder.stop()                                  # doctest: +SKIP
    """

    def __init__(
        self,
        path: str | Path,
        fps: float = 30.0,
        size: Tuple[int, int] = (1280, 720),
        codec: str = "mp4v",
        max_queue: int = 4,
        gif: bool = False,
        gif_fps: float = 12.0,
        gif_max_frames: int = 240,
        audio: bool = False,
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fps = float(max(1.0, fps))
        self.size = (int(size[0]), int(size[1]))
        self.codec = codec
        self.gif = bool(gif)
        self.gif_fps = float(gif_fps)
        self.gif_max_frames = int(gif_max_frames)

        self.frames_written = 0
        self.frames_dropped = 0
        self._queue: "queue.Queue[Optional[np.ndarray]]" = queue.Queue(maxsize=max(1, int(max_queue)))
        self._thread: Optional[threading.Thread] = None
        self._writer: Optional[cv2.VideoWriter] = None
        self._gif_frames: List[np.ndarray] = []
        self._running = False
        self._failed = False

    # ------------------------------------------------------------------ #
    def start(self) -> "Recorder":
        """Open the writer and start the encoder thread."""
        fourcc = cv2.VideoWriter_fourcc(*self.codec)  # type: ignore[attr-defined]
        writer = cv2.VideoWriter(str(self.path), fourcc, self.fps, self.size)
        if not writer.isOpened():
            # Fall back to mp4v, then to the first codec that opens.
            for fallback in ("mp4v", "XVID", "MJPG"):
                if fallback == self.codec:
                    continue
                writer = cv2.VideoWriter(
                    str(self.path), cv2.VideoWriter_fourcc(*fallback), self.fps, self.size  # type: ignore[attr-defined]
                )
                if writer.isOpened():
                    log.warning("Codec %s unavailable; using %s instead.", self.codec, fallback)
                    break
        if not writer.isOpened():
            self._failed = True
            raise OSError(
                f"Could not open a video writer for {self.path}.\n"
                f"  Try a different container or codec: --record-codec mp4v (or XVID/MJPG with .avi)."
            )
        self._writer = writer
        self._running = True
        self._thread = threading.Thread(target=self._run, name="mirrorlab-recorder", daemon=True)
        self._thread.start()
        log.info("Recording to %s (%dx%d @ %.0f fps, %s)", self.path, *self.size, self.fps, self.codec)
        return self

    def _run(self) -> None:
        while True:
            frame = self._queue.get()
            try:
                if frame is None:
                    return
                if (frame.shape[1], frame.shape[0]) != self.size:
                    frame = cv2.resize(frame, self.size, interpolation=cv2.INTER_AREA)
                if self._writer is not None:
                    self._writer.write(frame)
                self.frames_written += 1
            except Exception as exc:  # pragma: no cover - encoder failure
                log.error("Recorder error: %s", exc)
                self._failed = True
                return
            finally:
                self._queue.task_done()

    # ------------------------------------------------------------------ #
    def write(self, frame: np.ndarray) -> bool:
        """Queue a frame for encoding. Returns ``False`` if it was dropped."""
        if not self._running:
            return False
        if self.gif and len(self._gif_frames) < self.gif_max_frames:
            # Buffer every Nth frame so the GIF plays at its own, lower fps.
            stride = max(1, round(self.fps / max(self.gif_fps, 1.0)))
            if self.frames_written % stride == 0:
                self._gif_frames.append(frame.copy())
        try:
            self._queue.put_nowait(frame)
            return True
        except queue.Full:
            # Drop the oldest pending frame to keep latency flat.
            try:
                self._queue.get_nowait()
                self._queue.task_done()
                self.frames_dropped += 1
            except queue.Empty:  # pragma: no cover - race
                pass
            try:
                self._queue.put_nowait(frame)
            except queue.Full:  # pragma: no cover - race
                self.frames_dropped += 1
                return False
            return True

    def stop(self, export_gif: bool = True) -> SaveResult:
        """Flush, close the writer and optionally export a GIF."""
        if not self._running:
            raise RuntimeError("Recorder is not running")
        self._running = False
        self._queue.put(None)
        if self._thread is not None:
            self._thread.join(timeout=10.0)
        if self._writer is not None:
            self._writer.release()
            self._writer = None

        gif_result: Optional[SaveResult] = None
        if self.gif and export_gif and self._gif_frames:
            try:
                gif_result = save_gif(self._gif_frames, self.path.with_suffix(".gif"), fps=self.gif_fps)
            except Exception as exc:  # pragma: no cover - optional dependency
                log.warning("GIF export failed: %s", exc)

        if self._failed:
            log.error("Recording failed; %s may be incomplete.", self.path)
        else:
            log.info(
                "Saved %s (%d frames, %d dropped)%s",
                self.path,
                self.frames_written,
                self.frames_dropped,
                f" + {gif_result.path.name}" if gif_result else "",
            )

        final_path = gif_result.path if (gif_result and not self.path.exists()) else self.path
        size = final_path.stat().st_size if final_path.exists() else 0
        return SaveResult(
            path=final_path,
            bytes=size,
            width=self.size[0],
            height=self.size[1],
            frames=self.frames_written,
        )

    # ------------------------------------------------------------------ #
    @property
    def running(self) -> bool:
        return self._running

    @property
    def duration(self) -> float:
        return self.frames_written / self.fps if self.fps else 0.0

    def __enter__(self) -> "Recorder":
        return self.start()

    def __exit__(self, *exc: object) -> None:
        if self._running:
            with suppress(Exception):  # pragma: no cover - never mask the real error
                self.stop()
