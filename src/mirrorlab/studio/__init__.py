"""MirrorLab Studio: a virtual camera with background, framing, light and gesture control.

Typical use is the command line (``mirrorlab cam``), but every piece is a plain
class that can be used on its own::

    from mirrorlab.studio import StudioSettings, StudioPipeline

    settings = StudioSettings.load(profile="meeting")
    pipeline = StudioPipeline(settings)          # no detectors: framing/light/shutter only
    result = pipeline.process(frame_bgr)
    result.output                                 # BGR frame, ready to publish

See ``docs/STUDIO.md`` for the architecture, the platform setup and the control protocol.
"""

from .background import BackgroundProcessor, TemporalMask, blur_background
from .framing import AutoFramer
from .light import StudioLight
from .pipeline import FrameResult, StudioPipeline
from .privacy import AwayDetector, PrivacyShutter
from .reactions import REACTIONS, ReactionStage
from .session import LatencyStats, SessionReport, StudioSession
from .settings import PROFILES, StudioSettings
from .state import ActionResult, StudioState
from .vcam import MemorySink, NullSink, OutputError, VirtualCameraSink, probe

__all__ = [
    "PROFILES",
    "REACTIONS",
    "ActionResult",
    "AutoFramer",
    "AwayDetector",
    "BackgroundProcessor",
    "FrameResult",
    "LatencyStats",
    "MemorySink",
    "NullSink",
    "OutputError",
    "PrivacyShutter",
    "ReactionStage",
    "SessionReport",
    "StudioLight",
    "StudioPipeline",
    "StudioSession",
    "StudioSettings",
    "StudioState",
    "TemporalMask",
    "VirtualCameraSink",
    "blur_background",
    "probe",
]
