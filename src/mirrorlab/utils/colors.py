"""Colour themes and drawing palettes for the HUD and AR overlays."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

__all__ = ["PALETTES", "Palette", "bgr_to_hex", "get_palette", "hex_to_bgr", "with_alpha"]

RGB = Tuple[int, int, int]
BGR = Tuple[int, int, int]


def hex_to_bgr(value: str) -> BGR:
    """``"#RRGGBB"`` -> OpenCV's native ``(B, G, R)`` tuple."""
    text = value.lstrip("#")
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    if len(text) != 6:
        raise ValueError(f"Expected a #RGB or #RRGGBB colour, got {value!r}")
    r, g, b = (int(text[i : i + 2], 16) for i in (0, 2, 4))
    return (b, g, r)


def bgr_to_hex(color: BGR) -> str:
    """OpenCV ``(B, G, R)`` tuple -> ``"#RRGGBB"``."""
    b, g, r = (int(max(0, min(255, c))) for c in color[:3])
    return f"#{r:02x}{g:02x}{b:02x}"


def with_alpha(color: BGR, alpha: float, background: BGR = (0, 0, 0)) -> BGR:
    """Blend ``color`` towards ``background`` by ``alpha`` (0 = background)."""
    a = max(0.0, min(1.0, float(alpha)))
    return tuple(  # type: ignore[return-value]
        round(color[i] * a + background[i] * (1.0 - a)) for i in range(3)
    )


@dataclass(frozen=True)
class Palette:
    """A named colour scheme used by the HUD, skeletons and overlays."""

    name: str
    primary: BGR  # main accent (titles, active elements)
    secondary: BGR  # supporting accent (secondary text)
    face: BGR  # face mesh tessellation
    left_hand: BGR  # one hand colour so two hands stay distinguishable
    right_hand: BGR
    text: BGR
    text_dim: BGR
    panel: BGR  # HUD panel background
    warn: BGR
    ok: BGR

    def as_dict(self) -> Dict[str, Tuple[int, int, int]]:
        return {
            "primary": self.primary,
            "secondary": self.secondary,
            "face": self.face,
            "left_hand": self.left_hand,
            "right_hand": self.right_hand,
            "text": self.text,
            "text_dim": self.text_dim,
            "panel": self.panel,
            "warn": self.warn,
            "ok": self.ok,
        }


PALETTES: Dict[str, Palette] = {
    # Cool teal/violet — the default look of the MirrorLab site.
    "aurora": Palette(
        name="aurora",
        primary=hex_to_bgr("#5eead4"),
        secondary=hex_to_bgr("#a78bfa"),
        face=hex_to_bgr("#38bdf8"),
        left_hand=hex_to_bgr("#5eead4"),
        right_hand=hex_to_bgr("#fb7185"),
        text=(245, 245, 245),
        text_dim=(170, 170, 170),
        panel=(28, 24, 20),
        warn=hex_to_bgr("#fbbf24"),
        ok=hex_to_bgr("#4ade80"),
    ),
    # Hot orange/red — great on top of thermal and glitch filters.
    "magma": Palette(
        name="magma",
        primary=hex_to_bgr("#fb923c"),
        secondary=hex_to_bgr("#f43f5e"),
        face=hex_to_bgr("#fbbf24"),
        left_hand=hex_to_bgr("#fb923c"),
        right_hand=hex_to_bgr("#f43f5e"),
        text=(250, 245, 240),
        text_dim=(180, 165, 155),
        panel=(20, 20, 28),
        warn=hex_to_bgr("#facc15"),
        ok=hex_to_bgr("#34d399"),
    ),
    # Terminal green — pairs with the matrix and x-ray filters.
    "mono": Palette(
        name="mono",
        primary=hex_to_bgr("#e5e7eb"),
        secondary=hex_to_bgr("#9ca3af"),
        face=hex_to_bgr("#f3f4f6"),
        left_hand=hex_to_bgr("#e5e7eb"),
        right_hand=hex_to_bgr("#9ca3af"),
        text=(240, 240, 240),
        text_dim=(150, 150, 150),
        panel=(18, 18, 18),
        warn=hex_to_bgr("#fde047"),
        ok=hex_to_bgr("#86efac"),
    ),
    # Playful pink/cyan — the photo-booth theme.
    "candy": Palette(
        name="candy",
        primary=hex_to_bgr("#f472b6"),
        secondary=hex_to_bgr("#22d3ee"),
        face=hex_to_bgr("#c084fc"),
        left_hand=hex_to_bgr("#f472b6"),
        right_hand=hex_to_bgr("#22d3ee"),
        text=(255, 250, 252),
        text_dim=(200, 180, 195),
        panel=(32, 24, 34),
        warn=hex_to_bgr("#fdba74"),
        ok=hex_to_bgr("#86efac"),
    ),
}


def get_palette(name: str = "aurora") -> Palette:
    """Look up a palette by name, falling back to ``aurora``."""
    return PALETTES.get(name, PALETTES["aurora"])
