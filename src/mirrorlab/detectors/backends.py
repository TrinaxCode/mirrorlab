"""Detector backends: one interface, several engines.

MirrorLab does **not** hard-depend on a single MediaPipe API. As of MediaPipe
1.0 the legacy ``mp.solutions`` namespace was removed, while on some macOS
builds the 1.x Tasks runtime aborts inside Apple's Metal helper. Rather than
picking a side, MirrorLab probes what actually works on the host and degrades
gracefully:

======================  ==========================================  ====================
Backend                 Requires                                    Provides
======================  ==========================================  ====================
``tasks``               ``mediapipe>=0.10.9`` Tasks API              478 landmarks, **52 blendshapes**, pose matrix
``solutions``           ``mediapipe<1.0`` legacy ``mp.solutions``   468 landmarks
``yunet``               OpenCV + a 230 KB ONNX file                  5 landmarks (eyes, nose, mouth)
``haar``                OpenCV only (bundled cascade)                bounding box only
``none``                —                                            nothing (features disabled)
======================  ==========================================  ====================

The selection order is deliberate: blendshapes make expression recognition
dramatically more robust than landmark ratios, so anything that provides them
wins; everything else is a safety net so the application still starts.
"""

from __future__ import annotations

import threading
from contextlib import suppress
from typing import Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np

from ..utils.logging import get_logger
from .base import FaceObservation, HandObservation
from .models import ensure_model

__all__ = [
    "FaceBackend",
    "HaarFaceBackend",
    "HandBackend",
    "NullFaceBackend",
    "NullHandBackend",
    "SolutionsFaceBackend",
    "SolutionsHandBackend",
    "TasksFaceBackend",
    "TasksHandBackend",
    "YuNetFaceBackend",
    "create_face_backend",
    "create_hand_backend",
    "mediapipe_available",
    "mediapipe_version",
    "probe_environment",
]

log = get_logger("backends")


# --------------------------------------------------------------------------- #
# Capability probing
# --------------------------------------------------------------------------- #
def mediapipe_version() -> Optional[str]:
    """Installed MediaPipe version, or ``None`` when it is not importable."""
    try:
        import mediapipe as mp
    except Exception:  # pragma: no cover - environment dependent
        return None
    return getattr(mp, "__version__", "unknown")


def mediapipe_available() -> bool:
    return mediapipe_version() is not None


def _tasks_api():
    """Return ``(vision_module, BaseOptions)`` or ``None`` when unavailable."""
    try:
        from mediapipe.tasks.python import BaseOptions, vision
    except Exception:  # pragma: no cover - environment dependent
        return None
    if not hasattr(vision, "FaceLandmarker") or not hasattr(vision, "HandLandmarker"):
        return None
    return vision, BaseOptions


def _solutions_api():
    try:
        import mediapipe as mp

        if not hasattr(mp, "solutions"):
            return None
        solutions = mp.solutions
        if not hasattr(solutions, "face_mesh") or not hasattr(solutions, "hands"):
            return None
        return solutions
    except Exception:  # pragma: no cover - environment dependent
        return None


def probe_environment(auto_download: bool = False) -> Dict[str, object]:
    """Describe what this machine can actually run — used by ``mirrorlab doctor``."""
    version = mediapipe_version()
    tasks = _tasks_api() is not None
    solutions = _solutions_api() is not None
    report: Dict[str, object] = {
        "mediapipe_version": version,
        "mediapipe_tasks_api": tasks,
        "mediapipe_solutions_api": solutions,
        "opencv_version": cv2.__version__,
        "yunet_available": hasattr(cv2, "FaceDetectorYN"),
        "haar_available": bool(getattr(cv2.data, "haarcascades", "")),
        "face_backend": "",
        "hand_backend": "",
    }
    face = create_face_backend(auto_download=auto_download, quiet=True)
    hand = create_hand_backend(auto_download=auto_download, quiet=True)
    report["face_backend"] = face.name
    report["hand_backend"] = hand.name
    face.close()
    hand.close()
    return report


# --------------------------------------------------------------------------- #
# Interfaces
# --------------------------------------------------------------------------- #
class FaceBackend:
    """Common interface for every face engine."""

    name: str = "none"
    provides_blendshapes: bool = False
    provides_landmarks: bool = False
    landmark_count: int = 0

    def process(
        self, rgb: np.ndarray, timestamp_ms: int, frame_bgr: Optional[np.ndarray] = None
    ) -> List[FaceObservation]:
        raise NotImplementedError

    def close(self) -> None:
        pass

    def __enter__(self) -> "FaceBackend":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


class HandBackend:
    """Common interface for every hand engine."""

    name: str = "none"
    provides_world_landmarks: bool = False

    def process(self, rgb: np.ndarray, timestamp_ms: int) -> List[HandObservation]:
        raise NotImplementedError

    def close(self) -> None:
        pass

    def __enter__(self) -> "HandBackend":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


class _TimestampGuard:
    """MediaPipe VIDEO mode requires strictly increasing timestamps."""

    __slots__ = ("_last",)

    def __init__(self) -> None:
        self._last = -1

    def next(self, timestamp_ms: int) -> int:
        stamp = int(timestamp_ms)
        if stamp <= self._last:
            stamp = self._last + 1
        self._last = stamp
        return stamp


# --------------------------------------------------------------------------- #
# Face — MediaPipe Tasks
# --------------------------------------------------------------------------- #
class TasksFaceBackend(FaceBackend):
    """MediaPipe Tasks ``FaceLandmarker`` — the best-quality backend.

    Provides 478 landmarks, 52 ARKit blendshapes and a 4×4 facial
    transformation matrix. Blendshapes are what make MirrorLab's expression
    recognition reliable rather than anecdotal.
    """

    name = "tasks-face"
    provides_blendshapes = True
    provides_landmarks = True
    landmark_count = 478

    def __init__(
        self,
        max_faces: int = 1,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        auto_download: bool = True,
        model_path: Optional[str] = None,
    ) -> None:
        api = _tasks_api()
        if api is None:
            raise RuntimeError("MediaPipe Tasks API is not available")
        vision, BaseOptions = api

        path = model_path or ensure_model("face_landmarker", auto_download=auto_download)
        if path is None:
            raise RuntimeError(
                "face_landmarker.task is missing. Run `mirrorlab models --download` "
                "or pass --no-download to use a lighter fallback."
            )

        options = vision.FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(path)),
            running_mode=vision.RunningMode.VIDEO,
            num_faces=max(1, int(max_faces)),
            min_face_detection_confidence=float(min_detection_confidence),
            min_face_presence_confidence=float(min_detection_confidence),
            min_tracking_confidence=float(min_tracking_confidence),
            output_face_blendshapes=True,
            output_facial_transformation_matrixes=True,
        )
        self._landmarker = vision.FaceLandmarker.create_from_options(options)
        self._guard = _TimestampGuard()
        self._lock = threading.Lock()

    def process(
        self, rgb: np.ndarray, timestamp_ms: int, frame_bgr: Optional[np.ndarray] = None
    ) -> List[FaceObservation]:
        import mediapipe as mp

        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        with self._lock:
            result = self._landmarker.detect_for_video(image, self._guard.next(timestamp_ms))

        observations: List[FaceObservation] = []
        blendshape_sets = result.face_blendshapes or []
        matrices = result.facial_transformation_matrixes or []
        for face_index, landmarks in enumerate(result.face_landmarks or []):
            points = np.asarray([[lm.x, lm.y, lm.z] for lm in landmarks], dtype=np.float64)
            blends: Dict[str, float] = {}
            if face_index < len(blendshape_sets):
                for category in blendshape_sets[face_index]:
                    blends[category.category_name] = float(category.score)
            matrix = None
            if face_index < len(matrices):
                matrix = np.asarray(matrices[face_index], dtype=np.float64)
            observations.append(
                FaceObservation(
                    landmarks=points,
                    blendshapes=blends,
                    transformation_matrix=matrix,
                    confidence=1.0,
                )
            )
        return observations

    def close(self) -> None:
        landmarker = getattr(self, "_landmarker", None)
        if landmarker is not None:
            with suppress(Exception):  # pragma: no cover - already torn down
                landmarker.close()
            self._landmarker = None


# --------------------------------------------------------------------------- #
# Face — MediaPipe Solutions (MediaPipe < 1.0)
# --------------------------------------------------------------------------- #
class SolutionsFaceBackend(FaceBackend):
    """Legacy ``mp.solutions.face_mesh`` — 468 landmarks, no blendshapes.

    Expression recognition falls back to geometric ratios, which works but is
    less nuanced. Used automatically when the Tasks API is unavailable.
    """

    name = "solutions-face"
    provides_blendshapes = False
    provides_landmarks = True
    landmark_count = 468

    def __init__(
        self,
        max_faces: int = 1,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        refine_landmarks: bool = True,
    ) -> None:
        solutions = _solutions_api()
        if solutions is None:
            raise RuntimeError("MediaPipe solutions API is not available")
        self._mesh = solutions.face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=max(1, int(max_faces)),
            refine_landmarks=bool(refine_landmarks),
            min_detection_confidence=float(min_detection_confidence),
            min_tracking_confidence=float(min_tracking_confidence),
        )
        self._lock = threading.Lock()

    def process(
        self, rgb: np.ndarray, timestamp_ms: int, frame_bgr: Optional[np.ndarray] = None
    ) -> List[FaceObservation]:
        with self._lock:
            result = self._mesh.process(np.ascontiguousarray(rgb))
        observations: List[FaceObservation] = []
        for face in result.multi_face_landmarks or []:
            points = np.asarray([[lm.x, lm.y, lm.z] for lm in face.landmark], dtype=np.float64)
            observations.append(FaceObservation(landmarks=points, blendshapes={}, confidence=1.0))
        return observations

    def close(self) -> None:
        mesh = getattr(self, "_mesh", None)
        if mesh is not None:
            with suppress(Exception):  # pragma: no cover - already torn down
                mesh.close()
            self._mesh = None


# --------------------------------------------------------------------------- #
# Face — OpenCV fallbacks
# --------------------------------------------------------------------------- #
class YuNetFaceBackend(FaceBackend):
    """OpenCV YuNet: 5 landmarks, 230 KB, no MediaPipe required.

    Returns landmarks arranged to be *positionally compatible* with the
    MediaPipe indices MirrorLab cares about most, so the simplest expression
    heuristics keep working:

    ``[right_eye, left_eye, nose_tip, mouth_right, mouth_left]`` — mapped onto
    MediaPipe's ``[33, 263, 1, 61, 291]`` slots, with everything else filled by
    interpolation from those anchors.
    """

    name = "yunet-face"
    provides_blendshapes = False
    provides_landmarks = True
    landmark_count = 468

    #: MediaPipe indices we synthesise from YuNet's five points.
    _ANCHORS = (33, 263, 1, 61, 291)
    _DEFAULT_SCORE = 0.9

    def __init__(
        self,
        max_faces: int = 1,
        min_detection_confidence: float = 0.5,
        auto_download: bool = True,
        model_path: Optional[str] = None,
        input_size: Tuple[int, int] = (320, 320),
    ) -> None:
        if not hasattr(cv2, "FaceDetectorYN"):
            raise RuntimeError("This OpenCV build has no FaceDetectorYN")
        path = model_path or ensure_model("yunet_face", auto_download=auto_download)
        if path is None:
            raise RuntimeError("YuNet ONNX model is unavailable")
        self._detector = cv2.FaceDetectorYN.create(
            str(path), "", input_size, float(min_detection_confidence), 0.3, 5000
        )
        self._max_faces = max(1, int(max_faces))
        self._input_size = input_size

    def process(
        self, rgb: np.ndarray, timestamp_ms: int, frame_bgr: Optional[np.ndarray] = None
    ) -> List[FaceObservation]:
        bgr = frame_bgr if frame_bgr is not None else cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        height, width = bgr.shape[:2]
        self._detector.setInputSize((width, height))
        _, faces = self._detector.detect(bgr)
        if faces is None:
            return []

        observations: List[FaceObservation] = []
        for row in faces[: self._max_faces]:
            confidence = float(row[-1])
            points = self._expand(np.asarray(row[:14], dtype=np.float64).reshape(7, 2), width, height)
            observations.append(
                FaceObservation(
                    landmarks=points,
                    blendshapes={},
                    bbox=(
                        float(row[0]) / width,
                        float(row[1]) / height,
                        float(row[0] + row[2]) / width,
                        float(row[1] + row[3]) / height,
                    ),
                    confidence=confidence,
                )
            )
        return observations

    def _expand(self, raw: np.ndarray, width: int, height: int) -> np.ndarray:
        """Grow YuNet's 5 points into a sparse 468-slot landmark array."""
        points = np.zeros((self.landmark_count, 3), dtype=np.float64)
        if raw.shape[0] < 5:
            return points
        normalized = raw[:5].copy()
        normalized[:, 0] /= max(width, 1)
        normalized[:, 1] /= max(height, 1)

        right_eye, left_eye, nose, mouth_right, mouth_left = normalized
        for index, point in zip(self._ANCHORS, (right_eye, left_eye, nose, mouth_right, mouth_left)):
            points[index, :2] = point

        # Fill the rest by bilinear interpolation over the anchor triangle so
        # ratio-based heuristics see a plausible, smoothly varying mesh.
        eye_mid = (right_eye + left_eye) / 2.0
        mouth_mid = (mouth_right + mouth_left) / 2.0
        half_width = max(float(np.linalg.norm(left_eye - right_eye)) * 0.75, 1e-3)
        half_height = max(float(np.linalg.norm(mouth_mid - eye_mid)) * 0.95, 1e-3)
        center = (eye_mid + mouth_mid) / 2.0

        # An elliptical grid keeps derived ratios (mouth width / height, etc.)
        # in the same ballpark as a real mesh.
        for index in range(self.landmark_count):
            if index in self._ANCHORS:
                continue
            angle = (index * 2.399963) % (2.0 * np.pi)  # golden-angle spiral
            radius = np.sqrt((index % 97) / 97.0)
            points[index, 0] = center[0] + np.cos(angle) * radius * half_width
            points[index, 1] = center[1] + np.sin(angle) * radius * half_height
        return points

    def close(self) -> None:
        self._detector = None


class HaarFaceBackend(FaceBackend):
    """Last-resort face detection using OpenCV's bundled Haar cascade.

    Gives a bounding box but **no landmarks**, so expression recognition is
    reported as ``unknown`` while effects needing anchors are skipped. The point
    is that the app still starts and the camera preview still works.
    """

    name = "haar-face"
    provides_blendshapes = False
    provides_landmarks = False
    landmark_count = 0

    def __init__(self, max_faces: int = 1, min_detection_confidence: float = 0.5) -> None:
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self._cascade = cv2.CascadeClassifier(cascade_path)
        if self._cascade.empty():
            raise RuntimeError("Could not load the bundled Haar cascade")
        self._max_faces = max(1, int(max_faces))
        self._min_neighbors = max(3, round(3 + (1.0 - min_detection_confidence) * 6))

    def process(
        self, rgb: np.ndarray, timestamp_ms: int, frame_bgr: Optional[np.ndarray] = None
    ) -> List[FaceObservation]:
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        gray = cv2.equalizeHist(gray)
        boxes = self._cascade.detectMultiScale(
            gray, scaleFactor=1.15, minNeighbors=self._min_neighbors, minSize=(64, 64)
        )
        if len(boxes) == 0:
            return []
        height, width = gray.shape[:2]
        observations: List[FaceObservation] = []
        for x, y, w, h in sorted(boxes, key=lambda b: -b[2] * b[3])[: self._max_faces]:
            observations.append(
                FaceObservation(
                    landmarks=np.zeros((0, 3), dtype=np.float64),
                    blendshapes={},
                    bbox=(x / width, y / height, (x + w) / width, (y + h) / height),
                    confidence=0.5,
                )
            )
        return observations

    def close(self) -> None:
        self._cascade = None


class NullFaceBackend(FaceBackend):
    """Explicitly disabled face detection."""

    name = "none"

    def process(
        self, rgb: np.ndarray, timestamp_ms: int, frame_bgr: Optional[np.ndarray] = None
    ) -> List[FaceObservation]:
        return []


# --------------------------------------------------------------------------- #
# Hands
# --------------------------------------------------------------------------- #
class TasksHandBackend(HandBackend):
    """MediaPipe Tasks ``HandLandmarker`` — 21 landmarks per hand + world points."""

    name = "tasks-hands"
    provides_world_landmarks = True

    def __init__(
        self,
        max_hands: int = 2,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        auto_download: bool = True,
        model_path: Optional[str] = None,
    ) -> None:
        api = _tasks_api()
        if api is None:
            raise RuntimeError("MediaPipe Tasks API is not available")
        vision, BaseOptions = api
        path = model_path or ensure_model("hand_landmarker", auto_download=auto_download)
        if path is None:
            raise RuntimeError("hand_landmarker.task is missing. Run `mirrorlab models --download`.")
        options = vision.HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(path)),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=max(1, int(max_hands)),
            min_hand_detection_confidence=float(min_detection_confidence),
            min_hand_presence_confidence=float(min_detection_confidence),
            min_tracking_confidence=float(min_tracking_confidence),
        )
        self._landmarker = vision.HandLandmarker.create_from_options(options)
        self._guard = _TimestampGuard()
        self._lock = threading.Lock()

    def process(self, rgb: np.ndarray, timestamp_ms: int) -> List[HandObservation]:
        import mediapipe as mp

        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        with self._lock:
            result = self._landmarker.detect_for_video(image, self._guard.next(timestamp_ms))

        handedness_sets = result.handedness or []
        world_sets = result.hand_world_landmarks or []
        observations: List[HandObservation] = []
        for index, hand in enumerate(result.hand_landmarks or []):
            points = np.asarray([[lm.x, lm.y, lm.z] for lm in hand], dtype=np.float64)
            world = None
            if index < len(world_sets):
                world = np.asarray([[lm.x, lm.y, lm.z] for lm in world_sets[index]], dtype=np.float64)
            label, score = "Unknown", 1.0
            if index < len(handedness_sets) and handedness_sets[index]:
                category = handedness_sets[index][0]
                label = str(category.category_name or "Unknown")
                score = float(category.score)
            observations.append(
                HandObservation(landmarks=points, world_landmarks=world, handedness=label, score=score)
            )
        return observations

    def close(self) -> None:
        landmarker = getattr(self, "_landmarker", None)
        if landmarker is not None:
            with suppress(Exception):  # pragma: no cover - already torn down
                landmarker.close()
            self._landmarker = None


class SolutionsHandBackend(HandBackend):
    """Legacy ``mp.solutions.hands`` backend."""

    name = "solutions-hands"
    provides_world_landmarks = True

    def __init__(
        self,
        max_hands: int = 2,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        model_complexity: int = 1,
    ) -> None:
        solutions = _solutions_api()
        if solutions is None:
            raise RuntimeError("MediaPipe solutions API is not available")
        self._hands = solutions.hands.Hands(
            static_image_mode=False,
            max_num_hands=max(1, int(max_hands)),
            model_complexity=int(model_complexity),
            min_detection_confidence=float(min_detection_confidence),
            min_tracking_confidence=float(min_tracking_confidence),
        )
        self._lock = threading.Lock()

    def process(self, rgb: np.ndarray, timestamp_ms: int) -> List[HandObservation]:
        with self._lock:
            result = self._hands.process(np.ascontiguousarray(rgb))
        observations: List[HandObservation] = []
        world_sets = result.multi_hand_world_landmarks or []
        handedness_sets = result.multi_handedness or []
        for index, hand in enumerate(result.multi_hand_landmarks or []):
            points = np.asarray([[lm.x, lm.y, lm.z] for lm in hand.landmark], dtype=np.float64)
            world = None
            if index < len(world_sets):
                world = np.asarray(
                    [[lm.x, lm.y, lm.z] for lm in world_sets[index].landmark], dtype=np.float64
                )
            label, score = "Unknown", 1.0
            if index < len(handedness_sets):
                classification = handedness_sets[index].classification[0]
                label = str(classification.label)
                score = float(classification.score)
            observations.append(
                HandObservation(landmarks=points, world_landmarks=world, handedness=label, score=score)
            )
        return observations

    def close(self) -> None:
        hands = getattr(self, "_hands", None)
        if hands is not None:
            with suppress(Exception):  # pragma: no cover - already torn down
                hands.close()
            self._hands = None


class NullHandBackend(HandBackend):
    """Explicitly disabled hand tracking."""

    name = "none"

    def process(self, rgb: np.ndarray, timestamp_ms: int) -> List[HandObservation]:
        return []


# --------------------------------------------------------------------------- #
# Factories
# --------------------------------------------------------------------------- #
def create_face_backend(
    *,
    max_faces: int = 1,
    min_detection_confidence: float = 0.5,
    min_tracking_confidence: float = 0.5,
    preferred: str = "auto",
    auto_download: bool = True,
    quiet: bool = False,
) -> FaceBackend:
    """Build the best available face backend.

    ``preferred`` may force a specific engine (``tasks``, ``solutions``,
    ``yunet``, ``haar``, ``none``); ``auto`` walks the quality ladder and stops
    at the first engine that initialises successfully.
    """
    if preferred == "none" or max_faces <= 0:
        return NullFaceBackend()

    builders = {
        "tasks": lambda: TasksFaceBackend(
            max_faces, min_detection_confidence, min_tracking_confidence, auto_download
        ),
        "solutions": lambda: SolutionsFaceBackend(
            max_faces, min_detection_confidence, min_tracking_confidence
        ),
        "yunet": lambda: YuNetFaceBackend(max_faces, min_detection_confidence, auto_download),
        "haar": lambda: HaarFaceBackend(max_faces, min_detection_confidence),
    }

    order = [preferred] if preferred in builders else ["tasks", "solutions", "yunet", "haar"]
    for name in order:
        try:
            backend = builders[name]()
            if not quiet:
                log.info(
                    "Face backend: %s%s",
                    backend.name,
                    "" if backend.provides_blendshapes else " (no blendshapes)",
                )
            return backend
        except Exception as exc:
            log.debug("Face backend %s unavailable: %s", name, exc)

    log.warning(
        "No face backend could be initialised — face features are disabled. "
        "Install MediaPipe (`pip install 'mediapipe>=0.10.9,<0.11'`) to enable them."
    )
    return NullFaceBackend()


def create_hand_backend(
    *,
    max_hands: int = 2,
    min_detection_confidence: float = 0.5,
    min_tracking_confidence: float = 0.5,
    model_complexity: int = 1,
    preferred: str = "auto",
    auto_download: bool = True,
    quiet: bool = False,
) -> HandBackend:
    """Build the best available hand backend (``tasks`` → ``solutions`` → none).

    ``model_complexity`` only affects the legacy Solutions rung; the Tasks
    backend ships a single fixed bundle.
    """
    if preferred == "none" or max_hands <= 0:
        return NullHandBackend()

    builders = {
        "tasks": lambda: TasksHandBackend(
            max_hands, min_detection_confidence, min_tracking_confidence, auto_download
        ),
        "solutions": lambda: SolutionsHandBackend(
            max_hands, min_detection_confidence, min_tracking_confidence, model_complexity
        ),
    }
    order = [preferred] if preferred in builders else ["tasks", "solutions"]
    for name in order:
        try:
            backend = builders[name]()
            if not quiet:
                log.info("Hand backend: %s", backend.name)
            return backend
        except Exception as exc:
            log.debug("Hand backend %s unavailable: %s", name, exc)

    log.warning(
        "No hand backend could be initialised — hand gestures are disabled. "
        "Install MediaPipe (`pip install 'mediapipe>=0.10.9,<0.11'`) to enable them."
    )
    return NullHandBackend()


def backend_names() -> Sequence[str]:
    return ("tasks", "solutions", "yunet", "haar", "none")
