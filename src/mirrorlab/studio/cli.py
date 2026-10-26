"""``mirrorlab cam`` and ``mirrorlab ctl``: the studio on the command line."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List

from ..config import Config
from .settings import BACKGROUND_MODES, PROFILES, StudioSettings

__all__ = ["add_parsers", "cmd_cam", "cmd_ctl", "doctor_lines"]

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_CAMERA = 3
EXIT_OUTPUT = 4


def add_parsers(sub: Any, common: argparse.ArgumentParser) -> None:
    """Register ``cam`` and ``ctl`` on the top-level subparsers."""
    cam = sub.add_parser(
        "cam",
        parents=[common],
        help="publish your camera as a virtual camera with background, framing, light and gestures",
        description=(
            "Reads your camera, applies the studio effects, and publishes the result as a virtual "
            "camera that Zoom, Meet, Teams, Discord, OBS and browsers can select."
        ),
        epilog=(
            "Profiles: " + ", ".join(sorted(PROFILES)) + "\n"
            "Examples:\n"
            "  mirrorlab cam --profile meeting             blur + auto-frame + studio light\n"
            "  mirrorlab cam --background replace --bg-image office.jpg\n"
            "  mirrorlab cam --privacy-on-start            start covered; show a palm to open\n"
            "  mirrorlab cam --output none --preview       try it with no virtual camera installed\n"
            "  mirrorlab cam --check                       is this machine ready?\n"
            "Control a running session from another terminal with `mirrorlab ctl`."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    source = cam.add_argument_group("input")
    source.add_argument("-c", "--camera", type=int, default=None, help="camera index (default: 0)")
    source.add_argument("--input", dest="input_path", help="use a video or image file instead of a camera")
    source.add_argument("--synthetic", action="store_true", help="built-in test pattern (no camera needed)")

    look = cam.add_argument_group("look")
    look.add_argument(
        "--profile", help="named preset: " + ", ".join(sorted(PROFILES)) + " (or one from your settings file)"
    )
    look.add_argument(
        "--settings", metavar="FILE", help="settings file (default: ./studio.json or ~/.config/mirrorlab)"
    )
    look.add_argument("--background", choices=BACKGROUND_MODES, help="background treatment")
    look.add_argument(
        "--bg-image", dest="background_image", metavar="PATH", help="image for --background replace"
    )
    look.add_argument("--blur-strength", type=int, help="blur kernel size, 3-201 (default: 51)")
    look.add_argument(
        "--auto-frame", dest="auto_frame", action="store_true", default=None, help="keep you centred"
    )
    look.add_argument("--no-auto-frame", dest="auto_frame", action="store_false")
    look.add_argument(
        "--studio-light", dest="studio_light", action="store_true", default=None, help="expose for your face"
    )
    look.add_argument("--no-studio-light", dest="studio_light", action="store_false")

    privacy = cam.add_argument_group("privacy and gestures")
    privacy.add_argument(
        "--privacy-on-start",
        dest="privacy_on_start",
        action="store_true",
        default=None,
        help="start with the shutter closed",
    )
    privacy.add_argument(
        "--away-after",
        type=float,
        metavar="SEC",
        help="cover the camera after SEC seconds with nobody in frame",
    )
    privacy.add_argument(
        "--no-gestures",
        dest="gesture_control",
        action="store_false",
        default=None,
        help="disable hand-gesture control",
    )

    out = cam.add_argument_group("output")
    out.add_argument(
        "--output", choices=["vcam", "none"], default="vcam", help="where frames go (default: vcam)"
    )
    out.add_argument("--device", help="virtual camera device (e.g. /dev/video10)")
    out.add_argument("--width", type=int, help="output width (default: 1280)")
    out.add_argument("--height", type=int, help="output height (default: 720)")
    out.add_argument("--fps", type=int, help="output frame rate (default: 30)")
    out.add_argument("--preview", action="store_true", help="also show a local preview window")

    run = cam.add_argument_group("session")
    run.add_argument("--no-control", action="store_true", help="do not open the local control channel")
    run.add_argument("--max-frames", type=int, default=0, help="stop after N frames (0 = run until stopped)")
    run.add_argument("--report", action="store_true", help="print per-stage latency at the end")
    run.add_argument("--check", action="store_true", help="check virtual camera readiness and exit")

    ctl = sub.add_parser(
        "ctl",
        parents=[common],
        help="control a running `mirrorlab cam` session",
        description="Send a command to the session started by `mirrorlab cam`.",
        epilog=(
            "Commands:\n"
            "  status                     show the current state\n"
            "  privacy [on|off]           toggle or set the privacy shutter\n"
            "  background MODE            off | blur | replace | green | black\n"
            "  next-background            cycle the background\n"
            "  framing [on|off]           toggle auto-framing\n"
            "  light [on|off]             toggle studio light\n"
            "  react NAME                 love | thumbs_up | ok | star\n"
            "  snapshot                   save a still of the output\n"
            "  quit                       stop the session\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ctl.add_argument("name", help="command (see below)")
    ctl.add_argument("value", nargs="?", default="", help="optional argument")


# --------------------------------------------------------------------------- #
def _overrides(args: argparse.Namespace) -> Dict[str, Any]:
    keys = [
        "background",
        "background_image",
        "blur_strength",
        "auto_frame",
        "studio_light",
        "privacy_on_start",
        "away_after",
        "gesture_control",
        "width",
        "height",
        "fps",
    ]
    return {key: getattr(args, key, None) for key in keys if getattr(args, key, None) is not None}


def _err(message: str) -> None:
    print(message, file=sys.stderr)


def cmd_cam(args: argparse.Namespace) -> int:
    from ..camera import CameraError
    from .session import StudioSession, describe_report
    from .vcam import OutputError, open_sink, probe

    if args.check:
        status = probe()
        if args.json:
            print(json.dumps(status.to_dict(), indent=2))
        else:
            print("\n".join(doctor_lines(status.to_dict())))
        return EXIT_OK if status.ready else EXIT_ERROR

    try:
        settings = StudioSettings.load(args.settings, profile=args.profile, overrides=_overrides(args))
        config = Config.load(overrides={"camera_index": args.camera, "headless": not args.preview})
    except (ValueError, OSError) as exc:
        _err(f"error: {exc}")
        return EXIT_USAGE

    source: Any = args.input_path if args.input_path else (args.camera if args.camera is not None else 0)
    sink = open_sink("none" if args.output == "none" else "vcam", args.device)
    session = StudioSession(
        settings,
        config,
        source=source,
        sink=sink,
        preview=args.preview,
        control=not args.no_control,
        synthetic=args.synthetic,
    )

    if not args.json:
        print(
            f"MirrorLab Studio  {settings.width}x{settings.height}@{settings.fps}  "
            f"background={settings.background} framing={'on' if settings.auto_frame else 'off'} "
            f"light={'on' if settings.studio_light else 'off'} "
            f"gestures={'on' if settings.gesture_control else 'off'}"
        )
        print("Ctrl-C to stop. Control it from another terminal with `mirrorlab ctl status`.\n")

    try:
        report = session.run(max_frames=args.max_frames)
    except CameraError as exc:
        _err(f"\nCamera error\n{exc}")
        return EXIT_CAMERA
    except OutputError as exc:
        _err(f"\n{exc}\n\nTo try the studio without a virtual camera: mirrorlab cam --output none --preview")
        return EXIT_OUTPUT

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    elif args.report or args.max_frames:
        print("\n".join(describe_report(report)))
    return EXIT_OK


def cmd_ctl(args: argparse.Namespace) -> int:
    from .control import ControlClientError, send_command

    name = args.name.strip().lower().replace("-", "_")
    value = str(args.value or "").strip().lower()

    try:
        if name == "status":
            reply = send_command({"cmd": "status"})
        elif name == "quit":
            reply = send_command({"cmd": "quit"})
        else:
            aliases = {"react": "reaction", "next_background": "background_next"}
            action = aliases.get(name, name)
            reply = send_command({"cmd": "action", "action": f"{action}:{value}" if value else action})
    except ControlClientError as exc:
        _err(f"error: {exc}")
        return EXIT_ERROR

    if args.json:
        print(json.dumps(reply, indent=2))
    elif not reply.get("ok"):
        _err(f"error: {reply.get('error') or reply.get('message') or 'command failed'}")
    elif "status" in reply and name == "status":
        for key, current in reply["status"].items():
            print(f"{key:<12} {current}")
    else:
        print(reply.get("message", "ok"))
    return EXIT_OK if reply.get("ok") else EXIT_ERROR


def doctor_lines(status: Dict[str, Any]) -> List[str]:
    """Lines describing virtual-camera readiness, shared by `doctor` and `cam --check`."""
    lines = [
        f"virtual camera  {'ready' if status['ready'] else 'NOT ready'}  ({status['platform']}, backend: {status['backend'] or 'n/a'})",
        f"  {'ok ' if status['pyvirtualcam'] else '-- '}pyvirtualcam {'installed' if status['pyvirtualcam'] else 'missing'}",
    ]
    lines += [f"      {detail}" for detail in status["details"]]
    if status["fixes"]:
        lines.append("  to fix:")
        lines += [f"    {fix}" for fix in status["fixes"]]
    return lines
