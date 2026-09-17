"""Frame-rate measurement and profiling helpers."""

from __future__ import annotations

import time
from collections import deque
from typing import Deque, Dict, Optional

__all__ = ["FpsMeter", "Stopwatch"]


class FpsMeter:
    """Rolling FPS estimate plus per-stage timings.

    Uses a deque of frame timestamps, which gives a stable reading instead of
    the jumpy "1/dt" number most demos show.
    """

    __slots__ = ("_frames", "_maxlen", "_open", "_stages", "_stamps", "_started")

    def __init__(self, window: int = 45) -> None:
        self._maxlen = int(max(2, window))
        self._stamps: Deque[float] = deque(maxlen=self._maxlen)
        self._started = time.perf_counter()
        self._frames = 0
        self._stages: Dict[str, Deque[float]] = {}
        self._open: Dict[str, float] = {}

    def tick(self) -> float:
        """Register a completed frame and return the current FPS."""
        now = time.perf_counter()
        self._stamps.append(now)
        self._frames += 1
        return self.fps

    @property
    def fps(self) -> float:
        if len(self._stamps) < 2:
            return 0.0
        span = self._stamps[-1] - self._stamps[0]
        if span <= 1e-9:
            return 0.0
        return (len(self._stamps) - 1) / span

    @property
    def frame_time_ms(self) -> float:
        fps = self.fps
        return 1000.0 / fps if fps > 0 else 0.0

    @property
    def frames(self) -> int:
        return self._frames

    @property
    def elapsed(self) -> float:
        return time.perf_counter() - self._started

    @property
    def average_fps(self) -> float:
        elapsed = self.elapsed
        return self._frames / elapsed if elapsed > 0 else 0.0

    # -- stage profiling --------------------------------------------------- #
    def begin(self, stage: str) -> None:
        """Start timing a pipeline stage (``detect``, ``filter``, ``render``…)."""
        self._open[stage] = time.perf_counter()

    def end(self, stage: str) -> float:
        """Stop timing a stage and return its duration in milliseconds."""
        started = self._open.pop(stage, None)
        if started is None:
            return 0.0
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        bucket = self._stages.setdefault(stage, deque(maxlen=self._maxlen))
        bucket.append(elapsed_ms)
        return elapsed_ms

    def stage_mean(self, stage: str) -> float:
        bucket = self._stages.get(stage)
        return sum(bucket) / len(bucket) if bucket else 0.0

    def stage_peak(self, stage: str) -> float:
        bucket = self._stages.get(stage)
        return max(bucket) if bucket else 0.0

    def stages(self) -> Dict[str, float]:
        """Mean milliseconds per recorded stage."""
        return {name: self.stage_mean(name) for name in self._stages}

    def reset(self) -> None:
        self._stamps.clear()
        self._stages.clear()
        self._open.clear()
        self._frames = 0
        self._started = time.perf_counter()


class Stopwatch:
    """Context manager that records its duration on exit."""

    __slots__ = ("_start", "elapsed", "label", "sink")

    def __init__(self, label: str = "", sink: Optional[FpsMeter] = None) -> None:
        self.label = label
        self.sink = sink
        self.elapsed = 0.0
        self._start = 0.0

    def __enter__(self) -> "Stopwatch":
        self._start = time.perf_counter()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.elapsed = time.perf_counter() - self._start
        if self.sink is not None and self.label:
            bucket = self.sink._stages.setdefault(self.label, deque(maxlen=self.sink._maxlen))
            bucket.append(self.elapsed * 1000.0)

    @property
    def ms(self) -> float:
        return self.elapsed * 1000.0
