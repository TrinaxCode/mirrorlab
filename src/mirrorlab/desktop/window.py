"""The MirrorLab Studio window: a live preview and the controls around it.

Everything the window does to the camera goes through :class:`StudioRunner`, the
same action vocabulary that gestures and ``mirrorlab ctl`` use, so what a button
does and what a hand gesture does can never drift apart.

The look follows the website: near-black "screens" and one accent, the red of a
camera's tally light.
"""

from __future__ import annotations

import contextlib
import sys
import tkinter as tk
import webbrowser
from functools import partial
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable, Dict, List, Optional, Tuple

import cv2
import numpy as np

from ..studio.settings import StudioSettings
from ..studio.vcam import VCamStatus, probe
from ..version import __version__
from .prefs import DesktopPrefs
from .runner import StudioRunner
from .strings import detect_language, translate

__all__ = ["AUTHOR_URL", "REPO_URL", "WEB_URL", "MirrorLabWindow", "frame_to_ppm"]

REPO_URL = "https://github.com/TrinaxCode/mirrorlab"
AUTHOR_URL = "https://github.com/TrinaxCode"
WEB_URL = "https://mirrorlabapp.web.app"

BG = "#0f1214"
PANEL = "#161a1d"
RAISED = "#1d2226"
LINE = "#2a3036"
INK = "#e8ebe6"
SOFT = "#8e979e"
TALLY = "#ff5b38"
ON_TALLY = "#0f1214"
SIGNAL = "#86efc0"

PREVIEW_INTERVAL_MS = 33
STATUS_INTERVAL_MS = 150
PANEL_WIDTH = 380
BACKGROUNDS = ("off", "blur", "replace", "green", "black")
REACTIONS = ("thumbs_up", "love", "ok", "star")


def frame_to_ppm(frame_bgr: np.ndarray, max_width: int, max_height: int) -> Tuple[bytes, int, int]:
    """Scale a BGR frame to fit the box and return it as binary PPM (Tk reads this natively).

    Going through PPM keeps the window free of Pillow: Tk decodes the format itself.
    """
    height, width = frame_bgr.shape[:2]
    scale = min(max_width / width, max_height / height)
    new_width, new_height = max(2, int(width * scale)), max(2, int(height * scale))
    interpolation = cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR
    resized = cv2.resize(frame_bgr, (new_width, new_height), interpolation=interpolation)
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
    header = f"P6 {new_width} {new_height} 255\n".encode("ascii")
    return header + rgb.tobytes(), new_width, new_height


def _icon_path() -> Optional[Path]:
    path = Path(__file__).resolve().parent / "assets" / "icon.png"
    return path if path.is_file() else None


class MirrorLabWindow:
    """Builds the window and keeps it in step with the running session."""

    def __init__(
        self,
        root: tk.Tk,
        prefs: Optional[DesktopPrefs] = None,
        runner: Optional[StudioRunner] = None,
        vcam_probe: Callable[[], VCamStatus] = probe,
        snapshot_dir: Optional[Path] = None,
        source: "int | str | Path | None" = None,
        synthetic: bool = False,
        ready_file: Optional[Path] = None,
    ) -> None:
        self.root = root
        self._source = source
        self._synthetic = synthetic
        self._ready_file = ready_file
        self.prefs = prefs or DesktopPrefs.load()
        self.runner = runner or StudioRunner()
        self._probe = vcam_probe
        self.snapshot_dir = snapshot_dir or (Path.home() / "Pictures" / "MirrorLab")
        self.lang = self.prefs.language or detect_language()

        self._texts: List[Tuple[Callable[..., object], str, Dict[str, object]]] = []
        self._photo: Optional[tk.PhotoImage] = None
        self._last_sequence = -1
        self._wanted = False  # the user asked for the camera to be on
        self._restart_pending = False
        self._vcam: Optional[VCamStatus] = None
        self._toast_job: Optional[str] = None

        self.bg_var = tk.StringVar(value=self.prefs.background)
        self.frame_var = tk.BooleanVar(value=self.prefs.auto_frame)
        self.light_var = tk.BooleanVar(value=self.prefs.studio_light)
        self.gesture_var = tk.BooleanVar(value=self.prefs.gesture_control)
        self.output_var = tk.StringVar(value=self.prefs.output)
        self.camera_var = tk.StringVar()

        self._configure_root()
        self._build_styles()
        self._build_layout()
        self._apply_language()
        self._refresh_vcam()
        self._bind_keys()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(PREVIEW_INTERVAL_MS, self._tick_preview)
        self.root.after(STATUS_INTERVAL_MS, self._tick_status)

    # ------------------------------------------------------------------ #
    # text helpers
    # ------------------------------------------------------------------ #
    def t(self, key: str, **values: object) -> str:
        return translate(self.lang, key, **values)

    def _bind_text(self, widget: tk.Misc, key: str, **values: object) -> None:
        """Set ``widget``'s text and remember how, so a language switch can redo it."""
        setter: Callable[..., object] = lambda text, w=widget: w.configure(text=text)  # noqa: E731
        self._texts.append((setter, key, values))
        setter(self.t(key, **values))

    def _apply_language(self) -> None:
        for setter, key, values in self._texts:
            setter(self.t(key, **values))
        self.root.title(self.t("app.title"))
        self._configure_camera_choices()
        self._refresh_status()

    # ------------------------------------------------------------------ #
    # construction
    # ------------------------------------------------------------------ #
    def _configure_root(self) -> None:
        self.root.title(self.t("app.title"))
        self.root.configure(background=BG)
        self.root.minsize(940, 600)
        self.root.geometry("1120x680")
        icon = _icon_path()
        if icon is not None:
            try:
                self._icon = tk.PhotoImage(file=str(icon))
                self.root.iconphoto(True, self._icon)
            except tk.TclError:
                pass

    def _build_styles(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        base = ("TkDefaultFont", 10)
        style.configure(".", background=PANEL, foreground=INK, font=base, borderwidth=0, focuscolor=TALLY)
        style.configure("TFrame", background=PANEL)
        style.configure("Screen.TFrame", background=BG)
        style.configure("TLabel", background=PANEL, foreground=INK)
        style.configure("Soft.TLabel", foreground=SOFT)
        style.configure("Section.TLabel", foreground=SOFT, font=("TkDefaultFont", 8, "bold"))
        style.configure("Title.TLabel", font=("TkDefaultFont", 17, "bold"))
        style.configure("Screen.TLabel", background=BG, foreground=INK)
        style.configure("ScreenSoft.TLabel", background=BG, foreground=SOFT)
        style.configure("Link.TLabel", foreground=SOFT, font=("TkDefaultFont", 9, "underline"))

        style.configure(
            "Primary.TButton",
            background=TALLY,
            foreground=ON_TALLY,
            font=("TkDefaultFont", 11, "bold"),
            padding=(14, 11),
            relief="flat",
        )
        style.map(
            "Primary.TButton",
            background=[("disabled", LINE), ("active", "#ff7455")],
            foreground=[("disabled", SOFT)],
        )
        style.configure(
            "Stop.TButton",
            background=RAISED,
            foreground=INK,
            font=("TkDefaultFont", 11, "bold"),
            padding=(14, 11),
        )
        style.map("Stop.TButton", background=[("active", LINE)])
        style.configure("Quiet.TButton", background=RAISED, foreground=INK, padding=(10, 7), relief="flat")
        style.map(
            "Quiet.TButton",
            background=[("disabled", RAISED), ("active", LINE)],
            foreground=[("disabled", "#5d666d")],
        )

        style.configure(
            "Seg.Toolbutton",
            background=RAISED,
            foreground=INK,
            padding=(8, 7),
            anchor="center",
            relief="flat",
        )
        style.map(
            "Seg.Toolbutton",
            background=[("selected", TALLY), ("disabled", RAISED), ("active", LINE)],
            foreground=[("selected", ON_TALLY), ("disabled", "#5d666d")],
        )
        style.configure(
            "TCombobox",
            fieldbackground=RAISED,
            background=RAISED,
            foreground=INK,
            arrowcolor=INK,
            bordercolor=LINE,
            lightcolor=RAISED,
            darkcolor=RAISED,
            padding=6,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", RAISED)],
            foreground=[("readonly", INK)],
            bordercolor=[("focus", TALLY)],
        )
        self.root.option_add("*TCombobox*Listbox.background", RAISED)
        self.root.option_add("*TCombobox*Listbox.foreground", INK)
        self.root.option_add("*TCombobox*Listbox.selectBackground", TALLY)
        self.root.option_add("*TCombobox*Listbox.selectForeground", ON_TALLY)

    def _build_layout(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.columnconfigure(1, weight=0)
        self.root.rowconfigure(0, weight=1)

        # -- left: the picture ------------------------------------------- #
        stage = ttk.Frame(self.root, style="Screen.TFrame", padding=(18, 18, 12, 14))
        stage.grid(row=0, column=0, sticky="nsew")
        stage.columnconfigure(0, weight=1)
        stage.rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(stage, background="#000000", highlightthickness=0, bd=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.bind("<Configure>", lambda _event: self._draw_idle())

        bar = ttk.Frame(stage, style="Screen.TFrame", padding=(2, 12, 2, 0))
        bar.grid(row=1, column=0, sticky="ew")
        bar.columnconfigure(1, weight=1)
        self.dot = tk.Canvas(bar, width=12, height=12, background=BG, highlightthickness=0)
        self.dot.grid(row=0, column=0, padx=(0, 8))
        self.dot_item = self.dot.create_oval(1, 1, 11, 11, fill=SOFT, outline="")
        self.state_label = ttk.Label(bar, style="Screen.TLabel", font=("TkDefaultFont", 10, "bold"))
        self.state_label.grid(row=0, column=1, sticky="w")
        self.fps_label = ttk.Label(bar, style="ScreenSoft.TLabel")
        self.fps_label.grid(row=0, column=2, sticky="e")
        self.toast = ttk.Label(stage, style="ScreenSoft.TLabel", anchor="w")
        self.toast.grid(row=2, column=0, sticky="ew", pady=(6, 0))

        # -- right: the controls ----------------------------------------- #
        panel = ttk.Frame(self.root, padding=(22, 20, 22, 14), width=PANEL_WIDTH)
        panel.grid(row=0, column=1, sticky="ns")
        panel.grid_propagate(False)
        panel.columnconfigure(0, weight=1)

        head = ttk.Frame(panel)
        head.grid(row=0, column=0, sticky="ew")
        head.columnconfigure(1, weight=1)
        self.logo = tk.Canvas(head, width=34, height=34, background=PANEL, highlightthickness=0)
        self.logo.grid(row=0, column=0, rowspan=2, padx=(0, 10))
        self._draw_logo()
        ttk.Label(head, text="MirrorLab", style="Title.TLabel").grid(row=0, column=1, sticky="w")
        self.tagline = ttk.Label(head, style="Soft.TLabel", wraplength=PANEL_WIDTH - 90)
        self.tagline.grid(row=1, column=1, sticky="w")
        self._bind_text(self.tagline, "app.tagline")

        self.power = ttk.Button(panel, style="Primary.TButton", command=self.toggle_camera)
        self.power.grid(row=1, column=0, sticky="ew", pady=(14, 12))

        row = 2
        row = self._section(panel, row, "section.camera")
        self.camera_box = ttk.Combobox(panel, textvariable=self.camera_var, state="readonly")
        self.camera_box.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        self.camera_box.bind("<<ComboboxSelected>>", self._on_camera_change)
        row += 1

        row = self._section(panel, row, "section.background")
        modes = ttk.Frame(panel)
        modes.grid(row=row, column=0, sticky="ew")
        self.bg_buttons: Dict[str, ttk.Radiobutton] = {}
        for column, mode in enumerate(BACKGROUNDS):
            modes.columnconfigure(column, weight=1, uniform="bg")
            button = ttk.Radiobutton(
                modes,
                style="Seg.Toolbutton",
                variable=self.bg_var,
                value=mode,
                command=self._on_background_change,
            )
            button.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 2, 0))
            self._bind_text(button, f"bg.{mode}")
            self.bg_buttons[mode] = button
        row += 1
        self.image_label = ttk.Label(panel, style="Soft.TLabel", cursor="hand2")
        self.image_label.grid(row=row, column=0, sticky="w", pady=(4, 0))
        self.image_label.bind("<Button-1>", lambda _event: self.pick_image())
        row += 1

        row = self._section(panel, row, "section.enhance", pad=10)
        toggles = ttk.Frame(panel)
        toggles.grid(row=row, column=0, sticky="ew")
        for column, (variable, key, handler) in enumerate(
            (
                (self.frame_var, "enhance.frame", self._on_frame_change),
                (self.light_var, "enhance.light", self._on_light_change),
                (self.gesture_var, "enhance.gestures", self._on_gesture_change),
            )
        ):
            toggles.columnconfigure(column, weight=1, uniform="toggle")
            check = ttk.Checkbutton(toggles, style="Seg.Toolbutton", variable=variable, command=handler)
            check.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 2, 0))
            self._bind_text(check, key)
        row += 1

        row = self._section(panel, row, "section.privacy", pad=10)
        actions = ttk.Frame(panel)
        actions.grid(row=row, column=0, sticky="ew")
        actions.columnconfigure(0, weight=3, uniform="act")
        actions.columnconfigure(1, weight=2, uniform="act")
        self.privacy_button = ttk.Button(actions, style="Quiet.TButton", command=self.toggle_privacy)
        self.privacy_button.grid(row=0, column=0, sticky="ew")
        self.snapshot_button = ttk.Button(actions, style="Quiet.TButton", command=self.snapshot)
        self.snapshot_button.grid(row=0, column=1, sticky="ew", padx=(4, 0))
        self._bind_text(self.snapshot_button, "snapshot")
        row += 1
        hint = ttk.Label(panel, style="Soft.TLabel", font=("TkDefaultFont", 8))
        hint.grid(row=row, column=0, sticky="w", pady=(4, 0))
        self._bind_text(hint, "privacy.hint")
        row += 1

        row = self._section(panel, row, "section.reactions", pad=10)
        reactions = ttk.Frame(panel)
        reactions.grid(row=row, column=0, sticky="ew")
        self.reaction_buttons: List[ttk.Button] = []
        for column, name in enumerate(REACTIONS):
            reactions.columnconfigure(column, weight=1, uniform="react")
            reaction = ttk.Button(reactions, style="Quiet.TButton", command=partial(self.react, name))
            reaction.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 2, 0))
            self._bind_text(reaction, f"react.{name}")
            self.reaction_buttons.append(reaction)
        row += 1

        row = self._section(panel, row, "section.output", pad=10)
        outputs = ttk.Frame(panel)
        outputs.grid(row=row, column=0, sticky="ew")
        for column, (value, key) in enumerate((("vcam", "output.vcam"), ("none", "output.none"))):
            outputs.columnconfigure(column, weight=1, uniform="out")
            radio = ttk.Radiobutton(
                outputs,
                style="Seg.Toolbutton",
                variable=self.output_var,
                value=value,
                command=self._on_output_change,
            )
            radio.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 2, 0))
            self._bind_text(radio, key)
        row += 1
        status = ttk.Frame(panel)
        status.grid(row=row, column=0, sticky="ew", pady=(5, 0))
        status.columnconfigure(0, weight=1)
        self.vcam_label = ttk.Label(status, style="Soft.TLabel")
        self.vcam_label.grid(row=0, column=0, sticky="w")
        self.vcam_fix = ttk.Label(status, style="Link.TLabel", cursor="hand2")
        self.vcam_fix.grid(row=0, column=1, sticky="e")
        self.vcam_fix.bind("<Button-1>", lambda _event: self.show_vcam_help())
        self._bind_text(self.vcam_fix, "vcam.fix")
        row += 1

        panel.rowconfigure(row, weight=1)
        row += 1
        foot = ttk.Frame(panel)
        foot.grid(row=row, column=0, sticky="ew", pady=(10, 0))
        foot.columnconfigure(0, weight=1)
        created = ttk.Label(foot, style="Link.TLabel", cursor="hand2")
        created.grid(row=0, column=0, sticky="w")
        created.bind("<Button-1>", lambda _event: webbrowser.open(AUTHOR_URL))
        self._bind_text(created, "footer.created")
        about = ttk.Label(foot, style="Link.TLabel", cursor="hand2")
        about.grid(row=0, column=1, sticky="e", padx=(0, 10))
        about.bind("<Button-1>", lambda _event: self.show_about())
        self._bind_text(about, "about")
        self.lang_button = ttk.Label(foot, style="Link.TLabel", cursor="hand2")
        self.lang_button.grid(row=0, column=2, sticky="e")
        self.lang_button.bind("<Button-1>", lambda _event: self.toggle_language())
        shortcuts = ttk.Label(foot, style="Soft.TLabel", font=("TkDefaultFont", 8))
        shortcuts.grid(row=1, column=0, columnspan=3, sticky="w", pady=(4, 0))
        self._bind_text(shortcuts, "shortcuts")

    def _section(self, panel: ttk.Frame, row: int, key: str, pad: int = 0) -> int:
        label = ttk.Label(panel, style="Section.TLabel")
        label.grid(row=row, column=0, sticky="w", pady=(pad, 5))
        self._texts.append((lambda text, w=label: w.configure(text=text.upper()), key, {}))
        label.configure(text=self.t(key).upper())
        return row + 1

    def _draw_logo(self) -> None:
        self.logo.create_rectangle(1, 1, 33, 33, fill=BG, outline="")
        self.logo.create_oval(7, 7, 27, 27, outline=INK, width=2)
        self.logo.create_oval(14, 14, 20, 20, fill=INK, outline="")
        self.logo.create_oval(24, 3, 31, 10, fill=TALLY, outline="")

    def _bind_keys(self) -> None:
        def fire(callback: Callable[[], None]) -> Callable[[tk.Event], Optional[str]]:
            def handler(event: tk.Event) -> Optional[str]:
                if isinstance(event.widget, (ttk.Combobox, tk.Entry, ttk.Entry)):
                    return None
                callback()
                return "break"

            return handler

        self.root.bind("<KeyPress-p>", fire(self.toggle_privacy))
        self.root.bind("<KeyPress-b>", fire(self.next_background))
        self.root.bind("<KeyPress-s>", fire(self.snapshot))
        self.root.bind("<Control-q>", lambda _event: self.close())

    # ------------------------------------------------------------------ #
    # camera choices and vcam status
    # ------------------------------------------------------------------ #
    def _configure_camera_choices(self) -> None:
        labels = [self.t("camera.n", n=index) for index in range(6)]
        self.camera_box.configure(values=labels)
        self.camera_var.set(labels[min(self.prefs.camera, len(labels) - 1)])
        self.lang_button.configure(text="EN" if self.lang == "es" else "ES")

    def _refresh_vcam(self) -> None:
        try:
            self._vcam = self._probe()
        except Exception:  # probing must never keep the window from opening
            self._vcam = None
        self._update_vcam_label()

    def _update_vcam_label(self) -> None:
        status = self._vcam
        wanted = self.output_var.get() == "vcam"
        if status is None or not wanted:
            self.vcam_label.configure(text="")
            self.vcam_fix.grid_remove()
            return
        if status.ready:
            self.vcam_label.configure(text="✓ " + self.t("vcam.ready"), foreground=SIGNAL)
            self.vcam_fix.grid_remove()
        else:
            self.vcam_label.configure(text="⚠ " + self.t("vcam.missing"), foreground=TALLY)
            self.vcam_fix.grid()

    def show_vcam_help(self) -> None:
        status = self._vcam
        dialog = tk.Toplevel(self.root)
        dialog.title(self.t("vcam.fix.title"))
        dialog.configure(background=PANEL)
        dialog.transient(self.root)
        dialog.resizable(False, False)
        body = ttk.Frame(dialog, padding=20)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text=self.t("vcam.fix.intro"), wraplength=460).pack(anchor="w")
        fixes = list(status.fixes) if status is not None else []
        details = list(status.details) if status is not None else []
        if not fixes:
            ttk.Label(body, text=self.t("vcam.fix.none"), style="Soft.TLabel").pack(anchor="w", pady=(12, 0))
        for line in details:
            ttk.Label(body, text=line, style="Soft.TLabel", wraplength=460).pack(anchor="w", pady=(8, 0))
        for fix in fixes:
            row = ttk.Frame(body)
            row.pack(fill="x", pady=(10, 0))
            entry = tk.Entry(
                row,
                background=RAISED,
                foreground=INK,
                relief="flat",
                readonlybackground=RAISED,
                insertbackground=INK,
                highlightthickness=1,
                highlightbackground=LINE,
                width=58,
            )
            entry.insert(0, fix)
            entry.configure(state="readonly")
            entry.pack(side="left", fill="x", expand=True, ipady=5)
            ttk.Button(
                row,
                text=self.t("vcam.fix.copy"),
                style="Quiet.TButton",
                command=partial(self._copy, fix),
            ).pack(side="left", padx=(8, 0))
        ttk.Button(body, text=self.t("vcam.fix.close"), style="Quiet.TButton", command=dialog.destroy).pack(
            anchor="e", pady=(18, 0)
        )

    def _copy(self, text: str) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(text)

    def show_about(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title(self.t("about"))
        dialog.configure(background=PANEL)
        dialog.transient(self.root)
        dialog.resizable(False, False)
        body = ttk.Frame(dialog, padding=24)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text=f"MirrorLab {__version__}", style="Title.TLabel").pack(anchor="w")
        ttk.Label(body, text=self.t("about.body"), wraplength=400, justify="left").pack(
            anchor="w", pady=(10, 0)
        )
        ttk.Label(body, text=self.t("about.created"), font=("TkDefaultFont", 10, "bold")).pack(
            anchor="w", pady=(14, 0)
        )
        ttk.Label(body, text=self.t("about.license"), style="Soft.TLabel").pack(anchor="w")
        links = ttk.Frame(body)
        links.pack(anchor="w", pady=(14, 0))
        for key, url in (("about.repo", REPO_URL), ("about.web", WEB_URL)):
            ttk.Button(
                links, text=self.t(key), style="Quiet.TButton", command=partial(webbrowser.open, url)
            ).pack(side="left", padx=(0, 8))
        ttk.Button(body, text=self.t("vcam.fix.close"), style="Quiet.TButton", command=dialog.destroy).pack(
            anchor="e", pady=(18, 0)
        )

    # ------------------------------------------------------------------ #
    # actions
    # ------------------------------------------------------------------ #
    def build_settings(self) -> StudioSettings:
        mapping: Dict[str, object] = {
            "background": self.bg_var.get(),
            "auto_frame": bool(self.frame_var.get()),
            "studio_light": bool(self.light_var.get()),
            "gesture_control": bool(self.gesture_var.get()),
            "away_text": self.t("privacy.away"),
        }
        if self.prefs.background_image:
            mapping["background_image"] = self.prefs.background_image
        return StudioSettings.from_mapping(mapping)

    def toggle_camera(self) -> None:
        if self._wanted or self.runner.running:
            self.stop_camera()
        else:
            self.start_camera()

    def start_camera(self) -> None:
        if self.runner.running:
            return
        self._save_prefs()
        try:
            settings = self.build_settings()
        except ValueError as exc:
            messagebox.showerror(self.t("error.title"), str(exc), parent=self.root)
            return
        self._wanted = True
        self._last_sequence = -1
        self._photo = None
        self.runner.start(
            settings,
            camera=self.prefs.camera,
            output=self.output_var.get(),
            snapshot_dir=self.snapshot_dir,
            source=self._source,
            synthetic=self._synthetic,
        )
        self._draw_idle()
        self._refresh_status()

    def stop_camera(self) -> None:
        self._wanted = False
        self._restart_pending = False
        self.runner.request_stop()
        self._refresh_status()

    def restart_if_running(self) -> None:
        """Settings the running session cannot change take effect on a fresh one."""
        if self._wanted:
            self.runner.request_stop()
            self._restart_pending = True

    def toggle_privacy(self) -> None:
        self.runner.apply("privacy")

    def next_background(self) -> None:
        if self.runner.running:
            self.runner.apply("background_next")
            current = str(self.runner.state().get("background", self.bg_var.get()))
            self.bg_var.set(current)
        else:
            usable = [m for m in BACKGROUNDS if m != "replace" or self.prefs.background_image]
            index = usable.index(self.bg_var.get()) if self.bg_var.get() in usable else -1
            self.bg_var.set(usable[(index + 1) % len(usable)])
            self._on_background_change()

    def react(self, name: str) -> None:
        self.runner.apply(f"reaction:{name}")

    def snapshot(self) -> None:
        if self.runner.apply("snapshot").ok:
            self.show_toast(self.t("snapshot.saved", path=self.snapshot_dir))

    def pick_image(self) -> None:
        path = filedialog.askopenfilename(
            parent=self.root,
            title=self.t("bg.pick"),
            filetypes=[(self.t("bg.filetypes"), "*.jpg *.jpeg *.png *.webp *.bmp")],
        )
        if not path:
            return
        self.prefs.background_image = path
        self.bg_var.set("replace")
        self._on_background_change()
        self.restart_if_running()

    def toggle_language(self) -> None:
        self.lang = "en" if self.lang == "es" else "es"
        self.prefs.language = self.lang
        self._apply_language()
        self._update_vcam_label()
        self._save_prefs()

    def show_toast(self, message: str, seconds: float = 4.0) -> None:
        self.toast.configure(text=message)
        if self._toast_job is not None:
            self.root.after_cancel(self._toast_job)
        self._toast_job = self.root.after(int(seconds * 1000), lambda: self.toast.configure(text=""))

    # -- widget callbacks ------------------------------------------------ #
    def _on_background_change(self) -> None:
        mode = self.bg_var.get()
        if mode == "replace" and not self.prefs.background_image:
            self.bg_var.set(self.prefs.background if self.prefs.background != "replace" else "blur")
            self.pick_image()
            return
        self.prefs.background = mode
        self._update_image_label()
        if self.runner.running:
            self.runner.apply(f"background:{mode}")
        self._save_prefs()

    def _update_image_label(self) -> None:
        image = self.prefs.background_image
        if self.bg_var.get() == "replace" and image:
            self.image_label.configure(text=self.t("bg.picked", name=Path(image).name))
        elif self.bg_var.get() == "replace":
            self.image_label.configure(text=self.t("bg.pick"))
        else:
            self.image_label.configure(text="")

    def _on_frame_change(self) -> None:
        self.prefs.auto_frame = bool(self.frame_var.get())
        self.runner.apply("framing:on" if self.prefs.auto_frame else "framing:off")
        self._save_prefs()

    def _on_light_change(self) -> None:
        self.prefs.studio_light = bool(self.light_var.get())
        self.runner.apply("light:on" if self.prefs.studio_light else "light:off")
        self._save_prefs()

    def _on_gesture_change(self) -> None:
        self.prefs.gesture_control = bool(self.gesture_var.get())
        self._save_prefs()
        self.restart_if_running()

    def _on_output_change(self) -> None:
        self.prefs.output = self.output_var.get()
        self._update_vcam_label()
        self._save_prefs()
        self.restart_if_running()

    def _on_camera_change(self, _event: object = None) -> None:
        labels = list(self.camera_box.cget("values"))
        try:
            self.prefs.camera = labels.index(self.camera_var.get())
        except ValueError:
            return
        self._save_prefs()
        self.restart_if_running()

    def _save_prefs(self) -> None:
        self.prefs.background = self.bg_var.get()
        self.prefs.output = self.output_var.get()
        self.prefs.save()

    # ------------------------------------------------------------------ #
    # drawing and timers
    # ------------------------------------------------------------------ #
    def _canvas_size(self) -> Tuple[int, int]:
        return max(2, self.canvas.winfo_width()), max(2, self.canvas.winfo_height())

    def _draw_idle(self) -> None:
        if self.runner.has_frame and self.runner.running:
            return
        width, height = self._canvas_size()
        self.canvas.delete("all")
        self._photo = None
        if self._wanted:
            title, body = self.t("starting"), self.t("starting.models")
        else:
            title, body = self.t("idle.title"), self.t("idle.body")
        self.canvas.create_text(
            width / 2,
            height / 2 - 16,
            text=title,
            fill=INK,
            font=("TkDefaultFont", 20, "bold"),
            width=max(80, width - 40),
            justify="center",
        )
        self.canvas.create_text(
            width / 2,
            height / 2 + 22,
            text=body,
            fill=SOFT,
            font=("TkDefaultFont", 11),
            width=min(520, width - 60),
            justify="center",
        )

    def _tick_preview(self) -> None:
        try:
            sequence, frame = self.runner.latest_frame()
            if frame is not None and self.runner.running and sequence != self._last_sequence:
                self._last_sequence = sequence
                width, height = self._canvas_size()
                ppm, _, _ = frame_to_ppm(frame, width, height)
                self._photo = tk.PhotoImage(data=ppm, format="PPM")
                self.canvas.delete("all")
                self.canvas.create_image(width // 2, height // 2, image=self._photo)
                self._signal_ready()
        finally:
            self.root.after(PREVIEW_INTERVAL_MS, self._tick_preview)

    def _signal_ready(self) -> None:
        """Write the ``--ready-file`` once the first frame is on screen (used by the release smoke test)."""
        if self._ready_file is None:
            return
        with contextlib.suppress(OSError):
            self._ready_file.write_text("ok", encoding="utf-8")
        self._ready_file = None

    def _tick_status(self) -> None:
        try:
            self._follow_session()
            self._refresh_status()
        finally:
            self.root.after(STATUS_INTERVAL_MS, self._tick_status)

    def _follow_session(self) -> None:
        """Notice that a session ended: report why, or start the requested restart."""
        if self.runner.running:
            return
        if self._restart_pending:
            self._restart_pending = False
            self.start_camera()
            return
        if self._wanted:
            self._wanted = False
            message = self.runner.error
            if message:
                hint = self.t("error.output") if self.runner.error_kind == "output" else ""
                messagebox.showerror(self.t("error.title"), f"{message}\n\n{hint}".strip(), parent=self.root)
            self._draw_idle()
        elif self._photo is not None:
            self._draw_idle()  # the session ended: replace the last picture with the idle card

    def _refresh_status(self) -> None:
        running = self.runner.running
        covered = bool(self.runner.state().get("privacy")) if running else False
        live = running and self.runner.has_frame

        if running and not self._wanted:
            self.power.configure(text=self.t("stopping"), style="Stop.TButton", state="disabled")
        elif running or self._wanted:
            starting = not live
            self.power.configure(
                text=self.t("starting") if starting else self.t("stop"), style="Stop.TButton", state="normal"
            )
        else:
            self.power.configure(text=self.t("start"), style="Primary.TButton", state="normal")

        if not running:
            state, colour = ("state.starting" if self._wanted else "state.off"), SOFT
        elif not live:
            state, colour = "state.starting", SOFT
        elif covered:
            state, colour = "state.covered", SOFT
        else:
            state, colour = "state.live", TALLY
        self.state_label.configure(text=self.t(state))
        self.dot.itemconfigure(self.dot_item, fill=colour)

        status = self.runner.status()
        fps = float(status.get("fps", 0.0)) if status else 0.0
        resolution = str(status.get("resolution", "")) if status else ""
        self.fps_label.configure(text=f"{resolution}   {self.t('fps', fps=fps)}" if live else "")

        self.privacy_button.configure(text=self.t("privacy.open" if covered else "privacy.close"))
        controls = "normal" if live else "disabled"
        for button in (self.privacy_button, self.snapshot_button, *self.reaction_buttons):
            button.configure(state=controls)
        self._update_image_label()
        self.bg_buttons["replace"].configure(state="normal")

    # ------------------------------------------------------------------ #
    def close(self) -> None:
        self._save_prefs()
        self._wanted = False
        self.runner.stop(timeout=4.0)
        self.root.destroy()


def main(argv: Optional[List[str]] = None) -> int:
    """Open the window. Returns a process exit code."""
    import argparse

    parser = argparse.ArgumentParser(prog="mirrorlab-studio", description="The MirrorLab Studio window.")
    parser.add_argument("--source", help="use a video or image file instead of a camera (for demos)")
    parser.add_argument("--synthetic", action="store_true", help="use the built-in test pattern")
    parser.add_argument("--output", choices=("vcam", "none"), help="start with this output selected")
    parser.add_argument("--geometry", metavar="WxH", help="open the window at this size (for screenshots)")
    parser.add_argument(
        "--autostart", action="store_true", help="turn the camera on as soon as the window opens"
    )
    parser.add_argument("--ready-file", metavar="PATH", help="write this file when the first frame is shown")
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    if sys.stdout is None:  # a windowed PyInstaller build has no console streams
        sys.stdout = open("/dev/null" if sys.platform != "win32" else "NUL", "w")  # noqa: SIM115
    if sys.stderr is None:
        sys.stderr = sys.stdout
    root = tk.Tk()
    prefs = DesktopPrefs.load()
    if args.output:
        prefs.output = args.output
    window = MirrorLabWindow(
        root,
        prefs=prefs,
        source=args.source,
        synthetic=args.synthetic,
        ready_file=Path(args.ready_file) if args.ready_file else None,
    )
    if args.geometry:
        root.geometry(args.geometry)
    if args.autostart:
        root.after(300, window.start_camera)
    root.mainloop()
    return 0
