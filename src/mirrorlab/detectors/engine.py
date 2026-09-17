"""The perception engine: one call per frame, everything MirrorLab knows.

``PerceptionEngine`` owns the face and hand detectors, the expression
classifier and the gesture tracker, and returns a single :class:`PerceptionResult`
that the filter chain, the overlay renderer and the gesture controller consume.
Keeping this orchestration in one place is what lets the rest of the codebase
stay pure and testable.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

from ..config import Config
from ..expressions import ExpressionClassifier, ExpressionResult
from ..gestures import DynamicGesture, GestureMatch, GestureTracker, classify_hands
from ..utils.logging import get_logger
from ..utils.smoothing import SlidingWindow
from .base import FaceObservation, FrameAnalysis, HandObservation
from .face import FaceDetector
from .hands import HandDetector

__all__ = ["PerceptionEngine", "PerceptionResult"]

log = get_logger("engine")


@dataclass
class PerceptionResult:
    """Everything derived from one video frame."""

    analysis: FrameAnalysis
    expression: ExpressionResult = field(default_factory=ExpressionResult)
    gestures: List[GestureMatch] = field(default_factory=list)
    dynamic: List[DynamicGesture] = field(default_factory=list)
    timestamp_ms: int = 0
    total_ms: float = 0.0

    @property
    def faces(self) -> List[FaceObservation]:
        return self.analysis.faces

    @property
    def hands(self) -> List[HandObservation]:
        return self.analysis.hands

    @property
    def face(self) -> Optional[FaceObservation]:
        return self.analysis.primary_face

    @property
    def hand(self) -> Optional[HandObservation]:
        return self.analysis.primary_hand

    @property
    def gesture(self) -> GestureMatch:
        """The most confident gesture across all visible hands."""
        if not self.gestures:
            return GestureMatch(name="none", score=0.0, definition=None)
        return max(self.gestures, key=lambda match: match.score)

    @property
    def pose(self):
        """The :class:`~mirrorlab.gestures.HandPose` of the most confident gesture."""
        match = self.gesture
        return match.pose

    def gesture_names(self) -> List[str]:
        return [match.name for match in self.gestures if match.name != "none"]

    def describe(self) -> str:
        bits = []
        if self.analysis.faces:
            bits.append(f"faces={len(self.analysis.faces)}")
        if self.analysis.hands:
            bits.append(f"hands={len(self.analysis.hands)}")
        if self.expression.name != "unknown":
            bits.append(f"expr={self.expression.name}({self.expression.score:.2f})")
        names = self.gesture_names()
        if names:
            bits.append("gesture=" + ",".join(names))
        return " ".join(bits) if bits else "no detections"


class PerceptionEngine:
    """Runs every detector for a frame and caches the derived state.

    Args:
        config: MirrorLab configuration.
        face_backend: Force a face engine, or ``auto``.
        hand_backend: Force a hand engine, or ``auto``.
        auto_download: Allow model downloads on first use.

    Example:
        >>> engine = PerceptionEngine(Config())              # doctest: +SKIP
        >>> result = engine.process(frame_bgr, frame_index=0)  # doctest: +SKIP
        >>> result.expression.display()                      # doctest: +SKIP
        '😊 Feliz'
    """

    def __init__(
        self,
        config: Optional[Config] = None,
        face_backend: str = "auto",
        hand_backend: str = "auto",
        auto_download: bool = True,
    ) -> None:
        self.config = config or Config()
        self.face_detector = FaceDetector(self.config, face_backend, auto_download)
        self.hand_detector = HandDetector(self.config, hand_backend, auto_download)
        self.classifier = ExpressionClassifier(
            smoothing=self.config.expression_smoothing if self.config.smooth_landmarks else 0.0
        )
        self.tracker = GestureTracker()
        self._expression_votes = SlidingWindow(maxlen=7)
        self._frame_index = 0
        self._start = time.perf_counter()

    # -- capabilities ------------------------------------------------------ #
    @property
    def face_available(self) -> bool:
        return self.face_detector.available

    @property
    def hand_available(self) -> bool:
        return self.hand_detector.available

    @property
    def backend_summary(self) -> str:
        return f"face={self.face_detector.backend.name} hands={self.hand_detector.backend.name}"

    # -- main entry point -------------------------------------------------- #
    def process(
        self,
        frame_bgr: np.ndarray,
        frame_index: Optional[int] = None,
        timestamp_ms: Optional[int] = None,
    ) -> PerceptionResult:
        """Run the full perception stack on one BGR frame."""
        started = time.perf_counter()
        if frame_index is None:
            frame_index = self._frame_index
        self._frame_index = frame_index + 1
        if timestamp_ms is None:
            timestamp_ms = int((time.perf_counter() - self._start) * 1000.0)

        import cv2

        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

        faces: List[FaceObservation] = []
        hands: List[HandObservation] = []
        if self.config.enable_face:
            faces = self.face_detector.process(frame_bgr, timestamp_ms, rgb)
        if self.config.enable_hands:
            hands = self.hand_detector.process(frame_bgr, timestamp_ms, rgb)

        analysis = FrameAnalysis(
            faces=faces,
            hands=hands,
            frame_index=frame_index,
            timestamp_ms=timestamp_ms,
            backend=self.backend_summary,
        )

        expression = self._classify_expression(analysis.primary_face)
        gestures = classify_hands(hands) if hands else []

        dynamic: List[DynamicGesture] = []
        if hands:
            # Track the largest hand for motion gestures.
            primary = max(hands, key=lambda h: _hand_span(h))
            event = self.tracker.update(primary.landmarks[:, :2].mean(axis=0), time.perf_counter())
            if event is not None:
                dynamic.append(event)
        else:
            self.tracker.update(None)

        analysis.inference_ms = (time.perf_counter() - started) * 1000.0
        return PerceptionResult(
            analysis=analysis,
            expression=expression,
            gestures=gestures,
            dynamic=dynamic,
            timestamp_ms=timestamp_ms,
            total_ms=analysis.inference_ms,
        )

    # -- helpers ----------------------------------------------------------- #
    def _classify_expression(self, face: Optional[FaceObservation]) -> ExpressionResult:
        result = self.classifier.classify(face)
        if face is None:
            self._expression_votes.clear()
            return result
        # Majority vote over recent frames removes single-frame misreads without
        # adding the lag of a longer smoothing window.
        self._expression_votes.push(result.name)
        stable = self._expression_votes.majority(result.name)
        if stable and stable != result.name and self._expression_votes.items.count(stable) >= 4:
            result.name = str(stable)
            result.score = float(result.scores.get(result.name, result.score))
        return result

    # -- lifecycle --------------------------------------------------------- #
    def reset(self) -> None:
        self.face_detector.reset()
        self.hand_detector.reset()
        self.classifier.reset()
        self.tracker.reset()
        self._expression_votes.clear()

    def close(self) -> None:
        self.face_detector.close()
        self.hand_detector.close()

    def __enter__(self) -> "PerceptionEngine":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def warm_up(self, width: int = 640, height: int = 480, frames: int = 2) -> None:
        """Run a few blank frames so the first real frame is not the slow one.

        MediaPipe lazily allocates its graphs and XNNPACK delegates; without a
        warm-up the first user-visible frame can take 300 ms and the preview
        visibly hitches.
        """
        blank = np.zeros((height, width, 3), dtype=np.uint8)
        for index in range(max(0, frames)):
            self.process(blank, frame_index=index, timestamp_ms=index * 33)


def _hand_span(hand: HandObservation) -> float:
    points = hand.landmarks
    if points is None or points.size == 0:
        return 0.0
    xs, ys = points[:, 0], points[:, 1]
    return float((xs.max() - xs.min()) * (ys.max() - ys.min()))
