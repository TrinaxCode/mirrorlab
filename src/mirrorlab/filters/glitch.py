"""Glitch and retro filters: datamosh, VHS, CRT and chromatic aberration."""

from __future__ import annotations

from typing import Tuple

import cv2
import numpy as np

from .base import Filter, FilterContext, register_filter

__all__ = [
    "ChromaticFilter",
    "CrtFilter",
    "DatamoshFilter",
    "GlitchFilter",
    "ScanlinesFilter",
    "SlitScanFilter",
    "TrailsFilter",
    "VhsFilter",
]


class GlitchFilter(Filter):
    name = "glitch"
    label = "Glitch"
    label_es = "Glitch"
    emoji = "⚡"
    category = "glitch"
    cost = "medium"
    description = "Databend-style block displacement, RGB shear and dropout noise."
    description_es = "Bloques desplazados, separación RGB y ruido de caída de señal."

    def __init__(self, intensity: float = 0.45, seed: int = 0) -> None:
        super().__init__()
        self.intensity = float(max(0.0, min(1.0, intensity)))
        self.seed = int(seed)

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        height, width = frame.shape[:2]
        out = frame.copy()
        # A deterministic RNG per frame keeps the effect reproducible in tests
        # while still looking chaotic.
        rng = np.random.default_rng(self.seed + ctx.frame_index * 2654435761 % (2**32))

        # 1. Horizontal slice displacement.
        slices = int(4 + self.intensity * 16)
        for _ in range(slices):
            y = int(rng.integers(0, height - 4))
            band = int(rng.integers(4, max(6, height // 6)))
            shift = int(rng.normal(0, 22 * self.intensity + 2))
            y1 = min(height, y + band)
            out[y:y1] = np.roll(out[y:y1], shift, axis=1)

        # 2. Channel shear — the signature "broken codec" look.
        shear = int(2 + self.intensity * 10)
        b, g, r = cv2.split(out)
        out = cv2.merge(
            [
                np.roll(b, shear, axis=1),
                g,
                np.roll(r, -shear, axis=1),
            ]
        )

        # 3. Dropout blocks: copy rectangles from elsewhere in the frame.
        blocks = int(2 + self.intensity * 6)
        for _ in range(blocks):
            bw = int(rng.integers(width // 12, max(width // 12 + 1, width // 4)))
            bh = int(rng.integers(6, max(7, height // 12)))
            x = int(rng.integers(0, max(1, width - bw)))
            y = int(rng.integers(0, max(1, height - bh)))
            sx = int(rng.integers(0, max(1, width - bw)))
            sy = int(rng.integers(0, max(1, height - bh)))
            out[y : y + bh, x : x + bw] = frame[sy : sy + bh, sx : sx + bw]

        # 4. Sparse white noise.
        if self.intensity > 0.15:
            noise = rng.random((height, width, 1)) < (0.006 * self.intensity * 10)
            out[noise.repeat(3, axis=2)] = 255
        return out


class ChromaticFilter(Filter):
    name = "chromatic"
    label = "Chromatic aberration"
    label_es = "Aberración cromática"
    emoji = "🔴"
    category = "glitch"
    cost = "cheap"
    description = "Lens-style radial colour fringing, strongest at the edges."
    description_es = "Franjas de color radiales, más fuertes en los bordes."

    def __init__(self, strength: float = 1.5) -> None:
        super().__init__()
        self.strength = float(strength)

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        height, width = frame.shape[:2]
        cx, cy = width / 2.0, height / 2.0
        ys, xs = np.mgrid[0:height, 0:width].astype(np.float32)
        dx = (xs - cx) / cx
        dy = (ys - cy) / cy
        amount = self.strength * (1.0 + 0.25 * np.sin(ctx.time * 0.7))

        channels = []
        for index, direction in enumerate((1.0, 0.0, -1.0)):  # B, G, R
            map_x = (cx + (dx * (1.0 + direction * amount * 0.004)) * cx).astype(np.float32)
            map_y = (cy + (dy * (1.0 + direction * amount * 0.004)) * cy).astype(np.float32)
            channel = cv2.remap(
                frame[..., index], map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE
            )
            channels.append(channel)
        return cv2.merge(channels)


class VhsFilter(Filter):
    name = "vhs"
    label = "VHS"
    label_es = "VHS"
    emoji = "📼"
    category = "glitch"
    cost = "medium"
    description = "Tracking noise, colour bleed, tape wobble and a timecode stamp."
    description_es = "Ruido de seguimiento, sangrado de color, ondulación y timecode."

    def __init__(self, show_timecode: bool = True) -> None:
        super().__init__()
        self.show_timecode = bool(show_timecode)

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        height, width = frame.shape[:2]
        rng = np.random.default_rng(ctx.frame_index // 2 + 991)

        # 1. Tape wobble: a slow horizontal sine displacement per row.
        ys, xs = np.mgrid[0:height, 0:width].astype(np.float32)
        wobble = np.sin(ys * 0.06 + ctx.time * 6.0) * 1.6
        map_x = np.clip(xs + wobble, 0, width - 1).astype(np.float32)
        map_y = ys.astype(np.float32)
        out = cv2.remap(frame, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)

        # 2. Colour bleed: chroma is smeared horizontally far more than luma.
        ycrcb = cv2.cvtColor(out, cv2.COLOR_BGR2YCrCb).astype(np.float32)
        ycrcb[..., 1] = cv2.GaussianBlur(ycrcb[..., 1], (13, 3), 0)
        ycrcb[..., 2] = cv2.GaussianBlur(ycrcb[..., 2], (13, 3), 0)
        out = cv2.cvtColor(np.clip(ycrcb, 0, 255).astype(np.uint8), cv2.COLOR_YCrCb2BGR)

        # 3. Dropout: a bright horizontal streak near the bottom.
        if rng.random() < 0.25:
            y = int(rng.integers(int(height * 0.72), height - 6))
            out[y : y + 3] = np.clip(out[y : y + 3].astype(np.int16) + 55, 0, 255).astype(np.uint8)

        # 4. Luma noise + slight desaturation, then soften.
        noise = rng.normal(0, 7.0, (height, width, 1)).astype(np.float32)
        out = np.clip(out.astype(np.float32) + noise, 0, 255).astype(np.uint8)
        out = cv2.addWeighted(
            out, 0.86, cv2.cvtColor(cv2.cvtColor(out, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR), 0.14, 0
        )

        if self.show_timecode:
            stamp = f"REC  {ctx.frame_index // 30:02d}:{(ctx.frame_index // 30) % 60:02d}:{ctx.frame_index % 30:02d}"
            cv2.putText(
                out, "PLAY ▶", (24, 42), cv2.FONT_HERSHEY_DUPLEX, 0.7, (240, 240, 240), 2, cv2.LINE_AA
            )
            cv2.putText(
                out, stamp, (24, height - 26), cv2.FONT_HERSHEY_DUPLEX, 0.7, (240, 240, 240), 2, cv2.LINE_AA
            )
        return out


class CrtFilter(Filter):
    name = "crt"
    label = "CRT monitor"
    label_es = "Monitor CRT"
    emoji = "🖥️"
    category = "glitch"
    cost = "medium"
    description = "Aperture-grille subpixels, scanlines, barrel glass and a rolling bar."
    description_es = "Subpíxeles, líneas de barrido, cristal curvo y barra rodante."

    def __init__(self, curvature: float = 0.12) -> None:
        super().__init__()
        self.curvature = float(curvature)
        self._cache: Tuple[int, int, np.ndarray, np.ndarray] | None = None

    def _maps(self, height: int, width: int):
        if self._cache and self._cache[0] == height and self._cache[1] == width:
            return self._cache[2], self._cache[3]
        ys, xs = np.mgrid[0:height, 0:width].astype(np.float32)
        cx, cy = width / 2.0, height / 2.0
        nx = (xs - cx) / cx
        ny = (ys - cy) / cy
        # Pincushion/barrel: pull the borders inward so the glass looks convex.
        factor = 1.0 + self.curvature * (nx * nx + ny * ny) * 0.5
        map_x = (cx + nx * factor * cx).astype(np.float32)
        map_y = (cy + ny * factor * cy).astype(np.float32)
        self._cache = (height, width, map_x, map_y)
        return map_x, map_y

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        height, width = frame.shape[:2]
        map_x, map_y = self._maps(height, width)
        out = cv2.remap(
            frame, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0)
        )
        out = out.astype(np.float32)

        # Aperture grille: weight the three channel columns differently.
        cols = np.arange(width) % 3
        for channel, column in enumerate((2, 1, 0)):  # B, G, R
            out[..., channel] *= np.where(cols == column, 1.0, 0.62)

        # Scanlines.
        rows = np.ones((height, 1), dtype=np.float32)
        rows[::2] = 0.78
        out *= rows[..., None]

        # Slow rolling brightness bar.
        bar_y = (ctx.frame_index * 3) % (height + 120) - 60
        bar = np.exp(-((np.arange(height) - bar_y) ** 2) / (2 * 45.0**2)).astype(np.float32)
        out *= (1.0 + 0.16 * bar)[:, None, None]

        # Phosphor bloom.
        glow = cv2.GaussianBlur(out, (0, 0), 3.0)
        out = np.clip(out + glow * 0.35, 0, 255)
        return out.astype(np.uint8)


class DatamoshFilter(Filter):
    name = "datamosh"
    label = "Datamosh"
    label_es = "Datamosh"
    emoji = "🧬"
    category = "glitch"
    cost = "medium"
    description = "Motion vectors smear the previous frame's pixels — broken P-frames."
    description_es = "Los vectores de movimiento embadurnan el cuadro anterior."

    def __init__(self, persistence: float = 0.72) -> None:
        super().__init__()
        self.persistence = float(np.clip(persistence, 0.0, 0.98))

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        previous = self.state.get("previous")
        flow_state = self.state.get("flow")

        if previous is None or previous.shape != frame.shape:
            self.state["previous"] = frame.copy()
            self.state["flow"] = None
            return frame

        # Estimate motion at low resolution (fast) and upscale the vectors.
        small_prev = cv2.resize(previous, (0, 0), fx=0.25, fy=0.25)
        small_now = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
        gray_prev = cv2.cvtColor(small_prev, cv2.COLOR_BGR2GRAY)
        gray_now = cv2.cvtColor(small_now, cv2.COLOR_BGR2GRAY)
        flow = cv2.calcOpticalFlowFarneback(gray_prev, gray_now, flow_state, 0.5, 3, 15, 3, 5, 1.2, 0)
        full_flow = cv2.resize(flow, (frame.shape[1], frame.shape[0])) * 4.0

        height, width = frame.shape[:2]
        ys, xs = np.mgrid[0:height, 0:width].astype(np.float32)
        map_x = np.clip(xs + full_flow[..., 0], 0, width - 1)
        map_y = np.clip(ys + full_flow[..., 1], 0, height - 1)
        warped = cv2.remap(previous, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)

        out = cv2.addWeighted(warped, self.persistence, frame, 1.0 - self.persistence, 0)
        self.state["previous"] = out.copy()
        self.state["flow"] = flow
        return out


class ScanlinesFilter(Filter):
    name = "scanlines"
    label = "Scanlines"
    label_es = "Líneas de barrido"
    emoji = "〰️"
    category = "glitch"
    cost = "cheap"
    description = "Subtle interlacing plus a light horizontal drift."
    description_es = "Entrelazado sutil con una ligera deriva horizontal."

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        height = frame.shape[0]
        mask = np.ones((height, 1, 1), dtype=np.float32)
        mask[::2] = 0.68
        drift = np.sin(ctx.time * 2.0) * 1.2
        matrix = np.float32([[1, 0, drift], [0, 1, 0]])
        shifted = cv2.warpAffine(frame, matrix, (frame.shape[1], height), borderMode=cv2.BORDER_REPLICATE)
        return np.clip(shifted.astype(np.float32) * mask, 0, 255).astype(np.uint8)


class TrailsFilter(Filter):
    name = "trails"
    label = "Echo trails"
    label_es = "Estelas"
    emoji = "👻"
    category = "glitch"
    cost = "cheap"
    description = "Feedback delay that leaves ghosts of everything that moves."
    description_es = "Retardo de realimentación que deja fantasmas de lo que se mueve."

    def __init__(self, decay: float = 0.78, offset: int = 3) -> None:
        super().__init__()
        self.decay = float(np.clip(decay, 0.0, 0.97))
        self.offset = int(offset)

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        previous = self.state.get("buffer")
        if previous is None or previous.shape != frame.shape:
            self.state["buffer"] = frame.copy()
            return frame
        shifted = np.roll(previous, self.offset, axis=1)
        blended = cv2.addWeighted(frame, 1.0 - self.decay, shifted, self.decay, 0)
        self.state["buffer"] = blended.copy()
        return blended


class SlitScanFilter(Filter):
    name = "slitscan"
    label = "Slit-scan"
    label_es = "Escáner de rendija"
    emoji = "🌌"
    category = "glitch"
    cost = "cheap"
    description = "Each frame contributes one column — time becomes space."
    description_es = "Cada cuadro aporta una columna: el tiempo se vuelve espacio."

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        _height, width = frame.shape[:2]
        canvas = self.state.get("canvas")
        if canvas is None or canvas.shape != frame.shape:
            canvas = frame.copy()
        column = (ctx.frame_index * 3) % width
        canvas[:, column : column + 3] = frame[:, column : column + 3]
        self.state["canvas"] = canvas
        # Return a copy, never the live buffer: callers (the HUD, the recorder,
        # the transition cross-fade) hold on to the frame they were given, and
        # handing them an array we mutate next frame silently rewrites history.
        return canvas.copy()


for _filter in (
    GlitchFilter(),
    ChromaticFilter(),
    VhsFilter(),
    CrtFilter(),
    DatamoshFilter(),
    ScanlinesFilter(),
    TrailsFilter(),
    SlitScanFilter(),
):
    register_filter(_filter)
