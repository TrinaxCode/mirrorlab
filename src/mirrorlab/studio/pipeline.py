"""The studio frame pipeline: one camera frame in, one output frame out.

Stage order is deliberate::

    camera frame
      -> perception        face + hands (MediaPipe)
      -> gestures          hand poses become actions
      -> studio light      exposure metered on the face, applied to the real frame
      -> background        blur / replace / green / black, using the person mask
      -> auto-frame        crop and zoom the *composited* frame
      -> reactions         floating icons, drawn on the final picture
      -> privacy shutter   always last, so nothing can be drawn over the cover

Light runs before the background so a replacement image is not re-exposed, and
framing runs after it so a virtual background is cropped with the person. The
shutter runs last so that, once it is closed, no earlier stage can leak a pixel.

The pipeline takes its detectors as constructor arguments. Tests inject small
fakes; production code passes the real MediaPipe-backed objects.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

import cv2
import numpy as np

from ..actions import ActionEvent, GestureController
from ..utils.logging import get_logger
from .background import BackgroundProcessor
from .framing import AutoFramer, face_boxes, union_box
from .light import StudioLight
from .privacy import AwayDetector, PrivacyShutter
from .reactions import ReactionStage
from .settings import StudioSettings
from .state import StudioState

__all__ = ["FrameResult", "Perception", "Segmenter", "StudioPipeline"]

log = get_logger("studio.pipeline")


def _shrink(frame: np.ndarray, width: int) -> np.ndarray:
    """``frame`` scaled down to ``width`` pixels wide (never up)."""
    if frame.shape[1] <= width:
        return frame
    scale = width / frame.shape[1]
    return cv2.resize(frame, (width, max(8, round(frame.shape[0] * scale))), interpolation=cv2.INTER_AREA)


class Perception(Protocol):
    """What the pipeline needs from the perception engine."""

    def process(
        self, frame_bgr: np.ndarray, frame_index: Optional[int] = None, timestamp_ms: Optional[int] = None
    ) -> Any: ...


class Segmenter(Protocol):
    """What the pipeline needs from the person segmenter."""

    available: bool

    def process(self, frame_bgr: np.ndarray, timestamp_ms: int) -> Optional[np.ndarray]: ...


@dataclass
class FrameResult:
    """Everything produced for one frame."""

    output: np.ndarray
    events: List[ActionEvent] = field(default_factory=list)
    face_present: bool = False
    gesture: str = ""
    dwell_progress: float = 0.0
    shutter_level: float = 0.0
    timings_ms: Dict[str, float] = field(default_factory=dict)


class StudioPipeline:
    """Runs the studio stages for each frame.

    Args:
        settings: Immutable session settings.
        state: Mutable runtime state shared with gestures, keys and the control socket.
        perception: Face/hand engine, or ``None`` to run without perception.
        segmenter: Person segmenter, or ``None`` when unavailable.
    """

    def __init__(
        self,
        settings: StudioSettings,
        state: Optional[StudioState] = None,
        perception: Optional[Perception] = None,
        segmenter: Optional[Segmenter] = None,
    ) -> None:
        self.settings = settings
        self.perception = perception
        self.segmenter = segmenter

        has_image = bool(settings.background_image) and BackgroundProcessor.image_readable(
            settings.background_image
        )
        if settings.background == "replace" and not has_image:
            log.warning("background 'replace' needs a readable image (--bg-image PATH); using blur instead")
        self.state = state if state is not None else StudioState.from_settings(settings, has_image)
        self.state.has_replace_image = has_image
        state = self.state

        self.background = BackgroundProcessor(
            mode=state.background,
            blur_strength=settings.blur_strength,
            image_path=settings.background_image,
            smoothing=settings.mask_smoothing,
        )
        self.light = StudioLight(strength=settings.light_strength)
        self.framer = AutoFramer((settings.width, settings.height), max_zoom=settings.max_zoom)
        self.shutter = PrivacyShutter(mode=settings.privacy_mode, text=settings.away_text)
        if state.privacy:
            # Starting covered means covered from the very first frame, not a fade-in
            # from an open shutter, which would show the camera for a quarter second.
            self.shutter.closed = True
            self.shutter.level = 1.0
        self.away = AwayDetector(settings.away_after)
        self.reactions = ReactionStage() if settings.reactions else None
        self.controller = GestureController(
            bindings=settings.bindings,
            dwell_overrides=settings.dwell,
            enabled=settings.gesture_control,
        )
        self._index = 0
        self._origin = time.perf_counter()
        self._away = False

    # ------------------------------------------------------------------ #
    def process(self, frame: np.ndarray, now: Optional[float] = None) -> FrameResult:
        """Run every stage for ``frame`` (BGR, any size) and return the output frame."""
        now = time.perf_counter() if now is None else now
        timings: Dict[str, float] = {}
        settings, state = self.settings, self.state
        stamp = int((now - self._origin) * 1000.0)

        if frame.shape[1] != settings.width or frame.shape[0] != settings.height:
            frame = cv2.resize(frame, (settings.width, settings.height), interpolation=cv2.INTER_AREA)

        # Detectors run on a smaller copy: their outputs are normalised, so the
        # result is the same and the cost is a fraction.
        analysis = _shrink(frame, settings.analysis_width)

        # ---- perception and gestures ------------------------------------
        t0 = time.perf_counter()
        faces: list = []
        gesture_name, progress = "", 0.0
        events: List[ActionEvent] = []
        if self.perception is not None:
            try:
                result = self.perception.process(analysis, self._index, stamp)
                faces = list(getattr(result, "faces", []) or [])
                if settings.gesture_control:
                    events = self.controller.update(
                        getattr(result, "gestures", []) or [], getattr(result, "dynamic", []) or [], now
                    )
                    gesture_name = self.controller.pending
                    progress = self.controller.last_progress
            except Exception as exc:  # perception must never take the camera down
                log.warning("perception failed on frame %d: %s", self._index, exc)
        timings["perceive"] = (time.perf_counter() - t0) * 1000.0

        for event in events:
            outcome = state.apply_action(event.action)
            log.info("gesture %s -> %s (%s)", event.gesture, event.action, outcome.message)
        self._index += 1

        boxes = face_boxes(faces)
        face_box = union_box(boxes)

        # While the shutter is fully closed nothing underneath can be seen, so the
        # expensive stages are skipped. Perception keeps running: gestures must
        # still be able to reopen it, and the away detector needs to see faces.
        covered = self.shutter.level >= 1.0 and (state.privacy or self._away)

        # ---- light -------------------------------------------------------
        t0 = time.perf_counter()
        work = frame
        if state.studio_light and not covered:
            work = self.light.apply(work, face_box, now)
        timings["light"] = (time.perf_counter() - t0) * 1000.0

        # ---- background ----------------------------------------------------
        t0 = time.perf_counter()
        self.background.set_mode(state.background)
        if self.background.needs_mask and not covered:
            mask = None
            if self.segmenter is not None and getattr(self.segmenter, "available", False):
                try:
                    mask = self.segmenter.process(_shrink(frame, settings.segmentation_width), stamp)
                except Exception as exc:
                    log.warning("segmentation failed on frame %d: %s", self._index, exc)
            work = self.background.apply(work, mask)
        timings["background"] = (time.perf_counter() - t0) * 1000.0

        # ---- framing -------------------------------------------------------
        t0 = time.perf_counter()
        if state.auto_frame and not covered:
            rect = self.framer.update(boxes, now)
            work = self.framer.crop(work, rect)
        else:
            self.framer.reset()
        timings["frame"] = (time.perf_counter() - t0) * 1000.0

        # ---- reactions -----------------------------------------------------
        if self.reactions is not None:
            if work is frame:
                work = frame.copy()
            for name in state.drain_reactions():
                self.reactions.trigger(name, now, settings.height)
            work = self.reactions.apply(work, now)

        # ---- privacy shutter (last) ------------------------------------------
        self._away = self.away.update(bool(faces), now)
        self.shutter.set_closed(state.privacy)
        output = self.shutter.apply(work, now, force=self._away)

        return FrameResult(
            output=output,
            events=events,
            face_present=bool(faces),
            gesture=gesture_name,
            dwell_progress=progress,
            shutter_level=self.shutter.level,
            timings_ms=timings,
        )

    def cover_frame(self, now: Optional[float] = None) -> np.ndarray:
        """A fully covered frame, for when the camera itself is lost.

        Used by the session when the capture stalls: showing the last good frame
        would freeze the call on whatever you were doing, so the output is the
        privacy cover instead.
        """
        now = time.perf_counter() if now is None else now
        blank = np.zeros((self.settings.height, self.settings.width, 3), dtype=np.uint8)
        self.shutter.level = 1.0
        return self.shutter.apply(blank, now, force=True)

    def close(self) -> None:
        for component in (self.perception, self.segmenter):
            closer = getattr(component, "close", None)
            if callable(closer):
                try:
                    closer()
                except Exception as exc:  # pragma: no cover - teardown only
                    log.debug("close failed: %s", exc)
