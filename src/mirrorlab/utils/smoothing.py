"""Signal smoothing: the difference between a demo and a product.

Raw MediaPipe landmarks jitter by a pixel or two every frame. Drawing them
directly produces the classic "shaky AR" look. MirrorLab ships two filters:

* :class:`OneEuroFilter` — the adaptive low-pass filter from Casiez et al.
  (CHI 2012). It is the industry standard for interactive systems because it
  removes jitter at rest *without* adding lag during fast motion.
* :class:`EmaFilter` — a plain exponential moving average, used for scalar
  scores such as expression confidences.
"""

from __future__ import annotations

import math
import time
from typing import Dict, Iterable, List, Optional

import numpy as np

__all__ = ["EmaFilter", "LandmarkSmoother", "OneEuroFilter", "SlidingWindow"]


def _alpha(cutoff: float, dt: float) -> float:
    """Smoothing factor for a first-order low-pass filter."""
    tau = 1.0 / (2.0 * math.pi * max(cutoff, 1e-6))
    return 1.0 / (1.0 + tau / max(dt, 1e-6))


class OneEuroFilter:
    """Adaptive low-pass filter for a single scalar signal.

    Args:
        min_cutoff: Cutoff frequency at rest. Lower = smoother but laggier.
        beta: Speed coefficient. Higher = more responsive to fast motion.
        d_cutoff: Cutoff for the derivative estimate.
    """

    __slots__ = ("_dx_prev", "_t_prev", "_x_prev", "beta", "d_cutoff", "min_cutoff")

    def __init__(self, min_cutoff: float = 1.7, beta: float = 0.35, d_cutoff: float = 1.0) -> None:
        self.min_cutoff = float(min_cutoff)
        self.beta = float(beta)
        self.d_cutoff = float(d_cutoff)
        self._x_prev: Optional[float] = None
        self._dx_prev: float = 0.0
        self._t_prev: Optional[float] = None

    def reset(self) -> None:
        self._x_prev = None
        self._dx_prev = 0.0
        self._t_prev = None

    def __call__(self, value: float, timestamp: Optional[float] = None) -> float:
        now = time.perf_counter() if timestamp is None else float(timestamp)
        if self._t_prev is None or self._x_prev is None:
            self._t_prev = now
            self._x_prev = float(value)
            return self._x_prev

        dt = max(now - self._t_prev, 1e-6)
        self._t_prev = now

        # Estimate the (filtered) derivative to adapt the cutoff.
        dx = (float(value) - self._x_prev) / dt
        a_d = _alpha(self.d_cutoff, dt)
        dx_hat = a_d * dx + (1.0 - a_d) * self._dx_prev
        self._dx_prev = dx_hat

        cutoff = self.min_cutoff + self.beta * abs(dx_hat)
        a = _alpha(cutoff, dt)
        x_hat = a * float(value) + (1.0 - a) * self._x_prev
        self._x_prev = x_hat
        return x_hat


class EmaFilter:
    """Exponential moving average with a fixed weight."""

    __slots__ = ("_value", "alpha")

    def __init__(self, alpha: float = 0.35) -> None:
        self.alpha = float(min(max(alpha, 0.0), 1.0))
        self._value: Optional[float] = None

    def reset(self) -> None:
        self._value = None

    def __call__(self, value: float) -> float:
        if self._value is None:
            self._value = float(value)
        else:
            self._value = self.alpha * float(value) + (1.0 - self.alpha) * self._value
        return self._value

    @property
    def value(self) -> Optional[float]:
        return self._value


class SlidingWindow:
    """Fixed-size ring buffer with majority-vote and mean helpers."""

    __slots__ = ("_items", "maxlen")

    def __init__(self, maxlen: int = 5) -> None:
        self.maxlen = int(max(1, maxlen))
        self._items: List[object] = []

    def push(self, item: object) -> None:
        self._items.append(item)
        if len(self._items) > self.maxlen:
            del self._items[0]

    def clear(self) -> None:
        self._items.clear()

    def __len__(self) -> int:
        return len(self._items)

    @property
    def items(self) -> List[object]:
        return list(self._items)

    def majority(self, default: Optional[object] = None) -> Optional[object]:
        """Most frequent item, with ties broken by the most recent occurrence."""
        if not self._items:
            return default
        counts: Dict[object, int] = {}
        for item in self._items:
            counts[item] = counts.get(item, 0) + 1
        best = max(counts.values())
        for item in reversed(self._items):
            if counts[item] == best:
                return item
        return default

    def mean(self, default: float = 0.0) -> float:
        numeric = [float(item) for item in self._items if isinstance(item, (int, float))]
        return sum(numeric) / len(numeric) if numeric else default


class LandmarkSmoother:
    """One-Euro smoothing for a set of landmark point tracks.

    Each landmark and each coordinate gets **its own** filter instance. That is
    the whole point of the class, and it is easy to get wrong: reusing a single
    filter across all 478 face landmarks turns it into a global average and
    collapses the entire mesh onto one point — which reads as a detector
    failure rather than a smoothing bug.

    Per-point state is also what makes the result look *stable* rather than
    *damped*: a fingertip that moves fast keeps its responsiveness while a
    stationary face stops vibrating.
    """

    def __init__(
        self,
        min_cutoff: float = 1.7,
        beta: float = 0.35,
        dimensions: int = 3,
        max_tracks: int = 8,
    ) -> None:
        self.min_cutoff = float(min_cutoff)
        self.beta = float(beta)
        self.dimensions = int(dimensions)
        self.max_tracks = int(max_tracks)
        #: ``{track: [[filter per dimension] per landmark]}``
        self._filters: Dict[int, List[List[OneEuroFilter]]] = {}

    def reset(self) -> None:
        self._filters.clear()

    def _rows_for(self, track: int, count: int) -> List[List[OneEuroFilter]]:
        """Return (creating on demand) one filter row per landmark."""
        rows = self._filters.get(track)
        if rows is None:
            rows = []
            self._filters[track] = rows
        while len(rows) < count:
            rows.append([OneEuroFilter(self.min_cutoff, self.beta) for _ in range(self.dimensions)])
        return rows

    def apply(
        self,
        points: np.ndarray,
        track: int = 0,
        timestamp: Optional[float] = None,
    ) -> np.ndarray:
        """Smooth an ``(N, D)`` array of landmarks.

        Extra dimensions beyond ``self.dimensions`` are passed through untouched.
        """
        array = np.asarray(points, dtype=np.float64)
        if array.size == 0:
            return array
        rows = self._rows_for(track % self.max_tracks, array.shape[0])
        out = array.copy()
        dims = min(self.dimensions, array.shape[1])
        for index in range(array.shape[0]):
            row = rows[index]
            for dim in range(dims):
                out[index, dim] = row[dim](array[index, dim], timestamp)
        return out

    def apply_many(
        self,
        clouds: Iterable[np.ndarray],
        timestamp: Optional[float] = None,
    ) -> List[np.ndarray]:
        """Smooth several landmark clouds, each on its own track."""
        return [self.apply(cloud, track=i, timestamp=timestamp) for i, cloud in enumerate(clouds)]

    @property
    def filter_count(self) -> int:
        """Total live filter instances — the tests use this to prove no sharing."""
        return sum(len(row) for rows in self._filters.values() for row in rows)
