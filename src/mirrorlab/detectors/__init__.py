"""Detector layer: backends, model management, and the perception engine."""

from __future__ import annotations

from .backends import (
    HaarFaceBackend,
    NullFaceBackend,
    NullHandBackend,
    SolutionsFaceBackend,
    SolutionsHandBackend,
    TasksFaceBackend,
    TasksHandBackend,
    YuNetFaceBackend,
    create_face_backend,
    create_hand_backend,
    mediapipe_available,
    mediapipe_version,
    probe_environment,
)
from .base import (
    BLENDSHAPE_NAMES,
    FACE_OVAL,
    FINGER_NAMES,
    HAND_CONNECTIONS,
    FaceObservation,
    FrameAnalysis,
    HandObservation,
    Landmark,
)
from .engine import PerceptionEngine, PerceptionResult
from .face import FaceDetector
from .hands import HandDetector
from .models import MODELS, ModelSpec, download_model, ensure_model, find_model, list_model_status, models_dir

__all__ = [
    "BLENDSHAPE_NAMES",
    "FACE_OVAL",
    "FINGER_NAMES",
    "HAND_CONNECTIONS",
    "MODELS",
    "FaceDetector",
    "FaceObservation",
    "FrameAnalysis",
    "HaarFaceBackend",
    "HandDetector",
    "HandObservation",
    "Landmark",
    "ModelSpec",
    "NullFaceBackend",
    "NullHandBackend",
    "PerceptionEngine",
    "PerceptionResult",
    "SolutionsFaceBackend",
    "SolutionsHandBackend",
    "TasksFaceBackend",
    "TasksHandBackend",
    "YuNetFaceBackend",
    "create_face_backend",
    "create_hand_backend",
    "download_model",
    "ensure_model",
    "find_model",
    "list_model_status",
    "mediapipe_available",
    "mediapipe_version",
    "models_dir",
    "probe_environment",
]
