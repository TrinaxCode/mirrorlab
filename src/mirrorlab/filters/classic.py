"""Classic filters: tonal adjustments, colour grading and simple optics."""

from __future__ import annotations

from typing import Tuple

import cv2
import numpy as np

from .base import Filter, FilterContext, register_filter

__all__ = [
    "BlurFilter",
    "CyberpunkFilter",
    "DuotoneFilter",
    "EmbossFilter",
    "FisheyeFilter",
    "GrayscaleFilter",
    "InfraredFilter",
    "InvertFilter",
    "KaleidoscopeFilter",
    "OriginalFilter",
    "PosterizeFilter",
    "SaturationFilter",
    "SepiaFilter",
    "SharpenFilter",
    "VignetteFilter",
    "WarmthFilter",
]


class OriginalFilter(Filter):
    name = "original"
    label = "Original"
    label_es = "Original"
    emoji = "🎥"
    category = "basic"
    cost = "cheap"
    description = "The untouched camera feed."
    description_es = "La imagen original de la cámara, sin efectos."

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        return frame


class GrayscaleFilter(Filter):
    name = "grayscale"
    label = "Grayscale"
    label_es = "Escala de grises"
    emoji = "⚫"
    category = "basic"
    cost = "cheap"
    description = "Luminance-only rendering with a slight contrast lift."
    description_es = "Solo luminancia, con un ligero aumento de contraste."

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.convertScaleAbs(gray, alpha=1.08, beta=4)
        return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


class SepiaFilter(Filter):
    name = "sepia"
    label = "Sepia"
    label_es = "Sepia"
    emoji = "🟤"
    category = "basic"
    cost = "cheap"
    description = "Warm antique tone via a fixed colour matrix."
    description_es = "Tono cálido de foto antigua con una matriz de color fija."

    #: Classic sepia matrix, applied in BGR order.
    MATRIX = np.array(
        [
            [0.131, 0.534, 0.272],
            [0.168, 0.686, 0.349],
            [0.189, 0.769, 0.393],
        ],
        dtype=np.float32,
    )

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        out = cv2.transform(frame.astype(np.float32), self.MATRIX)
        return np.clip(out, 0, 255).astype(np.uint8)


class InvertFilter(Filter):
    name = "invert"
    label = "Negative"
    label_es = "Negativo"
    emoji = "🔳"
    category = "basic"
    cost = "cheap"
    description = "Photographic negative."
    description_es = "Negativo fotográfico."

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        return cv2.bitwise_not(frame)


class PosterizeFilter(Filter):
    name = "posterize"
    label = "Posterize"
    label_es = "Posterizar"
    emoji = "🧱"
    category = "basic"
    cost = "cheap"
    description = "Quantises each channel to a few flat levels — a screen-print look."
    description_es = "Reduce cada canal a pocos niveles planos, como una serigrafía."

    def __init__(self, levels: int = 6) -> None:
        super().__init__()
        self.levels = max(2, int(levels))
        step = 256 // self.levels
        ramp = (np.arange(256) // step * step + step // 2).clip(0, 255).astype(np.uint8)
        self._lut = ramp

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        return cv2.LUT(frame, self._lut)


class SharpenFilter(Filter):
    name = "sharpen"
    label = "Sharpen"
    label_es = "Enfocar"
    emoji = "🔪"
    category = "basic"
    cost = "cheap"
    description = "Unsharp mask that lifts local detail without halos."
    description_es = "Máscara de enfoque que realza el detalle sin halos."

    def __init__(self, amount: float = 0.8, radius: int = 5) -> None:
        super().__init__()
        self.amount = float(amount)
        self.radius = int(radius) | 1

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        blurred = cv2.GaussianBlur(frame, (self.radius, self.radius), 0)
        return cv2.addWeighted(frame, 1.0 + self.amount, blurred, -self.amount, 0)


class BlurFilter(Filter):
    name = "blur"
    label = "Soft focus"
    label_es = "Desenfoque"
    emoji = "💧"
    category = "basic"
    cost = "cheap"
    description = "Gaussian dream blur."
    description_es = "Desenfoque gaussiano tipo sueño."

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        return cv2.GaussianBlur(frame, (0, 0), 4.0)


class VignetteFilter(Filter):
    name = "vignette"
    label = "Vignette"
    label_es = "Viñeta"
    emoji = "⭕"
    category = "basic"
    cost = "cheap"
    description = "Darkened corners that pull the eye to the centre of frame."
    description_es = "Oscurece las esquinas para centrar la mirada."

    def __init__(self, strength: float = 1.35, radius: float = 0.78) -> None:
        super().__init__()
        self.strength = float(strength)
        self.radius = float(radius)
        self._cache: Tuple[int, int, np.ndarray] | None = None

    def _mask(self, height: int, width: int) -> np.ndarray:
        if self._cache is not None and self._cache[0] == height and self._cache[1] == width:
            return self._cache[2]
        ys = np.linspace(-1.0, 1.0, height, dtype=np.float32)[:, None]
        xs = np.linspace(-1.0, 1.0, width, dtype=np.float32)[None, :]
        distance = np.sqrt(xs * xs + ys * ys) / np.sqrt(2.0)
        mask = np.clip(1.0 - self.strength * np.clip(distance / self.radius - 0.35, 0, None) ** 1.6, 0.0, 1.0)
        mask = (mask * 255).astype(np.uint8)[..., None]
        self._cache = (height, width, mask)
        return mask

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        height, width = frame.shape[:2]
        mask = self._mask(height, width).astype(np.float32) / 255.0
        return (frame.astype(np.float32) * mask).astype(np.uint8)


class EmbossFilter(Filter):
    name = "emboss"
    label = "Emboss"
    label_es = "Relieve"
    emoji = "🗿"
    category = "basic"
    cost = "cheap"
    description = "Bas-relief edge shading that makes the image look carved."
    description_es = "Sombreado de bordes que da aspecto tallado."

    KERNEL = np.array([[-2, -1, 0], [-1, 1, 1], [0, 1, 2]], dtype=np.float32)

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        embossed = cv2.filter2D(gray, cv2.CV_32F, self.KERNEL)
        embossed = cv2.convertScaleAbs(embossed, alpha=1.0, beta=110)
        return cv2.cvtColor(embossed, cv2.COLOR_GRAY2BGR)


class KaleidoscopeFilter(Filter):
    name = "kaleidoscope"
    label = "Kaleidoscope"
    label_es = "Caleidoscopio"
    emoji = "🔮"
    category = "artistic"
    cost = "medium"
    description = "Mirrors the frame into N rotating wedges — pure wallpaper material."
    description_es = "Refleja el cuadro en N sectores giratorios, puro fondo de pantalla."

    def __init__(self, segments: int = 8, spin: float = 0.15) -> None:
        super().__init__()
        self.segments = max(2, int(segments))
        self.spin = float(spin)

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        height, width = frame.shape[:2]
        cx, cy = width / 2.0, height / 2.0
        angle = ctx.time * self.spin * 360.0 / max(self.segments, 1)
        wedge = 360.0 / self.segments

        # Build the inverse mapping analytically: for every output pixel find
        # the source pixel inside the first wedge.
        ys, xs = np.mgrid[0:height, 0:width].astype(np.float32)
        dx, dy = xs - cx, ys - cy
        radius = np.sqrt(dx * dx + dy * dy)
        theta = (np.degrees(np.arctan2(dy, dx)) + angle) % wedge
        theta = np.where(theta > wedge / 2.0, wedge - theta, theta)
        radians = np.radians(theta)
        map_x = (cx + radius * np.cos(radians)).astype(np.float32)
        map_y = (cy + radius * np.sin(radians)).astype(np.float32)
        out = cv2.remap(frame, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        # Soft seam mask so wedge joints do not look like hard cuts.
        return cv2.addWeighted(out, 0.94, frame, 0.06, 0)


class DuotoneFilter(Filter):
    name = "duotone"
    label = "Duotone"
    label_es = "Duotono"
    emoji = "🎭"
    category = "color"
    cost = "cheap"
    description = "Maps luminance onto a two-colour ramp."
    description_es = "Convierte la luminancia en una gama de dos colores."

    def __init__(
        self, shadow: Tuple[int, int, int] = (120, 40, 20), light: Tuple[int, int, int] = (90, 220, 250)
    ) -> None:
        super().__init__()
        self.shadow = shadow
        self.light = light
        ramp = np.zeros((256, 1, 3), dtype=np.uint8)
        for i in range(256):
            t = i / 255.0
            ramp[i, 0] = [int(self.shadow[c] * (1 - t) + self.light[c] * t) for c in range(3)]
        self._lut = ramp

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # A 3-channel LUT needs a 3-channel input, so expand first.
        return cv2.LUT(cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR), self._lut)


class CyberpunkFilter(Filter):
    name = "cyberpunk"
    label = "Cyberpunk"
    label_es = "Cyberpunk"
    emoji = "🌆"
    category = "color"
    cost = "medium"
    description = "Teal shadows, orange highlights and a neon bloom."
    description_es = "Sombras turquesa, luces naranjas y un resplandor neón."

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        image = frame.astype(np.float32) / 255.0
        luminance = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
        shadow_tint = np.array([0.75, 0.45, 0.20], dtype=np.float32)  # BGR teal
        light_tint = np.array([0.25, 0.65, 1.15], dtype=np.float32)  # BGR orange
        graded = image * (shadow_tint * (1 - luminance[..., None]) + light_tint * luminance[..., None])
        graded = np.clip(graded, 0, 1)

        # Bloom: blur the brightest areas and screen them back on.
        bright = np.clip((graded - 0.72) / 0.28, 0, 1)
        bloom = cv2.GaussianBlur(bright, (0, 0), 9.0)
        out = np.clip(graded + bloom * 0.55, 0, 1)
        return (out * 255).astype(np.uint8)


class WarmthFilter(Filter):
    name = "warmth"
    label = "Golden hour"
    label_es = "Hora dorada"
    emoji = "🌅"
    category = "color"
    cost = "cheap"
    description = "Warm, slightly lifted shadows — flattering on every skin tone."
    description_es = "Cálido y con sombras levantadas; favorece a cualquier tono de piel."

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        out = frame.astype(np.float32)
        out[..., 0] *= 0.88  # less blue
        out[..., 1] *= 1.02
        out[..., 2] *= 1.12  # more red
        out = cv2.add(out, np.array([-6.0, 4.0, 12.0], dtype=np.float32))
        return np.clip(out, 0, 255).astype(np.uint8)


class SaturationFilter(Filter):
    name = "saturation"
    label = "Vivid"
    label_es = "Vívido"
    emoji = "🎨"
    category = "color"
    cost = "cheap"
    description = "Punchy saturation boost in HSV space."
    description_es = "Aumento de saturación en el espacio HSV."

    def __init__(self, gain: float = 1.45) -> None:
        super().__init__()
        self.gain = float(gain)

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV).astype(np.float32)
        hsv[..., 1] = np.clip(hsv[..., 1] * self.gain, 0, 255)
        hsv[..., 2] = np.clip(hsv[..., 2] * 1.04, 0, 255)
        return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)


class InfraredFilter(Filter):
    name = "infrared"
    label = "Infrared"
    label_es = "Infrarrojo"
    emoji = "🩻"
    category = "color"
    cost = "medium"
    description = "Aerochrome-style false colour: foliage glows pink, skin goes porcelain."
    description_es = "Falso color tipo Aerochrome: la vegetación brilla rosada."

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        b, g, r = cv2.split(frame.astype(np.float32))
        out = cv2.merge(
            [
                np.clip(b * 0.55 + g * 0.45, 0, 255),  # B
                np.clip(g * 0.80 + r * 0.10, 0, 255),  # G
                np.clip(r * 0.35 + g * 1.05, 0, 255),  # R ← green bleeds into red
            ]
        ).astype(np.uint8)
        return cv2.addWeighted(out, 0.9, frame, 0.1, 0)


class FisheyeFilter(Filter):
    name = "fisheye"
    label = "Fisheye"
    label_es = "Ojo de pez"
    emoji = "🐟"
    category = "artistic"
    cost = "medium"
    description = "Barrel distortion straight out of a skate video."
    description_es = "Distorsión de barril, estilo vídeo de skate."

    def __init__(self, strength: float = 0.35) -> None:
        super().__init__()
        self.strength = float(strength)
        self._cache: Tuple[int, int, np.ndarray, np.ndarray] | None = None

    def _maps(self, height: int, width: int):
        if self._cache and self._cache[0] == height and self._cache[1] == width:
            return self._cache[2], self._cache[3]
        ys, xs = np.mgrid[0:height, 0:width].astype(np.float32)
        cx, cy = width / 2.0, height / 2.0
        nx = (xs - cx) / cx
        ny = (ys - cy) / cy
        r2 = nx * nx + ny * ny
        factor = 1.0 + self.strength * r2
        map_x = (cx + nx * factor * cx).astype(np.float32)
        map_y = (cy + ny * factor * cy).astype(np.float32)
        self._cache = (height, width, map_x, map_y)
        return map_x, map_y

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        height, width = frame.shape[:2]
        map_x, map_y = self._maps(height, width)
        return cv2.remap(frame, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


for _filter in (
    OriginalFilter(),
    GrayscaleFilter(),
    SepiaFilter(),
    InvertFilter(),
    PosterizeFilter(),
    SharpenFilter(),
    BlurFilter(),
    VignetteFilter(),
    EmbossFilter(),
    KaleidoscopeFilter(),
    DuotoneFilter(),
    CyberpunkFilter(),
    WarmthFilter(),
    SaturationFilter(),
    InfraredFilter(),
    FisheyeFilter(),
):
    register_filter(_filter)
