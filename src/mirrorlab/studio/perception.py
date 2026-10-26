"""Run perception off the video path.

Face and hand detection are the slowest, spikiest stages: hand detection in
particular costs ~100 ms on a laptop CPU when no hand is being tracked, because
MediaPipe re-runs its palm detector on every frame until it finds one. Run
inline, that turns a 30 fps stream into one with a visible hitch every frame.

:class:`AsyncPerception` moves the engine to a worker thread:

* the video path calls :meth:`process`, which hands over the newest frame and
  returns *immediately* with the latest finished result;
* the worker always processes the newest frame it has been given and skips any
  it missed (drop-latest), so it can never fall further and further behind;
* a result is flagged ``fresh`` exactly once, so a consumer that counts frames
  (the gesture vote window) is not fed the same detection thirty times.

The price is that detections are one to a few frames old. For framing, light and
gestures that is invisible; the person mask, which must line up with the pixels,
is **not** produced here and stays on the video path.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, List, Optional

import numpy as np

from ..utils.logging import get_logger

__all__ = ["AsyncPerception", "Snapshot"]

log = get_logger("studio.perception")

#: A result older than this is treated as missing.
STALE_AFTER_MS = 1500.0


@dataclass
class Snapshot:
    """What the video path sees of the latest perception result."""

    faces: List[Any] = field(default_factory=list)
    gestures: List[Any] = field(default_factory=list)
    dynamic: List[Any] = field(default_factory=list)
    fresh: bool = False
    age_ms: float = 0.0
    inference_ms: float = 0.0


class AsyncPerception:
    """Wraps a perception engine so it runs on its own thread.

    Args:
        engine: Anything with ``process(frame, frame_index, timestamp_ms)`` and ``close()``.
        max_fps: Upper bound on detections per second. Gestures and framing do not
            need more than ~15 Hz, and an uncapped worker would compete with the
            video path for CPU. ``0`` removes the cap.
    """

    def __init__(self, engine: Any, max_fps: float = 0.0) -> None:
        self.engine = engine
        self._min_interval = 1.0 / max_fps if max_fps and max_fps > 0 else 0.0
        self._cond = threading.Condition()
        self._pending: Optional[tuple] = None
        self._result: Optional[Any] = None
        self._result_at = 0.0
        self._inference_ms = 0.0
        self._delivered = True
        self._stop = False
        self._error_logged = False
        self._thread = threading.Thread(target=self._run, name="mirrorlab-perception", daemon=True)
        self._thread.start()

    # -- video path --------------------------------------------------------- #
    def process(
        self, frame_bgr: np.ndarray, frame_index: Optional[int] = None, timestamp_ms: Optional[int] = None
    ) -> Snapshot:
        with self._cond:
            self._pending = (frame_bgr.copy(), frame_index, timestamp_ms)
            self._cond.notify()
            result = self._result
            fresh = result is not None and not self._delivered
            self._delivered = True
            age = (time.perf_counter() - self._result_at) * 1000.0 if result is not None else 0.0
            inference = self._inference_ms
        if result is None or age > STALE_AFTER_MS:
            # No result yet, or the worker has stalled. Report "nobody there" rather
            # than a face that may have left a second ago: that keeps the away
            # detector and the framer honest.
            return Snapshot(age_ms=age)
        dynamic = list(getattr(result, "dynamic", []) or []) if fresh else []
        return Snapshot(
            faces=list(getattr(result, "faces", []) or []),
            gestures=list(getattr(result, "gestures", []) or []),
            dynamic=dynamic,
            fresh=fresh,
            age_ms=age,
            inference_ms=inference,
        )

    # -- worker ------------------------------------------------------------- #
    def _run(self) -> None:
        while True:
            with self._cond:
                while self._pending is None and not self._stop:
                    self._cond.wait(timeout=0.5)
                if self._stop:
                    return
                frame, index, stamp = self._pending  # type: ignore[misc]
                self._pending = None
            started = time.perf_counter()
            try:
                result = self.engine.process(frame, index, stamp)
            except Exception as exc:
                if not self._error_logged:
                    log.warning("perception worker error (further errors suppressed): %s", exc)
                    self._error_logged = True
                continue
            elapsed = (time.perf_counter() - started) * 1000.0
            with self._cond:
                self._result = result
                self._result_at = time.perf_counter()
                self._inference_ms = elapsed
                self._delivered = False
            spare = self._min_interval - (time.perf_counter() - started)
            if spare > 0:
                time.sleep(spare)

    # -- lifecycle ------------------------------------------------------------- #
    def close(self) -> None:
        with self._cond:
            self._stop = True
            self._cond.notify_all()
        self._thread.join(timeout=2.0)
        closer = getattr(self.engine, "close", None)
        if callable(closer):
            closer()
