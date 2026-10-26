"""Studio settings: what the virtual camera does, validated once, immutable after.

Settings are resolved from, lowest priority first:

1. the built-in defaults on :class:`StudioSettings`,
2. a named **profile** (``meeting``, ``stream``, ``privacy``, ``clean``, or one you
   define yourself in the settings file),
3. a ``studio.json`` / ``studio.yaml`` file found in the current directory or the
   user config directory,
4. explicit keyword overrides (what the CLI passes).

Unknown keys are an error. A typo such as ``backgroud`` must fail loudly, because
the alternative is a camera that silently does not blur your room.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, fields, replace
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from ..config import _read_yaml, _xdg_config_home

__all__ = [
    "BACKGROUND_MODES",
    "PRIVACY_MODES",
    "PROFILES",
    "STUDIO_BINDINGS",
    "StudioSettings",
    "settings_paths",
]

BACKGROUND_MODES = ("off", "blur", "replace", "green", "black")
PRIVACY_MODES = ("card", "black", "blur")

SETTINGS_FILENAMES = ("studio.json", "studio.yaml", "studio.yml")

#: Gesture -> studio action. Hand poses that people make by accident while
#: talking (a flat palm, a fist) get a long dwell in :data:`STUDIO_DWELL`.
STUDIO_BINDINGS: Dict[str, str] = {
    "open_palm": "privacy",
    "peace": "background_next",
    "thumbs_up": "reaction:thumbs_up",
    "ily": "reaction:love",
    "ok": "reaction:ok",
}

#: Per-gesture hold time in seconds before the action fires.
STUDIO_DWELL: Dict[str, float] = {
    "open_palm": 1.6,
    "peace": 1.0,
    "thumbs_up": 0.6,
    "ily": 0.6,
    "ok": 0.6,
}

#: Built-in profiles. Each is a partial settings mapping.
PROFILES: Dict[str, Dict[str, Any]] = {
    "meeting": {
        "background": "blur",
        "auto_frame": True,
        "studio_light": True,
    },
    # A flat chroma-key green that OBS, Zoom and Teams can key out.
    "stream": {
        "background": "green",
        "auto_frame": False,
        "studio_light": True,
        "reactions": True,
    },
    "privacy": {
        "background": "blur",
        "blur_strength": 71,
        "away_after": 5.0,
        "gesture_control": True,
    },
    "clean": {
        "background": "off",
        "auto_frame": False,
        "studio_light": False,
        "gesture_control": False,
        "reactions": False,
    },
}


def settings_paths() -> List[Path]:
    """Every location probed for a settings file, in priority order."""
    here = Path.cwd()
    home = _xdg_config_home()
    return [here / name for name in SETTINGS_FILENAMES] + [home / name for name in SETTINGS_FILENAMES]


@dataclass(frozen=True)
class StudioSettings:
    """Immutable, validated configuration for a studio session."""

    # --- output ---------------------------------------------------------
    width: int = 1280
    height: int = 720
    fps: int = 30
    #: Detections per second for faces and hands (0 = as fast as possible). Ten is
    #: plenty for gestures and framing, and leaves CPU for the video path: hand
    #: detection runs several threads and otherwise causes frame-time spikes.
    perception_fps: int = 10
    #: Width the detectors run at. Landmarks are normalised, so analysing a 640 px
    #: copy gives the same result as full resolution at a fraction of the cost.
    analysis_width: int = 480
    #: Width of the copy fed to the person segmenter (its model works at 256 px).
    segmentation_width: int = 320

    # --- background -----------------------------------------------------
    background: str = "off"
    blur_strength: int = 51
    background_image: str = ""
    mask_smoothing: float = 0.55

    # --- framing and light ----------------------------------------------
    auto_frame: bool = False
    max_zoom: float = 1.8
    studio_light: bool = False
    light_strength: float = 0.6

    # --- privacy --------------------------------------------------------
    privacy_mode: str = "card"
    away_text: str = "Be right back"
    #: Cover the camera automatically after this many seconds without a face. 0 disables.
    away_after: float = 0.0
    #: Start with the shutter closed, so nothing is shown until you open it.
    privacy_on_start: bool = False

    # --- gestures and reactions -----------------------------------------
    gesture_control: bool = True
    reactions: bool = True
    bindings: Dict[str, str] = field(default_factory=lambda: dict(STUDIO_BINDINGS))
    dwell: Dict[str, float] = field(default_factory=lambda: dict(STUDIO_DWELL))

    def __post_init__(self) -> None:
        problems: List[str] = []
        if not (160 <= self.width <= 7680 and 120 <= self.height <= 4320):
            problems.append("width/height must be between 160x120 and 7680x4320")
        if self.width % 2 or self.height % 2:
            problems.append("width and height must be even (video encoders require it)")
        if not 1 <= self.fps <= 120:
            problems.append("fps must be between 1 and 120")
        if not 0 <= self.perception_fps <= 120:
            problems.append("perception_fps must be between 0 and 120")
        if not 160 <= self.analysis_width <= 1920:
            problems.append("analysis_width must be between 160 and 1920")
        if not 128 <= self.segmentation_width <= 1280:
            problems.append("segmentation_width must be between 128 and 1280")
        if self.background not in BACKGROUND_MODES:
            problems.append(
                f"background must be one of {', '.join(BACKGROUND_MODES)}; got {self.background!r}"
            )
        if not 3 <= self.blur_strength <= 201:
            problems.append("blur_strength must be between 3 and 201")
        if not 0.0 <= self.mask_smoothing < 1.0:
            problems.append("mask_smoothing must be in [0, 1)")
        if not 1.0 <= self.max_zoom <= 4.0:
            problems.append("max_zoom must be between 1.0 and 4.0")
        if not 0.0 <= self.light_strength <= 1.0:
            problems.append("light_strength must be within [0, 1]")
        if self.privacy_mode not in PRIVACY_MODES:
            problems.append(
                f"privacy_mode must be one of {', '.join(PRIVACY_MODES)}; got {self.privacy_mode!r}"
            )
        if self.away_after < 0:
            problems.append("away_after must be >= 0")
        if len(self.away_text) > 80:
            problems.append("away_text must be at most 80 characters")

        for gesture, seconds in self.dwell.items():
            if not 0.0 <= float(seconds) <= 10.0:
                problems.append(f"dwell for {gesture!r} must be between 0 and 10 seconds")
        for gesture, action in self.bindings.items():
            if not isinstance(action, str) or not action:
                problems.append(f"binding for {gesture!r} must be a non-empty action name")
        if problems:
            raise ValueError("Invalid studio settings:\n  - " + "\n  - ".join(problems))

    # ------------------------------------------------------------------ #
    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "StudioSettings":
        known = {f.name for f in fields(cls)}
        unknown = sorted(set(data) - known)
        if unknown:
            raise ValueError(
                f"Unknown studio setting(s): {', '.join(unknown)}.\n"
                f"Valid keys: {', '.join(sorted(known))}."
            )
        clean = dict(data)
        if "bindings" in clean:
            clean["bindings"] = dict(clean["bindings"])
        if "dwell" in clean:
            clean["dwell"] = {str(k): float(v) for k, v in dict(clean["dwell"]).items()}
        return cls(**clean)

    @classmethod
    def load(
        cls,
        path: "os.PathLike[str] | str | None" = None,
        *,
        profile: Optional[str] = None,
        overrides: Optional[Mapping[str, Any]] = None,
    ) -> "StudioSettings":
        """Resolve defaults, profile, file and overrides into one validated object."""
        file_data: Dict[str, Any] = {}
        source = Path(path) if path else _discover()
        if source is not None:
            file_data = _read_file(source)

        user_profiles = file_data.pop("profiles", {}) or {}
        if not isinstance(user_profiles, dict):
            raise ValueError("'profiles' in the settings file must be a mapping of name -> settings")

        data: Dict[str, Any] = {}
        if profile:
            merged = {**PROFILES, **user_profiles}
            if profile not in merged:
                raise ValueError(f"Unknown profile {profile!r}. Available: {', '.join(sorted(merged))}.")
            data.update(merged[profile])
        data.update(file_data)
        if overrides:
            data.update({k: v for k, v in overrides.items() if v is not None})
        return cls.from_mapping(data)

    def with_overrides(self, **overrides: Any) -> "StudioSettings":
        return replace(self, **{k: v for k, v in overrides.items() if v is not None})

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


def _discover() -> Optional[Path]:
    for candidate in settings_paths():
        if candidate.is_file():
            return candidate
    return None


def _read_file(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    data = dict(_read_yaml(text)) if path.suffix.lower() in {".yaml", ".yml"} else json.loads(text or "{}")
    if not isinstance(data, dict):
        raise ValueError(f"Settings file {path} must contain a mapping at the top level.")
    return data
