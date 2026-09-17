"""Person/background segmentation.

Powers the background-blur, background-replace and privacy filters. Wraps
MediaPipe's ``ImageSegmenter`` and normalises its two output shapes
(``confidence_masks`` and ``category_mask``) into a single float mask in
``[0, 1]`` where 1 means "person".

Segmentation is optional: when the model or the runtime is missing, every
consumer degrades to a sensible default (whole-frame blur, full-frame
pixelation) instead of failing.
"""

from __future__ import annotations

import threading
from contextlib import suppress
from typing import Optional

import cv2
import numpy as np

from ..utils.logging import get_logger
from .models import ensure_model

__all__ = ["SelfieSegmenter", "create_segmenter", "refine_mask"]

log = get_logger("segmentation")


def refine_mask(
    mask: np.ndarray,
    feather: int = 9,
    threshold: float = 0.5,
    keep_largest: bool = True,
) -> np.ndarray:
    """Clean a raw probability mask into a usable alpha channel.

    Args:
        mask: Float mask in ``[0, 1]``.
        feather: Gaussian radius applied to the final alpha, which removes the
            blocky boundary MediaPipe's low-resolution mask would otherwise show.
        threshold: Below this the mask is treated as background.
        keep_largest: Drop disconnected blobs (a second person in the mirror,
            a poster on the wall) so the cut-out stays stable.
    """
    if mask is None or mask.size == 0:
        return mask
    binary = (np.clip(mask, 0.0, 1.0) > threshold).astype(np.uint8)
    if keep_largest and binary.any():
        count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
        if count > 2:
            largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
            binary = (labels == largest).astype(np.uint8)
    # Close pinholes then feather.
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    alpha = cv2.GaussianBlur(binary.astype(np.float32), (feather | 1, feather | 1), 0)
    return np.clip(alpha, 0.0, 1.0)


class SelfieSegmenter:
    """MediaPipe ``ImageSegmenter`` wrapper producing a person alpha mask."""

    def __init__(
        self,
        auto_download: bool = True,
        model_key: str = "selfie_segmenter",
        feather: int = 9,
    ) -> None:
        self.available = False
        self.reason = ""
        self._segmenter = None
        self._lock = threading.Lock()
        self._feather = int(feather)
        self._last_mask: Optional[np.ndarray] = None

        try:
            from mediapipe.tasks.python import BaseOptions, vision
        except Exception as exc:  # pragma: no cover - environment dependent
            self.reason = f"MediaPipe Tasks API unavailable ({exc})"
            log.info("Segmentation disabled: %s", self.reason)
            return

        path = ensure_model(model_key, auto_download=auto_download)
        if path is None:
            self.reason = f"model {model_key} is not cached"
            log.info("Segmentation disabled: %s", self.reason)
            return

        try:
            options = vision.ImageSegmenterOptions(
                base_options=BaseOptions(model_asset_path=str(path)),
                running_mode=vision.RunningMode.VIDEO,
                output_confidence_masks=True,
                output_category_mask=False,
            )
            self._segmenter = vision.ImageSegmenter.create_from_options(options)
            self.available = True
            log.info("Segmentation ready (%s)", model_key)
        except Exception as exc:  # pragma: no cover - environment dependent
            self.reason = str(exc)
            log.warning("Segmentation disabled: %s", exc)

    def process(self, frame_bgr: np.ndarray, timestamp_ms: int) -> Optional[np.ndarray]:
        """Return a feathered person mask in ``[0, 1]`` at frame resolution."""
        if not self.available or self._segmenter is None:
            return None
        import mediapipe as mp

        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        with self._lock:
            try:
                result = self._segmenter.segment_for_video(image, int(timestamp_ms))
            except Exception as exc:  # pragma: no cover - runtime dependent
                log.debug("Segmentation frame failed: %s", exc)
                return self._last_mask

        mask = self._extract(result)
        if mask is None:
            return self._last_mask

        height, width = frame_bgr.shape[:2]
        if mask.shape[:2] != (height, width):
            mask = cv2.resize(mask, (width, height), interpolation=cv2.INTER_LINEAR)
        refined = refine_mask(mask, feather=self._feather)
        self._last_mask = refined
        return refined

    @staticmethod
    def _extract(result: object) -> Optional[np.ndarray]:
        """Normalise MediaPipe's several mask representations into one array."""
        confidence = getattr(result, "confidence_masks", None)
        if confidence:
            # Selfie segmenter: channel 0 is background, channel 1 is person.
            array = np.asarray(confidence[0].numpy_view(), dtype=np.float32)
            mask = (array[..., 1] if array.shape[-1] >= 2 else array[..., 0]) if array.ndim == 3 else array
            return mask if mask.max() <= 1.0 else mask / 255.0

        category = getattr(result, "category_mask", None)
        if category is not None:
            array = np.asarray(category.numpy_view(), dtype=np.float32)
            array = np.squeeze(array)
            # Multiclass: label 0 is background, everything else is the person.
            return (array > 0).astype(np.float32)

        return None

    def close(self) -> None:
        if self._segmenter is not None:
            with suppress(Exception):  # pragma: no cover - already torn down
                self._segmenter.close()
            self._segmenter = None
        self.available = False

    def __enter__(self) -> "SelfieSegmenter":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def create_segmenter(auto_download: bool = True, model_key: str = "selfie_segmenter") -> SelfieSegmenter:
    """Build a segmenter; the result may report ``available == False``."""
    return SelfieSegmenter(auto_download=auto_download, model_key=model_key)
