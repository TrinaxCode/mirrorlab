"""What the desktop app remembers between runs, in a small JSON file.

Reading never raises: a missing, unreadable or hand-edited file just means the
defaults, because failing to open a camera app over a preferences typo is worse
than forgetting a setting.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any, Dict, Optional

from ..config import _xdg_config_home
from ..studio.settings import BACKGROUND_MODES
from .strings import LANGUAGES

__all__ = ["PREFS_FILENAME", "DesktopPrefs", "prefs_path"]

PREFS_FILENAME = "desktop.json"
OUTPUTS = ("vcam", "none")


def prefs_path() -> Path:
    return _xdg_config_home() / PREFS_FILENAME


@dataclass
class DesktopPrefs:
    language: str = ""  # "" means follow the system
    camera: int = 0
    background: str = "blur"
    background_image: str = ""
    auto_frame: bool = True
    studio_light: bool = True
    gesture_control: bool = True
    output: str = "vcam"

    @classmethod
    def from_mapping(cls, raw: Any) -> "DesktopPrefs":
        """Keep every valid field of ``raw`` and silently default the rest."""
        prefs = cls()
        if not isinstance(raw, dict):
            return prefs
        for item in fields(cls):
            if item.name not in raw:
                continue
            value = raw[item.name]
            default = getattr(prefs, item.name)
            if isinstance(default, bool):
                valid = isinstance(value, bool)
            elif isinstance(default, int):
                valid = isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 15
            else:
                valid = isinstance(value, str) and len(value) <= 4096
            if valid:
                setattr(prefs, item.name, value)
        if prefs.language and prefs.language not in LANGUAGES:
            prefs.language = ""
        if prefs.background not in BACKGROUND_MODES:
            prefs.background = "blur"
        if prefs.output not in OUTPUTS:
            prefs.output = "vcam"
        if prefs.background == "replace" and not prefs.background_image:
            prefs.background = "blur"
        return prefs

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "DesktopPrefs":
        target = path or prefs_path()
        try:
            return cls.from_mapping(json.loads(target.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            return cls()

    def save(self, path: Optional[Path] = None) -> bool:
        """Write atomically. Returns ``False`` (instead of raising) when the disk refuses."""
        target = path or prefs_path()
        payload: Dict[str, Any] = asdict(self)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            handle, temp_name = tempfile.mkstemp(dir=target.parent, prefix=".desktop-", suffix=".tmp")
            try:
                with os.fdopen(handle, "w", encoding="utf-8") as stream:
                    json.dump(payload, stream, indent=2)
                os.replace(temp_name, target)
            except BaseException:
                Path(temp_name).unlink(missing_ok=True)
                raise
        except OSError:
            return False
        return True
