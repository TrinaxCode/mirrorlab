"""Utility filters: background control, privacy and framing helpers."""

from __future__ import annotations

from typing import Optional, Tuple

import cv2
import numpy as np

from .base import Filter, FilterContext, apply_mask_blur, register_filter

__all__ = [
    "BackgroundBlurFilter",
    "BackgroundReplaceFilter",
    "FaceCropFilter",
    "GridFilter",
    "MirrorFilter",
    "PrivacyFilter",
    "SmoothSkinFilter",
    "ZoomFilter",
]


def _mask_from_context(ctx: FilterContext) -> Optional[np.ndarray]:
    """Person mask deposited by the pipeline, if segmentation is enabled."""
    mask = ctx.state.get("person_mask")
    return mask if isinstance(mask, np.ndarray) else None


class BackgroundBlurFilter(Filter):
    name = "bg_blur"
    label = "Background blur"
    label_es = "Fondo desenfocado"
    emoji = "🌀"
    category = "utility"
    cost = "medium"
    needs_mask = True
    description = "Portrait-mode separation. Needs --segment to build the person mask."
    description_es = "Modo retrato. Requiere --segment para generar la máscara."

    def __init__(self, strength: int = 31) -> None:
        super().__init__()
        self.strength = max(3, int(strength) | 1)

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        return apply_mask_blur(frame, _mask_from_context(ctx), self.strength)


class BackgroundReplaceFilter(Filter):
    name = "bg_replace"
    label = "Background replace"
    label_es = "Fondo reemplazado"
    emoji = "🏞️"
    category = "utility"
    cost = "medium"
    needs_mask = True
    description = "Swaps the background for a gradient or a solid colour."
    description_es = "Cambia el fondo por un degradado o un color plano."

    def __init__(self, mode: str = "gradient", color: Tuple[int, int, int] = (60, 30, 18)) -> None:
        super().__init__()
        self.mode = mode
        self.color = color
        self._cache: Optional[np.ndarray] = None

    def _background(self, height: int, width: int) -> np.ndarray:
        if self._cache is not None and self._cache.shape[:2] == (height, width):
            return self._cache
        if self.mode == "solid":
            background = np.full((height, width, 3), self.color, dtype=np.uint8)
        else:
            # Vertical teal→violet gradient, drawn with NumPy for speed.
            top = np.array([90, 40, 20], dtype=np.float32)  # BGR deep teal
            bottom = np.array([150, 70, 120], dtype=np.float32)  # BGR violet
            ramp = np.linspace(0.0, 1.0, height, dtype=np.float32)[:, None, None]
            background = (top * (1 - ramp) + bottom * ramp).astype(np.uint8)
            background = np.repeat(background, width, axis=1)
        self._cache = background
        return background

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        mask = _mask_from_context(ctx)
        height, width = frame.shape[:2]
        background = self._background(height, width)
        if mask is None:
            return frame
        alpha = cv2.GaussianBlur(mask.astype(np.float32), (15, 15), 0)[..., None]
        return (frame * alpha + background.astype(np.float32) * (1.0 - alpha)).astype(np.uint8)


class PrivacyFilter(Filter):
    name = "privacy"
    label = "Privacy"
    label_es = "Privacidad"
    emoji = "🕵️"
    category = "utility"
    cost = "medium"
    needs_mask = True
    description = "Blurs the background so only you are readable — safe screen sharing."
    description_es = "Desenfoca el fondo: solo tú eres legible. Ideal para compartir pantalla."

    def __init__(self, strength: int = 45) -> None:
        super().__init__()
        self.strength = max(5, int(strength) | 1)

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        mask = _mask_from_context(ctx)
        if mask is None:
            # Without a mask, pixelate the whole frame: better safe than sorry.
            height, width = frame.shape[:2]
            small = cv2.resize(
                frame, (max(2, width // 24), max(2, height // 24)), interpolation=cv2.INTER_AREA
            )
            return cv2.resize(small, (width, height), interpolation=cv2.INTER_NEAREST)
        return apply_mask_blur(frame, mask, self.strength)


class MirrorFilter(Filter):
    name = "mirror"
    label = "Kaleido mirror"
    label_es = "Espejo"
    emoji = "🪞"
    category = "utility"
    cost = "cheap"
    description = "Mirrors the left half onto the right — instant symmetry."
    description_es = "Refleja la mitad izquierda sobre la derecha: simetría instantánea."

    def __init__(self, axis: str = "vertical") -> None:
        super().__init__()
        self.axis = axis

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        height, width = frame.shape[:2]
        out = frame.copy()
        if self.axis == "horizontal":
            half = height // 2
            out[half:] = cv2.flip(out[: height - half], 0)
        else:
            half = width // 2
            out[:, half:] = cv2.flip(out[:, : width - half], 1)
        return out


class ZoomFilter(Filter):
    name = "zoom"
    label = "Punch-in"
    label_es = "Zoom"
    emoji = "🔍"
    category = "utility"
    cost = "cheap"
    description = "Digital zoom with a smooth breathing motion."
    description_es = "Zoom digital con un suave movimiento de respiración."

    def __init__(self, factor: float = 1.35, animate: bool = False) -> None:
        super().__init__()
        self.factor = float(max(1.0, factor))
        self.animate = bool(animate)

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        height, width = frame.shape[:2]
        factor = self.factor
        if self.animate:
            factor *= 1.0 + 0.08 * np.sin(ctx.time * 1.2)
        crop_w = int(width / factor)
        crop_h = int(height / factor)
        x0 = (width - crop_w) // 2
        y0 = (height - crop_h) // 2
        crop = frame[y0 : y0 + crop_h, x0 : x0 + crop_w]
        return cv2.resize(crop, (width, height), interpolation=cv2.INTER_LINEAR)


class FaceCropFilter(Filter):
    name = "face_crop"
    label = "Auto face frame"
    label_es = "Encuadre automático"
    emoji = "🙂"
    category = "utility"
    cost = "cheap"
    description = "Keeps your face centred and correctly sized in frame."
    description_es = "Mantiene tu cara centrada y bien encuadrada."

    def __init__(self, target: float = 0.32) -> None:
        super().__init__()
        self.target = float(target)

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        face = ctx.state.get("face_bbox")
        height, width = frame.shape[:2]
        if not isinstance(face, (tuple, list)) or len(face) != 4:
            return frame
        x0, y0, x1, y1 = (float(v) for v in face)
        face_w, face_h = max(x1 - x0, 1.0), max(y1 - y0, 1.0)
        scale = float(np.clip(self.target * width / face_w, 1.0, 2.2))
        crop_w = int(width / scale)
        crop_h = int(height / scale)
        cx = int((x0 + x1) / 2)
        cy = int((y0 + y1) / 2 - face_h * 0.18)
        x_start = int(np.clip(cx - crop_w // 2, 0, width - crop_w))
        y_start = int(np.clip(cy - crop_h // 2, 0, height - crop_h))
        crop = frame[y_start : y_start + crop_h, x_start : x_start + crop_w]
        return cv2.resize(crop, (width, height), interpolation=cv2.INTER_LINEAR)


class GridFilter(Filter):
    name = "grid"
    label = "Rule of thirds"
    label_es = "Regla de tercios"
    emoji = "📐"
    category = "utility"
    cost = "cheap"
    description = "Composition guides for framing a shot."
    description_es = "Guías de composición para encuadrar la toma."

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        out = frame.copy()
        height, width = out.shape[:2]
        colour = (235, 235, 235)
        for fraction in (1 / 3, 2 / 3):
            x = int(width * fraction)
            y = int(height * fraction)
            cv2.line(out, (x, 0), (x, height), colour, 1, cv2.LINE_AA)
            cv2.line(out, (0, y), (width, y), colour, 1, cv2.LINE_AA)
        cv2.circle(out, (width // 2, height // 2), 12, colour, 1, cv2.LINE_AA)
        return out


class SmoothSkinFilter(Filter):
    name = "skin_smooth"
    label = "Skin smooth"
    label_es = "Piel suave"
    emoji = "🧖"
    category = "utility"
    cost = "medium"
    description = "Frequency-separation retouching: softens texture, keeps detail."
    description_es = "Separación de frecuencias: suaviza la textura y mantiene el detalle."

    def __init__(self, strength: float = 0.65) -> None:
        super().__init__()
        self.strength = float(np.clip(strength, 0.0, 1.0))

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        # Bilateral filter is the low-frequency layer; the difference carries
        # texture (pores, stubble) which we blend back at reduced opacity.
        smoothed = cv2.bilateralFilter(frame, 9, 60, 60)
        smoothed = cv2.bilateralFilter(smoothed, 9, 45, 45)
        detail = cv2.subtract(frame, smoothed)
        return cv2.addWeighted(smoothed, 1.0, detail, 1.0 - self.strength, 0)


for _filter in (
    BackgroundBlurFilter(),
    BackgroundReplaceFilter(),
    PrivacyFilter(),
    MirrorFilter(),
    ZoomFilter(),
    FaceCropFilter(),
    GridFilter(),
    SmoothSkinFilter(),
):
    register_filter(_filter)
