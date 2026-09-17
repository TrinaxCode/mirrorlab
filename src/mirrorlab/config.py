"""Layered configuration for MirrorLab.

Configuration is resolved from four sources, lowest priority first:

1. Built-in defaults (:data:`DEFAULTS`).
2. A config file (``mirrorlab.json`` / ``mirrorlab.yaml``) discovered in the
   current directory, ``$XDG_CONFIG_HOME/mirrorlab``, ``~/.config/mirrorlab`` or
   ``%APPDATA%/mirrorlab``.
3. Environment variables prefixed with ``MIRRORLAB_`` (e.g. ``MIRRORLAB_FILTER``).
4. Explicit keyword overrides — what the CLI passes through.

The result is a frozen, validated :class:`Config` object so nothing mutates the
settings halfway through a session.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field, fields, replace
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

__all__ = ["DEFAULTS", "Config", "config_paths", "get_config", "load_config_file"]

#: File names probed, in order, when auto-discovering a config file.
CONFIG_FILENAMES = ("mirrorlab.json", "mirrorlab.yaml", "mirrorlab.yml")

DEFAULTS: Dict[str, Any] = {
    # --- camera -----------------------------------------------------------
    "camera_index": 0,
    "camera_width": 1280,
    "camera_height": 720,
    "camera_fps": 30,
    "camera_backend": "auto",  # auto | avfoundation | dshow | msmf | v4l2 | any
    "mirror": True,  # horizontal flip: behaves like a mirror
    # --- detectors --------------------------------------------------------
    "enable_face": True,
    "enable_hands": True,
    "enable_segmentation": False,
    "max_faces": 1,
    "max_hands": 2,
    "min_face_confidence": 0.5,
    "min_hand_confidence": 0.5,
    "min_tracking_confidence": 0.5,
    "model_complexity": 1,  # 0 = fastest, 1 = balanced
    # --- pipeline ---------------------------------------------------------
    "filter": "original",
    "effects": [],  # list[str] of AR overlays, e.g. ["sunglasses", "dog"]
    "gesture_control": True,  # gestures switch filters / trigger actions
    "air_draw": False,
    "smooth_landmarks": True,
    "smoothing_min_cutoff": 1.7,  # One-Euro filter: lower = smoother
    "smoothing_beta": 0.35,  # One-Euro filter: higher = more responsive
    "expression_smoothing": 0.35,  # EMA factor for expression scores
    # --- window / HUD -----------------------------------------------------
    "window_name": "MirrorLab",
    "window_width": 1280,
    "window_height": 720,
    "fullscreen": False,
    "show_hud": True,
    "show_landmarks": True,
    "show_fps": True,
    "reactions_dir": "assets/reactions",
    "show_reactions": False,
    # --- output -----------------------------------------------------------
    "output_dir": "captures",
    "record_fps": 30.0,
    "record_codec": "mp4v",
    "snapshot_format": "png",
    "jpeg_quality": 95,
    # --- runtime ----------------------------------------------------------
    "headless": False,  # no GUI window: useful for CI, servers, tests
    "max_frames": 0,  # 0 = unlimited (headless smoke tests use this)
    "stats_csv": "",  # path to append per-frame stats, empty = disabled
    "log_level": "INFO",
    "theme": "aurora",  # HUD palette: aurora | magma | mono | candy
}


def _xdg_config_home() -> Path:
    if sys.platform == "win32":  # pragma: no cover - windows only
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return Path(base) / "mirrorlab"
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return Path(base) / "mirrorlab"


def config_paths() -> List[Path]:
    """Return every location probed for a config file, in priority order."""
    here = Path.cwd()
    paths = [here / name for name in CONFIG_FILENAMES]
    home = _xdg_config_home()
    paths += [home / name for name in CONFIG_FILENAMES]
    paths.append(Path(__file__).resolve().parent / "data" / "default_config.json")
    return paths


def _read_yaml(text: str) -> Mapping[str, Any]:  # pragma: no cover - optional dep
    try:
        import yaml  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "PyYAML is required to read YAML config files. Install it with "
            "`pip install PyYAML`, or use a .json config instead."
        ) from exc
    data = yaml.safe_load(text)
    return data or {}


def load_config_file(path: os.PathLike[str] | str) -> Dict[str, Any]:
    """Load a JSON or YAML config file into a plain dict.

    Unknown keys are preserved (and later rejected by :class:`Config`) so typos
    surface as errors instead of silently doing nothing.
    """
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    data = dict(_read_yaml(text)) if path.suffix.lower() in {".yaml", ".yml"} else json.loads(text or "{}")
    if not isinstance(data, dict):
        raise ValueError(f"Config file {path} must contain a mapping at the top level.")
    return data


def _discover_config_file() -> Optional[Path]:
    for candidate in config_paths():
        if candidate.is_file():
            return candidate
    return None


def _coerce(key: str, value: Any, template: Any) -> Any:
    """Best-effort type coercion for values coming from env vars (always str)."""
    if isinstance(value, str) and not isinstance(template, str):
        lowered = value.strip().lower()
        if isinstance(template, bool):
            if lowered in {"1", "true", "yes", "on", "y"}:
                return True
            if lowered in {"0", "false", "no", "off", "n"}:
                return False
            raise ValueError(f"Environment override for {key!r} must be a boolean, got {value!r}")
        if isinstance(template, int):
            return int(float(value))
        if isinstance(template, float):
            return float(value)
        if isinstance(template, list):
            items = [item.strip() for item in value.replace(";", ",").split(",") if item.strip()]
            return items
    return value


def _env_overrides() -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key, template in DEFAULTS.items():
        env_key = f"MIRRORLAB_{key.upper()}"
        if env_key in os.environ:
            out[key] = _coerce(key, os.environ[env_key], template)
    return out


@dataclass(frozen=True)
class Config:
    """Immutable, validated MirrorLab configuration.

    Use :meth:`with_overrides` to derive a modified copy — MirrorLab never
    mutates a config in place, which keeps the render pipeline easy to reason
    about and trivially testable.
    """

    camera_index: int = DEFAULTS["camera_index"]
    camera_width: int = DEFAULTS["camera_width"]
    camera_height: int = DEFAULTS["camera_height"]
    camera_fps: int = DEFAULTS["camera_fps"]
    camera_backend: str = DEFAULTS["camera_backend"]
    mirror: bool = DEFAULTS["mirror"]

    enable_face: bool = DEFAULTS["enable_face"]
    enable_hands: bool = DEFAULTS["enable_hands"]
    enable_segmentation: bool = DEFAULTS["enable_segmentation"]
    max_faces: int = DEFAULTS["max_faces"]
    max_hands: int = DEFAULTS["max_hands"]
    min_face_confidence: float = DEFAULTS["min_face_confidence"]
    min_hand_confidence: float = DEFAULTS["min_hand_confidence"]
    min_tracking_confidence: float = DEFAULTS["min_tracking_confidence"]
    model_complexity: int = DEFAULTS["model_complexity"]

    filter: str = DEFAULTS["filter"]
    effects: List[str] = field(default_factory=list)
    gesture_control: bool = DEFAULTS["gesture_control"]
    air_draw: bool = DEFAULTS["air_draw"]
    smooth_landmarks: bool = DEFAULTS["smooth_landmarks"]
    smoothing_min_cutoff: float = DEFAULTS["smoothing_min_cutoff"]
    smoothing_beta: float = DEFAULTS["smoothing_beta"]
    expression_smoothing: float = DEFAULTS["expression_smoothing"]

    window_name: str = DEFAULTS["window_name"]
    window_width: int = DEFAULTS["window_width"]
    window_height: int = DEFAULTS["window_height"]
    fullscreen: bool = DEFAULTS["fullscreen"]
    show_hud: bool = DEFAULTS["show_hud"]
    show_landmarks: bool = DEFAULTS["show_landmarks"]
    show_fps: bool = DEFAULTS["show_fps"]
    reactions_dir: str = DEFAULTS["reactions_dir"]
    show_reactions: bool = DEFAULTS["show_reactions"]

    output_dir: str = DEFAULTS["output_dir"]
    record_fps: float = DEFAULTS["record_fps"]
    record_codec: str = DEFAULTS["record_codec"]
    snapshot_format: str = DEFAULTS["snapshot_format"]
    jpeg_quality: int = DEFAULTS["jpeg_quality"]

    headless: bool = DEFAULTS["headless"]
    max_frames: int = DEFAULTS["max_frames"]
    stats_csv: str = DEFAULTS["stats_csv"]
    log_level: str = DEFAULTS["log_level"]
    theme: str = DEFAULTS["theme"]

    # ------------------------------------------------------------------ #
    def __post_init__(self) -> None:
        problems: List[str] = []
        if self.camera_index < 0:
            problems.append("camera_index must be >= 0")
        if self.camera_width < 160 or self.camera_height < 120:
            problems.append("camera_width/camera_height are implausibly small")
        if not 1 <= self.camera_fps <= 240:
            problems.append("camera_fps must be between 1 and 240")
        if self.camera_backend not in {"auto", "avfoundation", "dshow", "msmf", "v4l2", "any"}:
            problems.append(f"unknown camera_backend {self.camera_backend!r}")
        if self.max_faces < 0 or self.max_hands < 0:
            problems.append("max_faces/max_hands must be >= 0")
        for name in (
            "min_face_confidence",
            "min_hand_confidence",
            "min_tracking_confidence",
        ):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                problems.append(f"{name} must be within [0, 1], got {value}")
        if not 0.0 <= self.expression_smoothing <= 1.0:
            problems.append("expression_smoothing must be within [0, 1]")
        if self.model_complexity not in (0, 1):
            problems.append("model_complexity must be 0 or 1")
        if self.theme not in {"aurora", "magma", "mono", "candy"}:
            problems.append(f"unknown theme {self.theme!r}")
        if self.snapshot_format not in {"png", "jpg", "jpeg", "webp"}:
            problems.append(f"unsupported snapshot_format {self.snapshot_format!r}")
        if not isinstance(self.effects, list):
            problems.append("effects must be a list of effect names")
        if problems:
            raise ValueError("Invalid MirrorLab configuration:\n  - " + "\n  - ".join(problems))

    # ------------------------------------------------------------------ #
    @classmethod
    def load(
        cls,
        path: os.PathLike[str] | str | None = None,
        *,
        overrides: Optional[Mapping[str, Any]] = None,
        use_env: bool = True,
    ) -> "Config":
        """Build a config from file + environment + explicit overrides."""
        data: Dict[str, Any] = {}
        source = Path(path) if path else _discover_config_file()
        if source is not None:
            data.update(load_config_file(source))
        if use_env:
            data.update(_env_overrides())
        if overrides:
            data.update({k: v for k, v in overrides.items() if v is not None})
        return cls.from_mapping(data)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "Config":
        """Build a config from a mapping, rejecting unknown keys."""
        known = {f.name for f in fields(cls)}
        unknown = sorted(set(data) - known)
        if unknown:
            hint = ", ".join(unknown)
            raise ValueError(
                f"Unknown configuration key(s): {hint}.\n"
                f"Run `mirrorlab config --list` to see every supported key."
            )
        return cls(**{k: v for k, v in data.items() if k in known})

    # ------------------------------------------------------------------ #
    def with_overrides(self, **overrides: Any) -> "Config":
        """Return a copy with ``overrides`` applied (``None`` values ignored)."""
        clean = {k: v for k, v in overrides.items() if v is not None}
        return replace(self, **clean)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def save(self, path: os.PathLike[str] | str) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.to_json(), encoding="utf-8")
        return target


_CACHED: Optional[Config] = None


def get_config(
    path: os.PathLike[str] | str | None = None,
    *,
    overrides: Optional[Mapping[str, Any]] = None,
    use_env: bool = True,
    refresh: bool = False,
) -> Config:
    """Return a process-wide cached config (handy for libraries and notebooks)."""
    global _CACHED
    if _CACHED is None or refresh or path is not None or overrides:
        _CACHED = Config.load(path, overrides=overrides, use_env=use_env)
    return _CACHED
