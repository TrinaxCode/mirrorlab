"""Single source of truth for the MirrorLab version."""

from __future__ import annotations

__version_info__ = (2, 1, 0)
__version__ = ".".join(str(part) for part in __version_info__)

#: Human readable codename, shown in the CLI banner and the HUD.
CODENAME = "Studio"
