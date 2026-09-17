"""MirrorLab — turn your webcam into a computer-vision playground.

MirrorLab detects **facial expressions** and **hand gestures** in real time and
stacks **visual filters** and **augmented-reality effects** on top of your camera
feed. It runs on macOS, Windows and Linux, and it also ships as a browser demo.

Quick start
-----------
::

    from mirrorlab import MirrorLab

    app = MirrorLab()
    app.run()

Or from the command line::

    mirrorlab run --filter cartoon --hand

See ``mirrorlab --help`` for the full command surface.
"""

from __future__ import annotations

from .version import __version__, __version_info__

__all__ = ["Config", "MirrorLab", "__version__", "__version_info__", "get_config"]


def __getattr__(name: str):  # pragma: no cover - lazy imports keep startup fast
    """Lazily expose the heavy entry points.

    Importing :mod:`mirrorlab` must stay cheap: the CLI, the doctor command and
    the test-suite all import the package without paying for OpenCV + MediaPipe
    initialisation. ``from mirrorlab import MirrorLab`` still works because of
    this module-level ``__getattr__`` (PEP 562).
    """
    if name == "MirrorLab":
        from .app import MirrorLab

        return MirrorLab
    if name == "Config":
        from .config import Config

        return Config
    if name == "get_config":
        from .config import get_config

        return get_config
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
