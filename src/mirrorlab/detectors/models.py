"""Model download + cache management.

MediaPipe's Tasks API loads ``.task`` bundles from disk. Rather than committing
~12 MB of binaries to git (or shipping them inside the wheel), MirrorLab
downloads them once into a cache directory and reuses them forever after:

1. ``$MIRRORLAB_MODELS`` if set,
2. the package's own ``data/models`` directory (a manual drop-in wins, which is
   what you want for offline and air-gapped setups),
3. ``./models`` next to the working directory,
4. the user cache — ``~/.cache/mirrorlab/models`` (Linux),
   ``~/Library/Caches/mirrorlab/models`` (macOS),
   ``%LOCALAPPDATA%/mirrorlab/models`` (Windows).

Dropping a file into *any* of those locations makes MirrorLab fully offline.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

from ..utils.logging import get_logger

__all__ = [
    "MODELS",
    "ModelSpec",
    "download_model",
    "ensure_model",
    "ensure_models",
    "find_model",
    "list_model_status",
    "model_search_paths",
    "models_dir",
]

log = get_logger("models")

_BASE = "https://storage.googleapis.com/mediapipe-models"


@dataclass(frozen=True)
class ModelSpec:
    """A downloadable model bundle."""

    key: str
    filename: str
    url: str
    size_mb: float
    purpose: str

    def describe(self) -> str:
        return f"{self.filename} ({self.size_mb:.1f} MB) — {self.purpose}"


MODELS: Dict[str, ModelSpec] = {
    "face_landmarker": ModelSpec(
        key="face_landmarker",
        filename="face_landmarker.task",
        url=f"{_BASE}/face_landmarker/face_landmarker/float16/1/face_landmarker.task",
        size_mb=3.7,
        purpose="478 face landmarks + 52 expression blendshapes",
    ),
    "hand_landmarker": ModelSpec(
        key="hand_landmarker",
        filename="hand_landmarker.task",
        url=f"{_BASE}/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task",
        size_mb=7.8,
        purpose="21 hand landmarks per hand + handedness",
    ),
    "gesture_recognizer": ModelSpec(
        key="gesture_recognizer",
        filename="gesture_recognizer.task",
        url=f"{_BASE}/gesture_recognizer/gesture_recognizer/float16/1/gesture_recognizer.task",
        size_mb=8.4,
        purpose="MediaPipe's canned 7-gesture classifier (optional cross-check)",
    ),
    "selfie_segmenter": ModelSpec(
        key="selfie_segmenter",
        filename="selfie_segmenter.tflite",
        url=f"{_BASE}/image_segmenter/selfie_segmenter/float16/latest/selfie_segmenter.tflite",
        size_mb=0.25,
        purpose="person/background mask for background blur & replacement",
    ),
    "selfie_multiclass": ModelSpec(
        key="selfie_multiclass",
        filename="selfie_multiclass_256x256.tflite",
        url=f"{_BASE}/image_segmenter/selfie_multiclass_256x256/float32/latest/selfie_multiclass_256x256.tflite",
        size_mb=16.0,
        purpose="6-class segmentation: hair, skin, clothes, background…",
    ),
    "yunet_face": ModelSpec(
        key="yunet_face",
        filename="face_detection_yunet_2023mar.onnx",
        url=(
            "https://github.com/opencv/opencv_zoo/raw/main/models/"
            "face_detection_yunet/face_detection_yunet_2023mar.onnx"
        ),
        size_mb=0.23,
        purpose="tiny OpenCV face detector — the no-MediaPipe fallback (5 landmarks)",
    ),
    "pose_landmarker": ModelSpec(
        key="pose_landmarker",
        filename="pose_landmarker_lite.task",
        url=f"{_BASE}/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task",
        size_mb=5.5,
        purpose="33 body landmarks (optional full-body mode)",
    ),
}


def _user_cache_dir() -> Path:
    override = os.environ.get("MIRRORLAB_MODELS")
    if override:
        return Path(override).expanduser()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "mirrorlab" / "models"
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / "mirrorlab" / "models"
        return Path.home() / "AppData" / "Local" / "mirrorlab" / "models"
    base = os.environ.get("XDG_CACHE_HOME") or (Path.home() / ".cache")
    return Path(base) / "mirrorlab" / "models"


def models_dir(create: bool = True) -> Path:
    """Return the writable cache directory for model bundles."""
    target = _user_cache_dir()
    if create:
        target.mkdir(parents=True, exist_ok=True)
    return target


def model_search_paths() -> List[Path]:
    """Every directory probed for an already-downloaded model, in order."""
    package_data = Path(__file__).resolve().parent.parent / "data" / "models"
    cwd_models = Path.cwd() / "models"
    candidates = [package_data, cwd_models, _user_cache_dir()]
    override = os.environ.get("MIRRORLAB_MODELS")
    if override:
        candidates.insert(0, Path(override).expanduser())
    seen: List[Path] = []
    for path in candidates:
        if path not in seen:
            seen.append(path)
    return seen


def _is_probably_valid(path: Path, spec: Optional[ModelSpec] = None) -> bool:
    """Cheap sanity check: exists, non-trivial size, and not an HTML error page."""
    if not path.is_file():
        return False
    size = path.stat().st_size
    if size < 1024:
        return False
    if spec is not None and size < spec.size_mb * 1024 * 1024 * 0.25:
        # A truncated download — re-fetch rather than fail deep inside MediaPipe.
        return False
    try:
        with path.open("rb") as handle:
            head = handle.read(64).lstrip()
    except OSError:
        return False
    return not head.startswith(b"<")


def find_model(key: str) -> Optional[Path]:
    """Return the path of an already-present model, or ``None``."""
    spec = MODELS.get(key)
    filename = spec.filename if spec else key
    for directory in model_search_paths():
        candidate = directory / filename
        if _is_probably_valid(candidate, spec):
            return candidate
    return None


def _download(url: str, target: Path, timeout: float = 120.0) -> Path:
    """Stream ``url`` into ``target`` atomically (download to a temp file first)."""
    target.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "mirrorlab"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        total = int(response.headers.get("Content-Length") or 0)
        with tempfile.NamedTemporaryFile(dir=str(target.parent), prefix=".download-", delete=False) as handle:
            temp_path = Path(handle.name)
            shutil.copyfileobj(response, handle, length=1024 * 256)
    if total and temp_path.stat().st_size < total * 0.9:
        temp_path.unlink(missing_ok=True)
        raise OSError(f"Truncated download for {url} ({temp_path.stat().st_size}/{total} bytes)")
    temp_path.replace(target)
    return target


def download_model(
    key: str,
    *,
    force: bool = False,
    progress: Optional[Callable[[str], None]] = None,
) -> Path:
    """Download a model into the cache and return its path.

    Raises:
        KeyError: unknown model key.
        OSError: network or filesystem failure, with an actionable message.
    """
    if key not in MODELS:
        raise KeyError(f"Unknown model {key!r}. Known models: {', '.join(sorted(MODELS))}")
    spec = MODELS[key]
    target = models_dir() / spec.filename

    if not force and _is_probably_valid(target, spec):
        return target

    notify = progress or (lambda message: log.info("%s", message))
    notify(f"Downloading {spec.describe()} …")
    try:
        _download(spec.url, target)
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        raise OSError(
            f"Could not download the {key} model from {spec.url}\n"
            f"  Reason: {exc}\n"
            f"  Fix: check your connection, or download the file manually into\n"
            f"       {models_dir()}\n"
            f"       and re-run. MirrorLab works offline once a model is cached."
        ) from exc
    notify(f"Cached {spec.filename} → {target}")
    return target


def ensure_model(
    key: str, auto_download: bool = True, progress: Optional[Callable[[str], None]] = None
) -> Optional[Path]:
    """Return the model path, downloading it when allowed and necessary."""
    found = find_model(key)
    if found is not None:
        return found
    if not auto_download:
        return None
    try:
        return download_model(key, progress=progress)
    except (OSError, KeyError) as exc:
        log.warning("Model %s unavailable (%s). Continuing with reduced features.", key, exc)
        return None


def ensure_models(keys: List[str], auto_download: bool = True) -> Dict[str, Optional[Path]]:
    """Resolve several models at once."""
    return {key: ensure_model(key, auto_download=auto_download) for key in keys}


def list_model_status() -> List[dict]:
    """Report which models are cached — used by ``mirrorlab models --status``."""
    rows = []
    for key, spec in sorted(MODELS.items()):
        found = find_model(key)
        rows.append(
            {
                "key": key,
                "filename": spec.filename,
                "size_mb": spec.size_mb,
                "purpose": spec.purpose,
                "cached": found is not None,
                "path": str(found) if found else "",
                "url": spec.url,
            }
        )
    return rows
