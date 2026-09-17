"""High-level face detector: backend + landmark smoothing + expression scores."""

from __future__ import annotations

from typing import List, Optional

import numpy as np

from ..config import Config
from ..utils.logging import get_logger
from ..utils.smoothing import LandmarkSmoother
from .backends import FaceBackend, create_face_backend
from .base import FaceObservation

__all__ = ["FaceDetector"]

log = get_logger("face")


class FaceDetector:
    """Detect faces and smooth their landmarks across frames.

    Args:
        config: MirrorLab configuration; detector-related fields are read here.
        backend: Force a specific engine — ``auto`` (default), ``tasks``,
            ``solutions``, ``yunet``, ``haar`` or ``none``.
        auto_download: Allow downloading model bundles on first use.

    Example:
        >>> detector = FaceDetector(Config(enable_face=True))   # doctest: +SKIP
        >>> faces = detector.process(frame_bgr, timestamp_ms=0)  # doctest: +SKIP
    """

    def __init__(
        self,
        config: Optional[Config] = None,
        backend: str = "auto",
        auto_download: bool = True,
    ) -> None:
        self.config = config or Config()
        self.backend: FaceBackend = create_face_backend(
            max_faces=self.config.max_faces,
            min_detection_confidence=self.config.min_face_confidence,
            min_tracking_confidence=self.config.min_tracking_confidence,
            preferred=backend,
            auto_download=auto_download,
        )
        self.smoother = LandmarkSmoother(
            min_cutoff=self.config.smoothing_min_cutoff,
            beta=self.config.smoothing_beta,
            dimensions=3,
        )

    @property
    def available(self) -> bool:
        return self.backend.name != "none"

    @property
    def provides_blendshapes(self) -> bool:
        return self.backend.provides_blendshapes

    def process(
        self,
        frame_bgr: np.ndarray,
        timestamp_ms: int,
        rgb: Optional[np.ndarray] = None,
    ) -> List[FaceObservation]:
        """Detect faces in a BGR frame, applying temporal smoothing when enabled."""
        import cv2

        rgb_frame = rgb if rgb is not None else cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        faces = self.backend.process(rgb_frame, timestamp_ms, frame_bgr)

        if self.config.smooth_landmarks and self.backend.provides_landmarks:
            for index, face in enumerate(faces):
                if face.landmarks.size:
                    face.landmarks = self.smoother.apply(
                        face.landmarks, track=index, timestamp=timestamp_ms / 1000.0
                    )
        elif not self.config.smooth_landmarks:
            self.smoother.reset()
        return faces

    def reset(self) -> None:
        self.smoother.reset()

    def close(self) -> None:
        self.backend.close()

    def __enter__(self) -> "FaceDetector":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
