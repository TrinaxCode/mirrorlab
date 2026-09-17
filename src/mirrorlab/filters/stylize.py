"""Stylised looks: thermal imaging, night vision, holograms and dreams."""

from __future__ import annotations

import cv2
import numpy as np

from .base import Filter, FilterContext, register_filter, sobel_magnitude, to_gray_bgr

__all__ = [
    "AnaglyphFilter",
    "DreamFilter",
    "HologramFilter",
    "LomoFilter",
    "MatrixFilter",
    "NightVisionFilter",
    "OrtonFilter",
    "SolarizeFilter",
    "ThermalFilter",
    "XRayFilter",
]


class ThermalFilter(Filter):
    name = "thermal"
    label = "Thermal"
    label_es = "Térmica"
    emoji = "🌡️"
    category = "stylize"
    cost = "cheap"
    description = "False-colour heat map driven by inverted luminance."
    description_es = "Mapa de calor en falso color a partir de la luminancia invertida."

    def __init__(self, palette: int = cv2.COLORMAP_INFERNO, invert: bool = True) -> None:
        super().__init__()
        self.palette = int(palette)
        self.invert = bool(invert)

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # Blur first: thermal cameras have low spatial resolution, and matching
        # that softness is what sells the effect.
        gray = cv2.GaussianBlur(gray, (7, 7), 0)
        if self.invert:
            gray = cv2.bitwise_not(gray)
        gray = cv2.equalizeHist(gray)
        colored = cv2.applyColorMap(gray, self.palette)
        return cv2.addWeighted(colored, 0.92, frame, 0.08, 0)


class NightVisionFilter(Filter):
    name = "night_vision"
    label = "Night vision"
    label_es = "Visión nocturna"
    emoji = "🌙"
    category = "stylize"
    cost = "medium"
    description = "Gen-II image intensifier: green phosphor, gain noise, bloom and a scope vignette."
    description_es = "Intensificador de imagen: fósforo verde, ruido, resplandor y viñeta de mira."

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        # Automatic gain control: normalise then push the exposure hard.
        gray = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
        gain = np.clip(gray * 1.35, 0, 255)

        # Sensor noise proportional to the signal, like real image intensifiers.
        rng = np.random.default_rng(ctx.frame_index % 9973)
        noise = rng.normal(0.0, 9.0, gain.shape).astype(np.float32)
        noisy = np.clip(gain + noise * (0.35 + gain / 255.0), 0, 255)

        bloom = cv2.GaussianBlur(noisy, (0, 0), 6.0)
        out = np.zeros((*noisy.shape, 3), dtype=np.float32)
        out[..., 1] = np.clip(noisy * 1.0 + bloom * 0.45, 0, 255)
        out[..., 0] = np.clip(noisy * 0.20 + bloom * 0.12, 0, 255)
        out[..., 2] = np.clip(noisy * 0.16 + bloom * 0.08, 0, 255)

        # Vignette + scanlines complete the tube look.
        height, width = out.shape[:2]
        ys = np.linspace(-1, 1, height, dtype=np.float32)[:, None]
        xs = np.linspace(-1, 1, width, dtype=np.float32)[None, :]
        vignette = np.clip(1.25 - 0.75 * (xs * xs + ys * ys), 0.15, 1.0)[..., None]
        return np.clip(out * vignette, 0, 255).astype(np.uint8)


class XRayFilter(Filter):
    name = "xray"
    label = "X-ray"
    label_es = "Rayos X"
    emoji = "🦴"
    category = "stylize"
    cost = "medium"
    description = "Inverted radiograph with bone-bright edges."
    description_es = "Radiografía invertida, con bordes brillantes."

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        gray, _ = to_gray_bgr(frame)
        edges = sobel_magnitude(gray)
        combined = cv2.addWeighted(gray, 0.55, edges, 0.75, 0)
        inverted = cv2.bitwise_not(combined)
        tinted = cv2.applyColorMap(inverted, cv2.COLORMAP_BONE)
        # Slight blue cast, like a lightbox.
        out = tinted.astype(np.float32)
        out[..., 0] = np.clip(out[..., 0] * 1.12, 0, 255)
        return out.astype(np.uint8)


class MatrixFilter(Filter):
    name = "matrix"
    label = "Matrix rain"
    label_es = "Lluvia Matrix"
    emoji = "🟩"
    category = "glitch"
    cost = "medium"
    description = "Falling katakana columns composited over a green-tinted feed."
    description_es = "Columnas de katakana cayendo sobre la imagen en verde."

    GLYPHS = "アイウエオカキクケコサシスセソタチツテトナニヌネノ0123456789ΨΩΔΣ"

    def __init__(self, columns: int = 90, speed: float = 1.0) -> None:
        super().__init__()
        self.columns = max(8, int(columns))
        self.speed = float(speed)

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        height, width = frame.shape[:2]
        state = self.state
        if "drops" not in state or state.get("width") != width:
            rng = np.random.default_rng(42)
            state["drops"] = rng.integers(0, height, size=self.columns).astype(np.float32)
            state["speeds"] = rng.uniform(6.0, 22.0, size=self.columns).astype(np.float32) * self.speed
            state["width"] = width

        drops: np.ndarray = state["drops"]  # type: ignore[assignment]
        speeds: np.ndarray = state["speeds"]  # type: ignore[assignment]
        cell_w = max(1, width // self.columns)
        drops += speeds * ctx.delta * 12.0
        drops[drops > height + 40] = -np.random.uniform(0, 200, size=int((drops > height + 40).sum()))

        # Green-tinted base.
        base = frame.astype(np.float32)
        base[..., 0] *= 0.35
        base[..., 1] = np.clip(base[..., 1] * 1.05 + 10, 0, 255)
        base[..., 2] *= 0.35

        canvas = base.astype(np.uint8)
        for index in range(self.columns):
            x = index * cell_w + 1
            y = int(drops[index])
            for tail in range(8):
                glyph_y = y - tail * cell_w
                if not (0 <= glyph_y < height - 4):
                    continue
                fade = 1.0 - tail / 8.0
                colour = (int(60 * fade), int(255 * fade), int(120 * fade))
                glyph = self.GLYPHS[(index * 7 + tail * 3 + ctx.frame_index // 6) % len(self.GLYPHS)]
                cv2.putText(canvas, glyph, (x, glyph_y), cv2.FONT_HERSHEY_PLAIN, 1.0, colour, 1, cv2.LINE_AA)
        return canvas


class HologramFilter(Filter):
    name = "hologram"
    label = "Hologram"
    label_es = "Holograma"
    emoji = "🔷"
    category = "stylize"
    cost = "medium"
    description = "Cyan wireframe projection with scanline flicker and a glitch bar."
    description_es = "Proyección de líneas cian con parpadeo y barra de fallo."

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        gray, _ = to_gray_bgr(frame)
        edges = cv2.Canny(cv2.GaussianBlur(gray, (3, 3), 0), 30, 90)

        canvas = np.zeros_like(frame)
        canvas[..., 0] = edges  # cyan in BGR
        canvas[..., 1] = (edges * 0.85).astype(np.uint8)
        canvas[..., 2] = (edges * 0.15).astype(np.uint8)

        glow = cv2.GaussianBlur(canvas, (0, 0), 5.0)
        out = cv2.addWeighted(canvas, 1.0, glow, 0.9, 0)

        # Horizontal scanline flicker.
        height = out.shape[0]
        lines = np.ones((height, 1, 1), dtype=np.float32)
        lines[::3] = 0.72
        out = (out.astype(np.float32) * lines).astype(np.uint8)

        # Occasional displacement bar, like a projector losing sync.
        if ctx.frame_index % 47 < 3:
            y0 = int((ctx.frame_index * 13) % max(1, height - 30))
            shift = int(18 * np.sin(ctx.time * 20))
            band = out[y0 : y0 + 24]
            out[y0 : y0 + 24] = np.roll(band, shift, axis=1)
        return out


class DreamFilter(Filter):
    name = "dream"
    label = "Dream"
    label_es = "Sueño"
    emoji = "☁️"
    category = "stylize"
    cost = "medium"
    description = "Soft-focus bloom with lifted blacks and pastel colour."
    description_es = "Resplandor suave con negros levantados y color pastel."

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        blurred = cv2.GaussianBlur(frame, (0, 0), 9.0)
        # Orton effect: screen the blurred copy back over the original.
        screen = 255 - cv2.multiply(255 - frame, 255 - blurred, scale=1 / 255.0)
        out = cv2.addWeighted(frame, 0.42, screen, 0.58, 0)
        out = cv2.addWeighted(out, 0.82, np.full_like(out, 236), 0.18, 0)
        out = cv2.convertScaleAbs(out, alpha=0.94, beta=14)
        return out


class LomoFilter(Filter):
    name = "lomo"
    label = "Lomo"
    label_es = "Lomo"
    emoji = "📷"
    category = "color"
    cost = "medium"
    description = "Saturated toy-camera look with crushed blacks and heavy vignette."
    description_es = "Cámara de juguete: saturación alta, negros duros y viñeta."

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV).astype(np.float32)
        hsv[..., 1] = np.clip(hsv[..., 1] * 1.75, 0, 255)
        vivid = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
        vivid = cv2.convertScaleAbs(vivid, alpha=1.15, beta=-18)

        height, width = vivid.shape[:2]
        ys = np.linspace(-1, 1, height, dtype=np.float32)[:, None]
        xs = np.linspace(-1, 1, width, dtype=np.float32)[None, :]
        vignette = np.clip(1.35 - 0.95 * (xs * xs + ys * ys), 0.0, 1.0)[..., None]
        return np.clip(vivid.astype(np.float32) * vignette, 0, 255).astype(np.uint8)


class OrtonFilter(Filter):
    name = "orton"
    label = "Orton"
    label_es = "Orton"
    emoji = "🌤️"
    category = "stylize"
    cost = "medium"
    description = "Landscape photographer's glow: blurred copy at 50 % screen."
    description_es = "El resplandor del paisajista: copia desenfocada al 50 %."

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        bright = cv2.convertScaleAbs(frame, alpha=1.0, beta=18)
        blurred = cv2.GaussianBlur(bright, (0, 0), 14.0)
        return cv2.addWeighted(frame, 0.5, blurred, 0.5, 0)


class SolarizeFilter(Filter):
    name = "solarize"
    label = "Solarize"
    label_es = "Solarizar"
    emoji = "🔆"
    category = "stylize"
    cost = "cheap"
    description = "Sabattier effect: tones past the midpoint invert."
    description_es = "Efecto Sabattier: los tonos pasados del medio se invierten."

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        lut = np.array([255 - i if i > 128 else i for i in range(256)], dtype=np.uint8)
        return cv2.LUT(frame, lut)


class AnaglyphFilter(Filter):
    name = "anaglyph"
    label = "3D anaglyph"
    label_es = "Anaglifo 3D"
    emoji = "🕶️"
    category = "stylize"
    cost = "cheap"
    description = "Red/cyan stereo split — grab some cardboard glasses."
    description_es = "Separación estéreo rojo/cian, para gafas de cartón."

    def __init__(self, shift: int = 6) -> None:
        super().__init__()
        self.shift = max(1, int(shift))

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        left = np.roll(frame, self.shift, axis=1)
        right = np.roll(frame, -self.shift, axis=1)
        out = np.zeros_like(frame)
        out[..., 0] = left[..., 0]  # blue channel from the left eye
        out[..., 1] = right[..., 1]  # green from the right
        out[..., 2] = right[..., 2]  # red from the right
        return out


for _filter in (
    ThermalFilter(),
    NightVisionFilter(),
    XRayFilter(),
    MatrixFilter(),
    HologramFilter(),
    DreamFilter(),
    LomoFilter(),
    OrtonFilter(),
    SolarizeFilter(),
    AnaglyphFilter(),
):
    register_filter(_filter)
