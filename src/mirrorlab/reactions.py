"""Reaction images: show a picture that matches the expression on your face.

This is the feature the original 1.0 prototype was built around, kept because it
is genuinely fun in a photo booth or a video call: smile and a grinning sticker
pops up, raise your eyebrows and a surprised one does.

The library is deliberately forgiving:

* images are looked up by expression name, then by any documented alias, so
  ``smile.png`` works for the ``happy`` expression;
* a missing directory or a missing file is not an error — the feature just
  shows nothing, which is what you want when someone runs the app from a
  different working directory;
* files are loaded once and cached at the display size, because decoding a PNG
  every frame would cost more than the whole rest of the pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from .expressions import EXPRESSION_ALIASES, EXPRESSIONS
from .utils.logging import get_logger

__all__ = ["ReactionLibrary", "ReactionOverlay"]

log = get_logger("reactions")

#: File names probed for each expression, in priority order.
_ALIASES: Dict[str, Tuple[str, ...]] = {
    "happy": ("smile", "happy", "sonrisa"),
    "laugh": ("laugh", "laughing", "risa"),
    "sad": ("sad", "triste", "tristeza"),
    "angry": ("angry", "enojo", "enfadado"),
    "surprised": ("surprised", "sorpresa", "wow"),
    "neutral": ("neutral",),
    "kiss": ("kiss", "love", "beso", "amor"),
    "wink": ("wink", "guino"),
    "brow_raise": ("brow_raise", "thinking", "pensando"),
    "thinking": ("thinking", "brow_raise", "pensando"),
    "disgust": ("disgust", "asco"),
    "fear": ("fear", "miedo"),
    "yawn": ("yawn", "bostezo"),
    "squint": ("squint",),
    "puff": ("puff",),
    "contempt": ("contempt",),
    "blink": ("blink",),
    "unknown": (),
}

_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")


@dataclass
class ReactionOverlay:
    """A reaction image plus the metadata needed to place it."""

    expression: str
    image: np.ndarray
    corner: str = "bottom-right"
    margin: int = 18
    scale: float = 0.26
    alpha: float = 0.95
    label: str = ""

    def draw(self, frame: np.ndarray) -> np.ndarray:
        """Composite the reaction onto ``frame`` (in place) and return it."""
        if self.image is None or self.image.size == 0:
            return frame
        height, width = frame.shape[:2]
        target_w = max(48, int(width * self.scale))
        ratio = target_w / self.image.shape[1]
        target_h = max(1, int(self.image.shape[0] * ratio))
        if target_h > height * 0.6:
            target_h = int(height * 0.6)
            target_w = max(1, int(self.image.shape[1] * (target_h / self.image.shape[0])))
        resized = cv2.resize(self.image, (target_w, target_h), interpolation=cv2.INTER_AREA)

        x0, y0 = self._origin(width, height, target_w, target_h)
        x1, y1 = min(width, x0 + target_w), min(height, y0 + target_h)
        x0, y0 = max(0, x0), max(0, y0)
        if x1 <= x0 or y1 <= y0:
            return frame
        patch = resized[: y1 - y0, : x1 - x0]
        roi = frame[y0:y1, x0:x1]
        cv2.addWeighted(patch, self.alpha, roi, 1.0 - self.alpha, 0, dst=roi)
        cv2.rectangle(frame, (x0 - 1, y0 - 1), (x1, y1), (235, 235, 235), 2, cv2.LINE_AA)
        return frame

    def _origin(self, width: int, height: int, w: int, h: int) -> Tuple[int, int]:
        m = self.margin
        return {
            "top-left": (m, m),
            "top-right": (width - w - m, m),
            "bottom-left": (m, height - h - m),
            "bottom-right": (width - w - m, height - h - m),
            "center": ((width - w) // 2, (height - h) // 2),
        }.get(self.corner, (width - w - m, height - h - m))


class ReactionLibrary:
    """Loads and caches one reaction image per expression.

    Args:
        directory: Folder to search. Missing folders are fine.
        max_width: Images are downscaled once on load to bound memory.
        corner: Where the overlay is drawn (``bottom-right`` by default).
        scale: Overlay width as a fraction of the frame width.
    """

    def __init__(
        self,
        directory: str | Path = "assets/reactions",
        max_width: int = 640,
        corner: str = "bottom-right",
        scale: float = 0.26,
    ) -> None:
        self.directory = Path(directory)
        self.max_width = int(max_width)
        self.corner = corner
        self.scale = float(scale)
        self._cache: Dict[str, Optional[np.ndarray]] = {}

    # ------------------------------------------------------------------ #
    @property
    def available(self) -> bool:
        return self.directory.is_dir()

    def candidates(self, expression: str) -> List[Path]:
        """Every path that could satisfy ``expression``, best first."""
        names = _ALIASES.get(expression)
        if names is None:
            # Fall back to the canonical name and any documented alias.
            canonical = EXPRESSION_ALIASES.get(expression, expression)
            names = (expression, canonical)
        paths: List[Path] = []
        for name in names:
            for extension in _EXTENSIONS:
                paths.append(self.directory / f"{name}{extension}")
        return paths

    def image_for(self, expression: str) -> Optional[np.ndarray]:
        """Return the cached BGR image for ``expression``, or ``None``."""
        if expression in self._cache:
            return self._cache[expression]
        image: Optional[np.ndarray] = None
        for path in self.candidates(expression):
            if not path.is_file():
                continue
            loaded = cv2.imread(str(path), cv2.IMREAD_COLOR)
            if loaded is None:
                log.debug("Could not decode reaction image %s", path)
                continue
            if loaded.shape[1] > self.max_width:
                ratio = self.max_width / loaded.shape[1]
                loaded = cv2.resize(
                    loaded,
                    (self.max_width, max(1, int(loaded.shape[0] * ratio))),
                    interpolation=cv2.INTER_AREA,
                )
            image = loaded
            log.debug("Reaction for %s -> %s", expression, path.name)
            break
        self._cache[expression] = image
        return image

    def overlay_for(
        self, expression: str, score: float = 1.0, min_score: float = 0.35
    ) -> Optional[ReactionOverlay]:
        """Build an overlay for ``expression`` when it is confident enough."""
        if expression == "unknown" or score < min_score:
            return None
        image = self.image_for(expression)
        if image is None:
            return None
        definition = EXPRESSIONS.get(expression)
        return ReactionOverlay(
            expression=expression,
            image=image,
            corner=self.corner,
            scale=self.scale,
            label=definition.label_es if definition else expression,
        )

    def preload(self, expressions: Optional[List[str]] = None) -> int:
        """Warm the cache; returns how many images were found."""
        found = 0
        for name in expressions or list(EXPRESSIONS):
            if self.image_for(name) is not None:
                found += 1
        return found

    def describe(self) -> str:
        if not self.available:
            return f"reactions: directory {self.directory} not found"
        found = sum(1 for name in EXPRESSIONS if self.image_for(name) is not None)
        return f"reactions: {found}/{len(EXPRESSIONS)} expressions have an image in {self.directory}"
