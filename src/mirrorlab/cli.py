"""Command-line interface.

``mirrorlab`` is designed so the *first* command a user types works, and every
error message tells them exactly what to type next::

    mirrorlab                      # just run it
    mirrorlab doctor               # is my machine ready?
    mirrorlab filters              # what can it do?
    mirrorlab gestures             # how do I drive it?
    mirrorlab run --filter cartoon --effect sunglasses
    mirrorlab benchmark --filter cartoon

Every subcommand supports ``--help`` and ``--json`` where a machine-readable
form makes sense (used by the website's catalog generator).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .config import DEFAULTS, Config
from .version import CODENAME, __version__

__all__ = ["build_parser", "main"]

#: Terminal helpers that degrade gracefully when colour is unavailable.
_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_CYAN = "\033[38;5;80m"
_VIOLET = "\033[38;5;141m"
_AMBER = "\033[38;5;214m"


def _colour(text: str, code: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"{code}{text}{_RESET}"


BANNER = r"""
   ╭──────────────────────────────────────────────────────────╮
   │   ███╗   ███╗██╗██████╗ ██████╗  ██████╗ ██████╗         │
   │   ████╗ ████║██║██╔══██╗██╔══██╗██╔═══██╗██╔══██╗        │
   │   ██╔████╔██║██║██████╔╝██████╔╝██║   ██║██████╔╝        │
   │   ██║╚██╔╝██║██║██╔══██╗██╔══██╗██║   ██║██╔══██╗        │
   │   ██║ ╚═╝ ██║██║██║  ██║██║  ██║╚██████╔╝██║  ██║        │
   │   ╚═╝     ╚═╝╚═╝╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝        │
   ╰──────────────────────────────────────────────────────────╯
"""


def _banner() -> str:
    return _colour(BANNER, _CYAN) + _colour(f"   webcam AI playground · v{__version__} “{CODENAME}”\n", _DIM)


# --------------------------------------------------------------------------- #
# Parser
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mirrorlab",
        description=(
            "MirrorLab — a webcam AI playground: facial expressions, hand gestures "
            "and 54 real-time filters. CPU only, no account, nothing uploaded."
        ),
        epilog=(
            "Examples:\n"
            "  mirrorlab                                  run with defaults\n"
            "  mirrorlab run --filter cartoon --effect sunglasses\n"
            "  mirrorlab run --preset noir --filter sketch\n"
            "  mirrorlab doctor                           check this machine\n"
            "  mirrorlab filters --category artistic\n"
            "  mirrorlab gestures                         hands-free cheat sheet\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"mirrorlab {__version__} ({CODENAME})")
    parser.add_argument("--json", action="store_true", help="machine-readable output where supported")
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")

    # Subparsers do not inherit options, so shared flags live in a parent
    # parser. `default=SUPPRESS` stops the subparser from clobbering a value
    # already parsed at the top level (e.g. `mirrorlab --json filters`).
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--json", action="store_true", default=argparse.SUPPRESS, help="machine-readable output"
    )
    common.add_argument(
        "-v", "--verbose", action="store_true", default=argparse.SUPPRESS, help="debug logging"
    )

    sub = parser.add_subparsers(dest="command")

    # -- run ------------------------------------------------------------- #
    run = sub.add_parser("run", parents=[common], help="start the live playground (default command)")
    _add_run_arguments(run)

    # -- doctor ---------------------------------------------------------- #
    doctor = sub.add_parser("doctor", parents=[common], help="diagnose camera, GPU and model availability")
    doctor.add_argument("--download", action="store_true", help="also fetch any missing models")

    # -- filters --------------------------------------------------------- #
    filters = sub.add_parser("filters", parents=[common], help="list every filter")
    filters.add_argument("--category", help="restrict to one category")
    filters.add_argument("--presets", action="store_true", help="list curated presets instead")

    # -- gestures / expressions / effects --------------------------------- #
    sub.add_parser("gestures", parents=[common], help="list hand gestures and their actions")
    sub.add_parser("expressions", parents=[common], help="list detectable facial expressions")
    sub.add_parser("effects", parents=[common], help="list AR effects")

    # -- models ---------------------------------------------------------- #
    models = sub.add_parser("models", parents=[common], help="show or download model bundles")
    models.add_argument(
        "--download", nargs="*", metavar="KEY", help="download one or more models (no keys = all)"
    )
    models.add_argument("--status", action="store_true", help="show the cache status (default)")

    # -- benchmark ------------------------------------------------------- #
    bench = sub.add_parser("benchmark", parents=[common], help="measure filter and detector performance")
    bench.add_argument("--filter", dest="filters", action="append", help="filter to benchmark (repeatable)")
    bench.add_argument("--frames", type=int, default=30, help="frames per filter (default: 30)")
    bench.add_argument("--width", type=int, default=640, help="frame width (default: 640)")
    bench.add_argument("--height", type=int, default=480, help="frame height (default: 480)")
    bench.add_argument("--all", action="store_true", help="benchmark every filter")

    # -- demo ------------------------------------------------------------ #
    demo = sub.add_parser(
        "demo", parents=[common], help="run offline on a synthetic source (no camera needed)"
    )
    _add_run_arguments(demo)

    # -- config ---------------------------------------------------------- #
    config = sub.add_parser("config", parents=[common], help="inspect configuration")
    config.add_argument("--list", action="store_true", help="list every supported key and default")
    config.add_argument("--show", action="store_true", help="print the resolved configuration")
    config.add_argument("--init", metavar="PATH", help="write a commented config file")

    # -- cameras --------------------------------------------------------- #
    cameras = sub.add_parser("cameras", parents=[common], help="probe cameras and capture backends")
    cameras.add_argument("--max-index", type=int, default=5, help="highest camera index to probe")

    # -- gallery --------------------------------------------------------- #
    gallery = sub.add_parser("gallery", parents=[common], help="render a contact sheet of every filter")
    gallery.add_argument("--output", default="assets/filter-gallery.png", help="output image path")
    gallery.add_argument("--columns", type=int, default=6, help="grid columns")
    gallery.add_argument("--source", help="image or video to use instead of the synthetic pattern")

    return parser


def _add_run_arguments(parser: argparse.ArgumentParser) -> None:
    """Every flag maps 1:1 onto a :class:`~mirrorlab.config.Config` field."""
    parser.add_argument("-c", "--camera", type=int, default=None, help="camera index (default: 0)")
    parser.add_argument("--input", dest="input_path", help="use a video file instead of a camera")
    parser.add_argument("--backend", default=None, help="capture backend: auto|avfoundation|dshow|msmf|v4l2")
    parser.add_argument("--camera-width", type=int, default=None, help="capture width")
    parser.add_argument("--camera-height", type=int, default=None, help="capture height")
    parser.add_argument("--camera-fps", type=int, default=None, help="requested capture frame rate")

    parser.add_argument(
        "-f",
        "--filter",
        dest="filter_spec",
        default=None,
        help="filter name, or a chain like cartoon+vignette+glitch",
    )
    parser.add_argument(
        "--preset",
        choices=["cinema", "anime", "noir", "retro80s", "broken", "toon", "ghost", "studio", "paper", "vhs"],
        help="apply a curated multi-filter look",
    )
    parser.add_argument(
        "--effect",
        dest="effects",
        action="append",
        default=None,
        help="AR effect name (repeatable): sunglasses, dog, crown, fire…",
    )
    parser.add_argument(
        "--theme", default=None, choices=["aurora", "magma", "mono", "candy"], help="HUD colour theme"
    )

    parser.add_argument(
        "--hand",
        dest="enable_hands",
        action="store_true",
        default=None,
        help="enable hand tracking (on by default)",
    )
    parser.add_argument(
        "--no-hands", dest="enable_hands", action="store_false", help="disable hand tracking for extra speed"
    )
    parser.add_argument(
        "--no-face", dest="enable_face", action="store_false", default=None, help="disable face detection"
    )
    parser.add_argument(
        "--segment",
        dest="enable_segmentation",
        action="store_true",
        default=None,
        help="enable person segmentation (background blur/replace)",
    )
    parser.add_argument("--max-faces", type=int, default=None, help="maximum faces to track")
    parser.add_argument("--max-hands", type=int, default=None, help="maximum hands to track")

    parser.add_argument(
        "--face-backend",
        default="auto",
        choices=["auto", "tasks", "solutions", "yunet", "haar", "none"],
        help="force a face engine (default: auto — best available)",
    )
    parser.add_argument(
        "--hand-backend",
        default="auto",
        choices=["auto", "tasks", "solutions", "none"],
        help="force a hand engine",
    )
    parser.add_argument(
        "--no-download",
        dest="auto_download",
        action="store_false",
        default=True,
        help="never download models; use only what is cached",
    )

    parser.add_argument("--air-draw", action="store_true", default=None, help="start with air-draw enabled")
    parser.add_argument(
        "--no-gesture-control",
        dest="gesture_control",
        action="store_false",
        default=None,
        help="recognise gestures but do not let them trigger actions",
    )
    parser.add_argument("--no-hud", dest="show_hud", action="store_false", default=None, help="hide the HUD")
    parser.add_argument(
        "--no-landmarks",
        dest="show_landmarks",
        action="store_false",
        default=None,
        help="hide the landmark overlays",
    )
    parser.add_argument(
        "--no-mirror",
        dest="mirror",
        action="store_false",
        default=None,
        help="do not flip the image horizontally",
    )
    parser.add_argument(
        "--reactions",
        dest="show_reactions",
        action="store_true",
        default=None,
        help="show a reaction image per expression",
    )

    parser.add_argument("--output", dest="output_dir", default=None, help="directory for captures and clips")
    parser.add_argument("--record-codec", default=None, help="video codec fourcc (default: mp4v)")
    parser.add_argument("--stats-csv", default=None, help="append per-frame statistics to a CSV file")

    parser.add_argument(
        "--headless", action="store_true", default=None, help="no preview window (for servers and CI)"
    )
    parser.add_argument(
        "--frames", dest="max_frames", type=int, default=None, help="stop after N frames (0 = unlimited)"
    )
    parser.add_argument("--fullscreen", action="store_true", default=None, help="start fullscreen")


def _run_overrides(args: argparse.Namespace) -> Dict[str, Any]:
    """Translate parsed arguments into Config overrides, skipping unset flags."""
    mapping = {
        "camera": "camera_index",
        "backend": "camera_backend",
        "camera_width": "camera_width",
        "camera_height": "camera_height",
        "camera_fps": "camera_fps",
        "filter_spec": "filter",
        "theme": "theme",
        "enable_hands": "enable_hands",
        "enable_face": "enable_face",
        "enable_segmentation": "enable_segmentation",
        "max_faces": "max_faces",
        "max_hands": "max_hands",
        "gesture_control": "gesture_control",
        "show_hud": "show_hud",
        "show_landmarks": "show_landmarks",
        "mirror": "mirror",
        "show_reactions": "show_reactions",
        "output_dir": "output_dir",
        "record_codec": "record_codec",
        "stats_csv": "stats_csv",
        "headless": "headless",
        "max_frames": "max_frames",
        "fullscreen": "fullscreen",
    }
    overrides: Dict[str, Any] = {}
    for attribute, key in mapping.items():
        value = getattr(args, attribute, None)
        if value is not None:
            overrides[key] = value
    if getattr(args, "air_draw", None):
        overrides["air_draw"] = True
    effects = getattr(args, "effects", None)
    if effects:
        overrides["effects"] = list(effects)
    return overrides


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #
def _cmd_run(args: argparse.Namespace) -> int:
    from .app import MirrorLab
    from .camera import CameraError
    from .filters import PRESETS

    overrides = _run_overrides(args)
    if getattr(args, "preset", None):
        overrides["filter"] = PRESETS[args.preset]["filter"]
    if not args.json:
        print(_banner())
    try:
        config = Config.load(overrides=overrides)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    source: Optional[int | str] = args.input_path or args.camera or 0
    try:
        app = MirrorLab(config=config, source=source, synthetic=False)
    except CameraError as exc:
        print(f"\n{_colour('Camera error', _AMBER)}\n{exc}", file=sys.stderr)
        return 3
    except Exception as exc:
        print(f"error: could not start MirrorLab: {exc}", file=sys.stderr)
        return 1

    if not args.json:
        print(_shortcut_table(app))
    app.run()
    return 0


def _cmd_demo(args: argparse.Namespace) -> int:
    """Offline run: no camera, no permissions — used by CI and the smoke tests."""
    from .app import MirrorLab
    from .filters import PRESETS

    overrides = _run_overrides(args)
    if getattr(args, "preset", None):
        overrides["filter"] = PRESETS[args.preset]["filter"]
    overrides["headless"] = True
    frames = int(args.max_frames or 120)
    overrides["max_frames"] = frames
    config = Config.load(overrides=overrides)
    app = MirrorLab(config=config, synthetic=True)
    stats = app.run(max_frames=frames)
    if args.json:
        print(json.dumps({"frames": stats.frames, "fps": round(stats.average_fps, 2)}))
    return 0


def _cmd_doctor(args: argparse.Namespace) -> int:
    from .camera import backend_priority, platform_summary
    from .detectors.backends import probe_environment
    from .detectors.models import list_model_status
    from .effects.face import FACE_EFFECTS, HAND_EFFECTS
    from .filters.base import FILTERS

    info: Dict[str, Any] = platform_summary()
    info.update(probe_environment(auto_download=bool(args.download)))
    info["models"] = list_model_status()
    info.setdefault("filters", len(FILTERS))
    info.setdefault("face_effects", len(FACE_EFFECTS))
    info.setdefault("hand_effects", len(HAND_EFFECTS))

    if args.json:
        print(json.dumps(info, indent=2))
        return 0

    print(_banner())
    ok = _colour("✓", "\033[38;5;114m")
    bad = _colour("✗", "\033[38;5;203m")
    warn = _colour("!", _AMBER)

    print(_colour("  Environment", _BOLD))
    for key in ("platform", "platform_release", "machine", "python", "opencv"):
        print(f"    {key:<18} {info.get(key)}")
    print(f"    {'backends':<18} {', '.join(info.get('opencv_backends', [])) or 'none'}")
    print(f"    {'preferred order':<18} {' → '.join(backend_priority('auto'))}")
    print(f"    {'display':<18} {'available' if info.get('display') else 'headless (no window)'}")

    print(_colour("\n  Detectors", _BOLD))
    version = info.get("mediapipe_version")
    print(f"    {'mediapipe':<18} {version or bad + ' not installed'}")
    print(f"    {'tasks API':<18} {ok if info.get('mediapipe_tasks_api') else bad}")
    print(
        f"    {'solutions API':<18} {ok if info.get('mediapipe_solutions_api') else warn + ' unavailable (MediaPipe ≥1.0)'}"
    )
    print(f"    {'opencv YuNet':<18} {ok if info.get('yunet_available') else bad}")
    print(f"    {'face backend':<18} {info.get('face_backend')}")
    print(f"    {'hand backend':<18} {info.get('hand_backend')}")

    if info.get("face_backend") == "none":
        print(_colour("\n  → No face engine could start.", _AMBER))
        print("    Install the tested dependency set:")
        print('      pip install "mediapipe>=0.10.9,<0.11" "numpy<2" "opencv-python<5"')

    print(_colour("\n  Models", _BOLD))
    for row in info["models"]:
        mark = ok if row["cached"] else (warn if row["size_mb"] > 10 else _colour("·", _DIM))
        print(f"    {mark} {row['filename']:<42} {row['size_mb']:>5.1f} MB  {row['key']}")
    missing = [
        row["key"]
        for row in info["models"]
        if not row["cached"] and row["key"] in {"face_landmarker", "hand_landmarker"}
    ]
    if missing:
        print(
            f"\n    Download the essentials with: {_colour('mirrorlab models --download ' + ' '.join(missing), _CYAN)}"
        )

    print(_colour("\n  Capabilities", _BOLD))
    print(f"    filters            {info.get('filters', 0)}")
    print(f"    face effects       {info.get('face_effects', 0)}")
    print(f"    hand effects       {info.get('hand_effects', 0)}")
    return 0


def _cmd_filters(args: argparse.Namespace) -> int:
    from .filters import CATEGORIES, PRESETS, filter_catalog

    if args.presets:
        if args.json:
            print(json.dumps(PRESETS, indent=2, ensure_ascii=False))
            return 0
        print(_colour("\n  Curated presets\n", _BOLD))
        for name, preset in PRESETS.items():
            print(f"    {name:<10} {preset['label_es']:<18} {_colour(preset['filter'], _CYAN)}")
            print(f"               {_colour(preset['description'], _DIM)}")
        print()
        return 0

    catalog = filter_catalog()
    if args.category:
        catalog = [row for row in catalog if row["category"] == args.category]
    if args.json:
        print(json.dumps(catalog, indent=2, ensure_ascii=False))
        return 0

    print(_colour(f"\n  {len(catalog)} filters\n", _BOLD))
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in catalog:
        grouped.setdefault(str(row["category"]), []).append(row)
    for category, rows in grouped.items():
        meta = CATEGORIES.get(category, {"label": category.title(), "emoji": "•"})
        print(_colour(f"  {meta['emoji']} {meta['label']}", _VIOLET))
        for row in rows:
            cost = {"cheap": "·", "medium": "··", "heavy": "···"}.get(str(row["cost"]), "")
            print(f"    {row['name']:<16} {row['emoji']:<3} {row['label_es']!s:<20} {_colour(cost, _DIM)}")
            if row["description_es"]:
                print(f"                     {_colour(str(row['description_es']), _DIM)}")
        print()
    print(_colour("  Chain them:  mirrorlab run --filter cartoon+vignette+glitch\n", _DIM))
    return 0


def _cmd_gestures(args: argparse.Namespace) -> int:
    from .actions import DEFAULT_BINDINGS
    from .gestures import gesture_catalog

    catalog = gesture_catalog()
    if args.json:
        print(json.dumps(catalog, indent=2, ensure_ascii=False))
        return 0

    print(_colour(f"\n  {len(catalog)} hand gestures\n", _BOLD))
    print(f"    {'emoji':<6} {'name':<14} {'español':<16} {'acción':<16} descripción")
    print(_colour("    " + "─" * 92, _DIM))
    for row in catalog:
        if row["name"] == "none":
            continue
        action = DEFAULT_BINDINGS.get(str(row["name"]), "")
        print(
            f"    {row['emoji']:<6} {row['name']:<14} {row['label_es']!s:<16} "
            f"{_colour(action or '—', _CYAN):<25} {_colour(str(row['description']), _DIM)}"
        )
    print(_colour("\n  Hold a pose for ~0.6 s; an on-screen ring shows the confirmation.", _DIM))
    print(_colour("  Swipes, waves and circles are detected from hand motion too.\n", _DIM))
    return 0


def _cmd_expressions(args: argparse.Namespace) -> int:
    from .expressions import expression_catalog

    catalog = expression_catalog()
    if args.json:
        print(json.dumps(catalog, indent=2, ensure_ascii=False))
        return 0

    print(_colour(f"\n  {len(catalog)} facial expressions\n", _BOLD))
    for row in catalog:
        print(
            f"    {row['emoji']:<3} {row['name']:<14} {row['label_es']!s:<18} {_colour(str(row['description']), _DIM)}"
        )
    print()
    print(_colour("  Powered by MediaPipe's 52 ARKit blendshapes", _DIM))
    print(_colour("  (muscle-activation coefficients), not landmark ratios.\n", _DIM))
    return 0


def _cmd_effects(args: argparse.Namespace) -> int:
    from .effects import effect_catalog

    catalog = effect_catalog()
    if args.json:
        print(json.dumps(catalog, indent=2, ensure_ascii=False))
        return 0

    print(_colour(f"\n  {len(catalog)} AR effects\n", _BOLD))
    for kind, title in (
        ("face", "Face effects (anchored to FaceMesh)"),
        ("hand", "Hand effects (anchored to 21 landmarks)"),
    ):
        rows = [row for row in catalog if row["kind"] == kind]
        if not rows:
            continue
        print(_colour(f"  {title}", _VIOLET))
        for row in rows:
            print(
                f"    {row['name']:<16} {row['emoji']:<3} {row['label_es']!s:<20} {_colour(str(row['description_es']), _DIM)}"
            )
        print()
    return 0


def _cmd_models(args: argparse.Namespace) -> int:
    from .detectors.models import MODELS, download_model, list_model_status, models_dir

    status = list_model_status()
    if args.download is not None:
        keys = args.download or list(MODELS)
        failed = []
        for key in keys:
            try:
                path = download_model(
                    key, progress=lambda message: None if args.json else print("  " + message)
                )
                if not args.json:
                    print(f"  ✓ {key:<20} {path}")
            except Exception as exc:
                failed.append(key)
                print(f"  ✗ {key:<20} {exc}", file=sys.stderr)
        if args.json:
            print(json.dumps({"downloaded": [k for k in keys if k not in failed], "failed": failed}))
        return 1 if failed else 0

    if args.json:
        print(json.dumps(status, indent=2))
        return 0

    print(_colour(f"\n  Model cache: {models_dir()}\n", _BOLD))
    for row in status:
        mark = _colour("✓", "\033[38;5;114m") if row["cached"] else _colour("·", _DIM)
        print(f"    {mark} {row['filename']:<44} {row['size_mb']:>5.1f} MB")
        print(f"      {_colour(str(row['purpose']), _DIM)}")
        if row["cached"]:
            print(f"      {_colour(str(row['path']), _DIM)}")
    print(_colour("\n  Download everything:  mirrorlab models --download\n", _DIM))
    return 0


def _cmd_benchmark(args: argparse.Namespace) -> int:
    import numpy as np

    from .filters import FILTERS, FilterContext

    names = args.filters or (
        sorted(FILTERS) if args.all else ["original", "cartoon", "sketch", "thermal", "glitch", "crt"]
    )
    names = [name for name in names if name in FILTERS]
    if not names:
        print("error: no known filters selected", file=sys.stderr)
        return 2

    width, height = max(64, args.width), max(64, args.height)
    frame = (np.random.default_rng(3).random((height, width, 3)) * 255).astype(np.uint8)
    ctx = FilterContext(width=width, height=height, delta=1 / 30.0)
    results = []

    for name in names:
        instance = FILTERS[name]
        # Warm up so the first-call allocations do not pollute the measurement.
        for _ in range(3):
            ctx.frame_index += 1
            instance.apply(frame.copy(), ctx)
        started = time.perf_counter()
        for _ in range(max(1, args.frames)):
            ctx.frame_index += 1
            ctx.time = ctx.frame_index / 30.0
            instance.apply(frame.copy(), ctx)
        elapsed = (time.perf_counter() - started) / max(1, args.frames)
        results.append((name, elapsed * 1000.0, instance.cost))

    results.sort(key=lambda row: -row[1])
    if args.json:
        print(
            json.dumps(
                {
                    "width": width,
                    "height": height,
                    "results": [
                        {
                            "filter": n,
                            "ms": round(ms, 3),
                            "fps": round(1000.0 / ms, 1) if ms else None,
                            "cost": c,
                        }
                        for n, ms, c in results
                    ],
                },
                indent=2,
            )
        )
        return 0

    print(_colour(f"\n  Filter benchmark · {width}×{height} · {args.frames} frames each\n", _BOLD))
    print(f"    {'filter':<18} {'ms/frame':>10} {'fps':>8}  cost")
    print(_colour("    " + "─" * 48, _DIM))
    for name, ms, cost in results:
        fps = 1000.0 / ms if ms > 0 else float("inf")
        flag = "" if ms < 33 else _colour("  ← heavy", _AMBER)
        print(f"    {name:<18} {ms:>10.2f} {fps:>8.1f}  {cost}{flag}")
    median = sorted(row[1] for row in results)[len(results) // 2]
    print(
        _colour(
            f"\n    median {median:.2f} ms → {1000 / median:.0f} fps headroom for the filter stage\n", _DIM
        )
    )
    return 0


def _cmd_config(args: argparse.Namespace) -> int:
    if args.list:
        print(_colour("\n  Supported configuration keys\n", _BOLD))
        for key, value in DEFAULTS.items():
            print(f"    {key:<26} {json.dumps(value)}")
        print(_colour("\n  Override any of them with MIRRORLAB_<KEY> or a mirrorlab.json file.\n", _DIM))
        return 0
    if args.init:
        path = Path(args.init)
        config = Config()
        config.save(path)
        print(f"Wrote {path} with {len(DEFAULTS)} keys.")
        return 0
    try:
        config = Config.load()
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(config.to_json())
    return 0


def _cmd_cameras(args: argparse.Namespace) -> int:
    from .camera import backend_priority, camera_troubleshooting, list_cameras, probe_backends

    found = list_cameras(max_index=max(1, args.max_index))
    if args.json:
        print(json.dumps([info.__dict__ for info in found], indent=2))
        return 0

    print(_colour("\n  Cameras\n", _BOLD))
    if found:
        for info in found:
            print(f"    ✓ {info.describe()}")
    else:
        print(f"    {_colour('none detected', _AMBER)}")
        print()
        print(camera_troubleshooting())
        return 1

    print(_colour("\n  Backends (probed on camera #0)\n", _BOLD))
    for name, works in probe_backends(0):
        mark = _colour("✓", "\033[38;5;114m") if works else _colour("✗", "\033[38;5;203m")
        print(f"    {mark} {name}")
    print(_colour(f"\n  Preferred order: {' → '.join(backend_priority('auto'))}\n", _DIM))
    return 0


def _cmd_gallery(args: argparse.Namespace) -> int:

    from .camera import SyntheticSource
    from .filters import FILTERS, FilterContext
    from .render.composition import tile_grid

    if args.source:
        import cv2

        frame = cv2.imread(args.source)
        if frame is None:
            print(f"error: could not read {args.source}", file=sys.stderr)
            return 2
    else:
        frame = SyntheticSource(480, 270, frame_limit=1).render(0)

    ctx = FilterContext(width=frame.shape[1], height=frame.shape[0], delta=1 / 30.0)
    frames = []
    for name in sorted(FILTERS):
        ctx.frame_index += 1
        ctx.time = ctx.frame_index / 30.0
        out = FILTERS[name].apply(frame.copy(), ctx)
        if out.shape != frame.shape:
            import cv2

            out = cv2.resize(out, (frame.shape[1], frame.shape[0]))
        frames.append(out)

    sheet = tile_grid(frames, columns=args.columns, cell=(frame.shape[1], frame.shape[0]))
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    import cv2

    cv2.imwrite(str(out_path), sheet)
    print(f"Wrote {out_path} ({len(frames)} filters, {sheet.shape[1]}×{sheet.shape[0]})")
    return 0


def _shortcut_table(app: Any) -> str:
    lines = [_colour("\n  Keyboard shortcuts", _BOLD)]
    rows = app.keymap_help()
    for index in range(0, len(rows), 2):
        pair = rows[index : index + 2]
        rendered = "      ".join(f"{key:<5} {text:<38}" for key, text in pair)
        lines.append("    " + rendered)
    lines.append(
        _colour("\n  Gestures: peace = next filter · thumbs up = snapshot · fist = freeze · ok = HUD\n", _DIM)
    )
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entry point. Returns a process exit code."""
    argv = list(sys.argv[1:] if argv is None else argv)

    # `mirrorlab` with no arguments (or only run-flags) means `mirrorlab run`.
    known = {
        "run",
        "doctor",
        "filters",
        "gestures",
        "expressions",
        "effects",
        "models",
        "benchmark",
        "demo",
        "config",
        "cameras",
        "gallery",
    }
    top_level_only = {"-h", "--help", "--version"}
    if argv and argv[0] not in known and not argv[0].startswith("-"):
        print(f"error: unknown command {argv[0]!r}\nRun `mirrorlab --help` for the list.", file=sys.stderr)
        return 2
    if not argv or (argv[0].startswith("-") and argv[0] not in top_level_only):
        argv = ["run", *argv]

    parser = build_parser()
    args = parser.parse_args(argv)

    from .utils.logging import setup_logging

    # `--verbose` wins; otherwise the configured level applies, so a
    # `"log_level": "DEBUG"` in mirrorlab.json actually takes effect.
    if getattr(args, "verbose", False):
        setup_logging("DEBUG")
    else:
        try:
            setup_logging(Config.load().log_level)
        except ValueError:
            setup_logging("INFO")

    handlers = {
        "run": _cmd_run,
        "demo": _cmd_demo,
        "doctor": _cmd_doctor,
        "filters": _cmd_filters,
        "gestures": _cmd_gestures,
        "expressions": _cmd_expressions,
        "effects": _cmd_effects,
        "models": _cmd_models,
        "benchmark": _cmd_benchmark,
        "config": _cmd_config,
        "cameras": _cmd_cameras,
        "gallery": _cmd_gallery,
    }
    handler = handlers.get(args.command or "run")
    if handler is None:  # pragma: no cover - argparse prevents this
        parser.print_help()
        return 2
    try:
        return int(handler(args))
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
