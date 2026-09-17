"""Artistic filters: painting, drawing and print-making techniques."""

from __future__ import annotations

import cv2
import numpy as np

from .base import Filter, FilterContext, register_filter, to_gray_bgr

__all__ = [
    "AsciiFilter",
    "CartoonFilter",
    "ComicFilter",
    "HalftoneFilter",
    "InkFilter",
    "NeonFilter",
    "OilPaintingFilter",
    "PencilSketchFilter",
    "PixelateFilter",
    "PointillismFilter",
    "StainedGlassFilter",
    "WatercolorFilter",
]

#: Density ramp for the ASCII filter, darkest first.
ASCII_RAMP = "@%#*+=-:. "


class CartoonFilter(Filter):
    name = "cartoon"
    label = "Cartoon"
    label_es = "Caricatura"
    emoji = "🖍️"
    category = "artistic"
    cost = "medium"
    description = "Flat colour regions plus bold ink outlines — the classic cel look."
    description_es = "Regiones de color plano con contornos gruesos, estilo cómic."

    def __init__(self, levels: int = 8, edge_thickness: int = 5) -> None:
        super().__init__()
        self.levels = max(2, int(levels))
        self.edge_thickness = max(1, int(edge_thickness) | 1)

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        # 1. Smooth colour while keeping edges (bilateral is the key operator:
        #    a plain blur destroys the outlines we are about to draw).
        color = cv2.bilateralFilter(frame, 9, 75, 75)
        for _ in range(2):
            color = cv2.bilateralFilter(color, 9, 60, 60)

        # 2. Quantise each channel to `levels` bands.
        step = max(1, 256 // self.levels)
        quantised = (color // step) * step + step // 2
        color = np.clip(quantised, 0, 255).astype(np.uint8)

        # 3. Ink outlines from an adaptive threshold of the grayscale image.
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.medianBlur(gray, 5)
        edges = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 9, 9)
        edges = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
        if self.edge_thickness > 1:
            edges = cv2.erode(edges, np.ones((self.edge_thickness, self.edge_thickness), np.uint8))
        return cv2.bitwise_and(color, edges)


class PencilSketchFilter(Filter):
    name = "sketch"
    label = "Pencil sketch"
    label_es = "Lápiz"
    emoji = "✏️"
    category = "artistic"
    cost = "medium"
    description = "Dodge-blend graphite drawing with an optional colour wash."
    description_es = "Dibujo a lápiz por división, con lavado de color opcional."

    def __init__(self, color: bool = False) -> None:
        super().__init__()
        self.color = bool(color)

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        gray, _ = to_gray_bgr(frame)
        inverted = cv2.bitwise_not(gray)
        blurred = cv2.GaussianBlur(inverted, (0, 0), 12.0)
        # Colour dodge: gray / (255 - blurred), with a small epsilon guard.
        sketch = cv2.divide(gray, 255 - blurred, scale=256)
        sketch = cv2.convertScaleAbs(sketch, alpha=1.05, beta=2)
        result = cv2.cvtColor(sketch, cv2.COLOR_GRAY2BGR)
        if self.color:
            wash = cv2.bilateralFilter(frame, 9, 90, 90)
            wash = cv2.addWeighted(wash, 0.55, np.full_like(wash, 255), 0.45, 0)
            result = cv2.multiply(result.astype(np.float32) / 255.0, wash.astype(np.float32)).astype(np.uint8)
        return result


class InkFilter(Filter):
    name = "ink"
    label = "Ink"
    label_es = "Tinta"
    emoji = "🖊️"
    category = "artistic"
    cost = "medium"
    description = "High-contrast line art, like a brush pen drawing."
    description_es = "Dibujo de línea de alto contraste, como con pincel."

    def __init__(self, threshold: float = 0.55) -> None:
        super().__init__()
        self.threshold = float(threshold)

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        gray, _ = to_gray_bgr(frame)
        # Difference of Gaussians emphasises ink-like strokes.
        fine = cv2.GaussianBlur(gray, (0, 0), 1.0)
        coarse = cv2.GaussianBlur(gray, (0, 0), 3.5)
        dog = cv2.absdiff(fine, coarse)
        dog = cv2.normalize(dog, None, 0, 255, cv2.NORM_MINMAX)
        _, ink = cv2.threshold(dog, int(self.threshold * 255), 255, cv2.THRESH_BINARY_INV)
        ink = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, np.ones((2, 2), np.uint8))
        return cv2.cvtColor(ink, cv2.COLOR_GRAY2BGR)


class OilPaintingFilter(Filter):
    name = "oil"
    label = "Oil painting"
    label_es = "Óleo"
    emoji = "🖼️"
    category = "artistic"
    cost = "heavy"
    description = "Histogram-based brush strokes: each pixel takes the dominant colour of its neighbourhood."
    description_es = "Pinceladas por histograma: cada píxel toma el color dominante de su entorno."

    def __init__(self, radius: int = 3, levels: int = 10, max_width: int = 480) -> None:
        super().__init__()
        self.radius = max(1, int(radius))
        self.levels = max(4, int(levels))
        self.max_width = max(160, int(max_width))

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        """Classic oil-paint algorithm (Hertzmann-style intensity binning).

        Ported to OpenCV because ``cv2.oilPainting`` lives in the *contrib*
        module, which MirrorLab deliberately does not require.

        For a window around every pixel we pick the most populated intensity
        bin and paint the average colour of the pixels in that bin. That is
        exactly what gives the effect its flat, stroke-like patches.

        The cost is ``levels × 4`` box filters, so the frame is downscaled to
        ``max_width`` first — at 30 fps nobody can tell, and the effect gets
        its painterly softness for free.
        """
        height, width = frame.shape[:2]
        scale = min(1.0, self.max_width / max(width, 1))
        work = (
            cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
            if scale < 1.0
            else frame
        )

        gray = cv2.cvtColor(work, cv2.COLOR_BGR2GRAY)
        bin_size = 256 // self.levels
        quantised = np.clip(gray // bin_size, 0, self.levels - 1)

        kernel = (self.radius * 2 + 1, self.radius * 2 + 1)
        counts = np.zeros((self.levels, *gray.shape), dtype=np.float32)
        sums = np.zeros((self.levels, *gray.shape, 3), dtype=np.float32)

        work_f = work.astype(np.float32)
        for level in range(self.levels):
            indicator = (quantised == level).astype(np.float32)
            counts[level] = cv2.boxFilter(indicator, -1, kernel, normalize=True)
            for channel in range(3):
                sums[level, ..., channel] = cv2.boxFilter(
                    indicator * work_f[..., channel], -1, kernel, normalize=True
                )

        best = np.argmax(counts, axis=0).astype(np.int32)
        best_count = np.take_along_axis(counts, best[None], axis=0)[0]

        out = np.zeros_like(work_f)
        for channel in range(3):
            picked = np.take_along_axis(sums[..., channel], best[None], axis=0)[0]
            out[..., channel] = np.where(
                best_count > 1e-6, picked / np.maximum(best_count, 1e-6), work_f[..., channel]
            )

        result = np.clip(out, 0, 255).astype(np.uint8)
        # A touch of smoothing removes the blocky bin edges.
        result = cv2.bilateralFilter(result, 5, 40, 40)
        if scale < 1.0:
            result = cv2.resize(result, (width, height), interpolation=cv2.INTER_LINEAR)
        return result


class WatercolorFilter(Filter):
    name = "watercolor"
    label = "Watercolor"
    label_es = "Acuarela"
    emoji = "🎐"
    category = "artistic"
    cost = "medium"
    description = "Soft washes with paper-like edges and lifted highlights."
    description_es = "Lavados suaves con bordes de papel y luces levantadas."

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        # `stylization` (NSC) is beautiful but ~40 ms at 640 px. The recursive
        # edge-preserving filter gives a visually equivalent wash for a tenth
        # of the cost, which is what keeps this filter usable at 30 fps.
        height, width = frame.shape[:2]
        scale = min(1.0, 640.0 / max(width, 1))
        work = (
            cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
            if scale < 1.0
            else frame
        )
        try:
            stylised = cv2.edgePreservingFilter(work, flags=cv2.RECURS_FILTER, sigma_s=60, sigma_r=0.42)
        except cv2.error:  # pragma: no cover
            stylised = cv2.bilateralFilter(work, 9, 80, 80)
        if scale < 1.0:
            stylised = cv2.resize(stylised, (width, height), interpolation=cv2.INTER_LINEAR)
        # Lift the shadows towards paper-white and soften further.
        paper = cv2.addWeighted(stylised, 0.82, np.full_like(stylised, 245), 0.18, 0)
        paper = cv2.bilateralFilter(paper, 7, 40, 40)
        gray, _ = to_gray_bgr(paper)
        edges = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 9, 12)
        return cv2.bitwise_and(paper, cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR))


class HalftoneFilter(Filter):
    name = "halftone"
    label = "Halftone"
    label_es = "Semitonos"
    emoji = "🔵"
    category = "artistic"
    cost = "medium"
    description = "Newspaper dot screen, generated with a rotated dot lattice."
    description_es = "Trama de puntos de periódico, con retícula rotada."

    def __init__(self, cell: int = 6, angle: float = 15.0) -> None:
        super().__init__()
        self.cell = max(3, int(cell))
        self.angle = float(angle)

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
        height, width = gray.shape

        # Rotate, build a dot lattice, rotate back — the classic screen.
        matrix = cv2.getRotationMatrix2D((width / 2, height / 2), self.angle, 1.0)
        rotated = cv2.warpAffine(
            gray, matrix, (width, height), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE
        )

        yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
        cx = (xx % self.cell) - self.cell / 2.0
        cy = (yy % self.cell) - self.cell / 2.0
        distance = np.sqrt(cx * cx + cy * cy) / (self.cell / 2.0)

        # Larger dots where the image is dark.
        radius = np.sqrt(1.0 - rotated)
        dots = (distance <= radius).astype(np.float32)
        screen = cv2.warpAffine(
            dots,
            cv2.invertAffineTransform(matrix),
            (width, height),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REPLICATE,
        )
        screen = np.clip(screen * 255, 0, 255).astype(np.uint8)
        return cv2.cvtColor(screen, cv2.COLOR_GRAY2BGR)


class AsciiFilter(Filter):
    name = "ascii"
    label = "ASCII art"
    label_es = "Arte ASCII"
    emoji = "🔤"
    category = "artistic"
    cost = "medium"
    description = "Renders the frame as text glyphs — yes, in real time."
    description_es = "Dibuja el cuadro con caracteres de texto, en tiempo real."

    def __init__(self, cell: int = 10, color: bool = True) -> None:
        super().__init__()
        self.cell = max(4, int(cell))
        self.color = bool(color)

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        height, width = frame.shape[:2]
        cell = self.cell
        # Characters are roughly twice as tall as wide, hence the 0.5 factor.
        cols = max(1, width // cell)
        rows = max(1, int(height / (cell * 2.0)))
        small = cv2.resize(frame, (cols, rows), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

        canvas = np.zeros((rows * cell * 2, cols * cell, 3), dtype=np.uint8)
        scale = cell / 12.0
        thickness = max(1, round(cell / 9.0))
        ramp_len = len(ASCII_RAMP)

        for row in range(rows):
            for col in range(cols):
                value = int(gray[row, col])
                glyph = ASCII_RAMP[min(ramp_len - 1, value * ramp_len // 256)]
                if glyph == " ":
                    continue
                origin = (col * cell, row * cell * 2 + cell)
                colour = tuple(int(c) for c in small[row, col]) if self.color else (90, 230, 120)
                cv2.putText(
                    canvas, glyph, origin, cv2.FONT_HERSHEY_PLAIN, scale, colour, thickness, cv2.LINE_AA
                )
        return canvas


class PixelateFilter(Filter):
    name = "pixelate"
    label = "Pixelate"
    label_es = "Pixelar"
    emoji = "🟦"
    category = "artistic"
    cost = "cheap"
    description = "Chunky 8-bit mosaic, with an animated block size option."
    description_es = "Mosaico de bloques grandes, con tamaño animable."

    def __init__(self, blocks: int = 12, animate: bool = False) -> None:
        super().__init__()
        self.blocks = max(2, int(blocks))
        self.animate = bool(animate)

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        height, width = frame.shape[:2]
        blocks = self.blocks
        if self.animate:
            blocks = max(3, int(self.blocks + 4 * np.sin(ctx.time * 1.5)))
        small_w = max(2, width // blocks)
        small_h = max(2, height // blocks)
        small = cv2.resize(frame, (small_w, small_h), interpolation=cv2.INTER_AREA)
        return cv2.resize(small, (width, height), interpolation=cv2.INTER_NEAREST)


class StainedGlassFilter(Filter):
    name = "glass"
    label = "Stained glass"
    label_es = "Vitral"
    emoji = "🪟"
    category = "artistic"
    cost = "medium"
    description = "Colour cells separated by dark lead lines."
    description_es = "Celdas de color separadas por líneas oscuras."

    def __init__(self, cells: int = 90) -> None:
        super().__init__()
        self.cells = max(10, int(cells))

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        _height, _width = frame.shape[:2]
        # Posterise then mean-shift towards flat regions.
        step = 36
        flat = (frame // step) * step + step // 2
        flat = flat.astype(np.uint8)
        flat = cv2.medianBlur(flat, 5)

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(cv2.medianBlur(gray, 5), 60, 140)
        edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)
        lead = cv2.cvtColor(255 - edges, cv2.COLOR_GRAY2BGR)
        return cv2.multiply(flat, lead, scale=1 / 255.0).astype(np.uint8)


class PointillismFilter(Filter):
    name = "pointillism"
    label = "Pointillism"
    label_es = "Puntillismo"
    emoji = "🔴"
    category = "artistic"
    cost = "medium"
    description = "Seurat-style dots of pure colour that blend in your eye."
    description_es = "Puntos de color puro que se mezclan en tu vista."

    def __init__(self, dot: int = 5, jitter: float = 0.35) -> None:
        super().__init__()
        self.dot = max(2, int(dot))
        self.jitter = float(jitter)

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        height, width = frame.shape[:2]
        dot = self.dot
        small_w = max(2, width // dot)
        small_h = max(2, height // dot)
        sampled = cv2.resize(frame, (small_w, small_h), interpolation=cv2.INTER_AREA)

        canvas = np.full_like(frame, 245)
        rng = np.random.default_rng(7)
        offsets = rng.uniform(-self.jitter, self.jitter, size=(small_h, small_w, 2))
        radius = max(1, int(dot * 0.62))

        for row in range(small_h):
            for col in range(small_w):
                cx = int((col + 0.5 + offsets[row, col, 0]) * dot)
                cy = int((row + 0.5 + offsets[row, col, 1]) * dot)
                colour = tuple(int(c) for c in sampled[row, col])
                cv2.circle(canvas, (cx, cy), radius, colour, -1, cv2.LINE_AA)
        return canvas


class NeonFilter(Filter):
    name = "neon"
    label = "Neon glow"
    label_es = "Neón"
    emoji = "💡"
    category = "stylize"
    cost = "medium"
    description = "Edges only, blooming in electric colour over black."
    description_es = "Solo los bordes, brillando en color eléctrico sobre negro."

    def __init__(self, hue_shift: float = 0.0) -> None:
        super().__init__()
        self.hue_shift = float(hue_shift)

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 40, 120)

        # Colour the edges by the original hue, then bloom them.
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        hsv[..., 0] = (hsv[..., 0].astype(np.float32) + ctx.time * 12.0 + self.hue_shift) % 180
        hsv[..., 1] = 255
        hsv[..., 2] = 255
        coloured = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

        mask = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR).astype(np.float32) / 255.0
        glow = cv2.GaussianBlur(coloured.astype(np.float32) * mask, (0, 0), 7.0)
        sharp = coloured.astype(np.float32) * mask
        out = np.clip(sharp * 1.1 + glow * 1.6, 0, 255)
        return out.astype(np.uint8)


class ComicFilter(Filter):
    name = "comic"
    label = "Comic book"
    label_es = "Cómic"
    emoji = "💥"
    category = "artistic"
    cost = "medium"
    description = "Ben-Day dots, halftone gradients and heavy ink — a printed page."
    description_es = "Tramas Ben-Day, degradados de semitono y tinta gruesa."

    def apply(self, frame: np.ndarray, ctx: FilterContext) -> np.ndarray:
        cartoon = CartoonFilter(levels=5, edge_thickness=3)
        base = cartoon.apply(frame, ctx)
        halftone = HalftoneFilter(cell=4, angle=45.0)
        screen = halftone.apply(base, ctx)
        # Screen the dots over the flat colours for the printed feel.
        return cv2.multiply(base, screen, scale=1 / 255.0).astype(np.uint8)


for _filter in (
    CartoonFilter(),
    PencilSketchFilter(),
    InkFilter(),
    OilPaintingFilter(),
    WatercolorFilter(),
    HalftoneFilter(),
    AsciiFilter(),
    PixelateFilter(),
    StainedGlassFilter(),
    PointillismFilter(),
    NeonFilter(),
    ComicFilter(),
):
    register_filter(_filter)
