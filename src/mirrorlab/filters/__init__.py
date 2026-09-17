"""The MirrorLab filter library.

Importing this package registers every built-in filter. Order matters only for
documentation: each module populates the shared :data:`~mirrorlab.filters.base.FILTERS`
registry on import.

::

    from mirrorlab.filters import build_filter, list_filters

    effect = build_filter("cartoon+vignette")
    for f in list_filters():
        print(f.emoji, f.name, "-", f.description)
"""

from __future__ import annotations

from . import artistic, classic, glitch, stylize, utility  # noqa: F401  (registration side effects)
from .base import (
    CATEGORIES,
    FILTERS,
    Filter,
    FilterChain,
    FilterContext,
    build_chain,
    build_filter,
    filter_catalog,
    get_filter,
    list_filters,
    register_filter,
)

__all__ = [
    "CATEGORIES",
    "FILTERS",
    "PRESETS",
    "Filter",
    "FilterChain",
    "FilterContext",
    "build_chain",
    "build_filter",
    "filter_catalog",
    "filter_names",
    "filters_by_category",
    "get_filter",
    "list_filters",
    "presets",
    "register_filter",
]


def filter_names() -> list:
    """Sorted names of every registered filter."""
    return sorted(FILTERS)


def filters_by_category() -> dict:
    """``{category: [filter, ...]}`` for grouped listings."""
    grouped: dict = {}
    for name in CATEGORIES:
        items = list_filters(name)
        if items:
            grouped[name] = items
    return grouped


#: Curated multi-filter looks, exposed as ``--preset`` on the CLI.
PRESETS: dict = {
    "cinema": {
        "filter": "warmth+vignette+sharpen",
        "label": "Cinematic",
        "label_es": "Cinemático",
        "description": "Warm highlights, soft corners, crisp detail.",
    },
    "anime": {
        "filter": "cartoon+saturation",
        "label": "Anime",
        "label_es": "Anime",
        "description": "Flat cel colours with a vivid palette.",
    },
    "noir": {
        "filter": "grayscale+vignette+sharpen",
        "label": "Film noir",
        "label_es": "Cine negro",
        "description": "High-contrast monochrome with a heavy vignette.",
    },
    "retro80s": {
        "filter": "cyberpunk+chromatic+scanlines",
        "label": "Retro 80s",
        "label_es": "Retro 80s",
        "description": "Neon grade, colour fringing and CRT lines.",
    },
    "broken": {
        "filter": "glitch+trails",
        "label": "Broken signal",
        "label_es": "Señal rota",
        "description": "Databend blocks with echo trails.",
    },
    "toon": {
        "filter": "comic+halftone",
        "label": "Comic print",
        "label_es": "Cómic impreso",
        "description": "Ben-Day dots and heavy ink.",
    },
    "ghost": {
        "filter": "xray+glitch",
        "label": "Ghost in the machine",
        "label_es": "Fantasma",
        "description": "Radiograph look with signal dropouts.",
    },
    "studio": {
        "filter": "skin_smooth+warmth+bg_blur",
        "label": "Studio portrait",
        "label_es": "Retrato de estudio",
        "description": "Retouched skin, warm light, blurred background.",
    },
    "paper": {
        "filter": "sketch+saturation",
        "label": "Sketchbook",
        "label_es": "Cuaderno",
        "description": "Graphite linework with a colour wash.",
    },
    "vhs": {
        "filter": "vhs+scanlines",
        "label": "Home video",
        "label_es": "Vídeo casero",
        "description": "Tape wobble, tracking noise and scanlines.",
    },
}


def presets() -> dict:
    """Return the curated preset table."""
    return PRESETS
