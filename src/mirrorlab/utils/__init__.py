"""Shared utilities: geometry, smoothing, colours, logging and timing."""

from __future__ import annotations

from .colors import PALETTES, Palette, bgr_to_hex, get_palette, hex_to_bgr, with_alpha
from .geometry import (
    angle,
    as_array,
    bounding_box,
    centroid,
    clamp,
    distance,
    distance_3d,
    finger_curl,
    hand_scale,
    point_in_polygon,
    to_pixel,
    to_pixels,
)
from .logging import get_logger, setup_logging
from .smoothing import EmaFilter, LandmarkSmoother, OneEuroFilter, SlidingWindow
from .timing import FpsMeter, Stopwatch

__all__ = [
    "PALETTES",
    "EmaFilter",
    "FpsMeter",
    "LandmarkSmoother",
    "OneEuroFilter",
    "Palette",
    "SlidingWindow",
    "Stopwatch",
    "angle",
    "as_array",
    "bgr_to_hex",
    "bounding_box",
    "centroid",
    "clamp",
    "distance",
    "distance_3d",
    "finger_curl",
    "get_logger",
    "get_palette",
    "hand_scale",
    "hex_to_bgr",
    "point_in_polygon",
    "setup_logging",
    "to_pixel",
    "to_pixels",
    "with_alpha",
]
