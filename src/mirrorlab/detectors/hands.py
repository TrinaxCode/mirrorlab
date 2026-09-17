"""High-level hand detector: backend + landmark smoothing + gesture labels."""

from __future__ import annotations

from typing import List, Optional

import numpy as np

from ..config import Config
from ..utils.logging import get_logger
from ..utils.smoothing import LandmarkSmoother
from .backends import HandBackend, create_hand_backend
from .base import HandObservation

__all__ = ["HandDetector"]

log = get_logger("hands")


class HandDetector:
    """Detect hands and smooth their 21 landmarks across frames.

    Gesture *classification* lives in :mod:`mirrorlab.gestures` and is applied
    by the perception engine, so this class stays a pure detector.

    Example:
        >>> detector = HandDetector(Config(enable_hands=True))  # doctest: +SKIP
        >>> hands = detector.process(frame_bgr, timestamp_ms=0)  # doctest: +SKIP
    """

    def __init__(
        self,
        config: Optional[Config] = None,
        backend: str = "auto",
        auto_download: bool = True,
    ) -> None:
        self.config = config or Config()
        self.backend: HandBackend = create_hand_backend(
            max_hands=self.config.max_hands,
            min_detection_confidence=self.config.min_hand_confidence,
            min_tracking_confidence=self.config.min_tracking_confidence,
            model_complexity=self.config.model_complexity,
            preferred=backend,
            auto_download=auto_download,
        )
        self.smoother = LandmarkSmoother(
            min_cutoff=self.config.smoothing_min_cutoff * 1.3,  # hands move faster than faces
            beta=self.config.smoothing_beta,
            dimensions=3,
            max_tracks=4,
        )

    @property
    def available(self) -> bool:
        return self.backend.name != "none"

    def process(
        self,
        frame_bgr: np.ndarray,
        timestamp_ms: int,
        rgb: Optional[np.ndarray] = None,
    ) -> List[HandObservation]:
        """Detect hands in a BGR frame, applying temporal smoothing when enabled."""
        import cv2

        rgb_frame = rgb if rgb is not None else cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        hands = self.backend.process(rgb_frame, timestamp_ms)

        if self.config.smooth_landmarks:
            for index, hand in enumerate(hands):
                # Track by handedness so a left hand does not inherit the
                # right hand's filter state when detection order swaps.
                track = index + (2 if hand.is_right else 0)
                if hand.landmarks.size:
                    hand.landmarks = self.smoother.apply(
                        hand.landmarks, track=track, timestamp=timestamp_ms / 1000.0
                    )
                if hand.world_landmarks is not None and hand.world_landmarks.size:
                    hand.world_landmarks = self.smoother.apply(
                        hand.world_landmarks, track=track + 100, timestamp=timestamp_ms / 1000.0
                    )
        else:
            self.smoother.reset()
        return hands

    def reset(self) -> None:
        self.smoother.reset()

    def close(self) -> None:
        self.backend.close()

    def __enter__(self) -> "HandDetector":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
