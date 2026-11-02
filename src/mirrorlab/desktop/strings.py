"""Interface text for the desktop app, in Spanish and English.

A plain dictionary rather than gettext: two languages, a few dozen strings, and a
test that fails when one language misses a key the other has.
"""

from __future__ import annotations

import ctypes
import locale
import os
import sys
from typing import Dict

__all__ = ["LANGUAGES", "STRINGS", "detect_language", "translate"]

LANGUAGES = ("es", "en")

STRINGS: Dict[str, Dict[str, str]] = {
    "es": {
        "app.title": "MirrorLab Studio",
        "app.tagline": "Cámara virtual con control por gestos",
        "start": "Encender cámara",
        "stop": "Apagar cámara",
        "starting": "Iniciando…",
        "stopping": "Apagando…",
        "section.camera": "Cámara",
        "section.background": "Fondo",
        "section.enhance": "Mejoras",
        "section.privacy": "Privacidad",
        "section.reactions": "Reacciones",
        "section.output": "Salida",
        "camera.n": "Cámara {n}",
        "bg.off": "Ninguno",
        "bg.blur": "Blur",
        "bg.replace": "Imagen",
        "bg.green": "Verde",
        "bg.black": "Negro",
        "bg.pick": "Elegir imagen…",
        "bg.picked": "Imagen: {name}",
        "bg.filetypes": "Imágenes",
        "enhance.frame": "Encuadre",
        "enhance.light": "Luz",
        "enhance.gestures": "Gestos",
        "privacy.close": "Tapar cámara",
        "privacy.open": "Destapar cámara",
        "privacy.hint": "También: palma abierta 1,6 s",
        "privacy.away": "Vuelvo enseguida",
        "react.thumbs_up": "Pulgar",
        "react.love": "Corazón",
        "react.ok": "OK",
        "react.star": "Estrella",
        "snapshot": "Captura",
        "snapshot.saved": "Captura guardada en {path}",
        "output.vcam": "Cámara virtual",
        "output.none": "Solo vista previa",
        "vcam.ready": "Cámara virtual lista",
        "vcam.missing": "Falta la cámara virtual",
        "vcam.fix": "Cómo arreglarlo",
        "vcam.fix.title": "Instalar la cámara virtual",
        "vcam.fix.intro": "Para que Zoom, Meet o Teams vean MirrorLab hace falta un dispositivo de cámara virtual en tu sistema.",
        "vcam.fix.none": "Todo listo: no falta nada.",
        "vcam.fix.copy": "Copiar",
        "vcam.fix.close": "Cerrar",
        "state.off": "APAGADA",
        "state.live": "EN VIVO",
        "state.covered": "TAPADA",
        "state.starting": "INICIANDO",
        "idle.title": "La cámara está apagada",
        "idle.body": "Pulsa «Encender cámara». Todo se procesa en tu equipo y nada se sube a internet.",
        "starting.models": "Preparando los modelos de visión. La primera vez se descargan unos 12 MB.",
        "error.title": "No se pudo encender la cámara",
        "error.output": "Puedes seguir con «Solo vista previa» para probar MirrorLab sin cámara virtual.",
        "error.tk": "Esta instalación de Python no incluye Tk. En Debian y Ubuntu: sudo apt install python3-tk",
        "about": "Acerca de",
        "about.body": "Cámara virtual para videollamadas: desenfoque de fondo, encuadre automático, luz de estudio y control por gestos. Funciona en tu equipo y no envía vídeo a ningún sitio.",
        "about.created": "Creado por TrinaxCode",
        "about.license": "Código bajo licencia MIT.",
        "about.repo": "Repositorio en GitHub",
        "about.web": "Sitio web",
        "language": "Idioma",
        "footer.created": "Creado por TrinaxCode",
        "fps": "{fps:.0f} fps",
        "shortcuts": "P tapar · B fondo · S captura",
    },
    "en": {
        "app.title": "MirrorLab Studio",
        "app.tagline": "A virtual camera you control with your hands",
        "start": "Turn camera on",
        "stop": "Turn camera off",
        "starting": "Starting…",
        "stopping": "Stopping…",
        "section.camera": "Camera",
        "section.background": "Background",
        "section.enhance": "Enhancements",
        "section.privacy": "Privacy",
        "section.reactions": "Reactions",
        "section.output": "Output",
        "camera.n": "Camera {n}",
        "bg.off": "None",
        "bg.blur": "Blur",
        "bg.replace": "Image",
        "bg.green": "Green",
        "bg.black": "Black",
        "bg.pick": "Choose image…",
        "bg.picked": "Image: {name}",
        "bg.filetypes": "Images",
        "enhance.frame": "Framing",
        "enhance.light": "Light",
        "enhance.gestures": "Gestures",
        "privacy.close": "Cover camera",
        "privacy.open": "Uncover camera",
        "privacy.hint": "Or hold an open palm for 1.6 s",
        "privacy.away": "Be right back",
        "react.thumbs_up": "Like",
        "react.love": "Heart",
        "react.ok": "OK",
        "react.star": "Star",
        "snapshot": "Snapshot",
        "snapshot.saved": "Snapshot saved to {path}",
        "output.vcam": "Virtual camera",
        "output.none": "Preview only",
        "vcam.ready": "Virtual camera ready",
        "vcam.missing": "Virtual camera missing",
        "vcam.fix": "How to fix it",
        "vcam.fix.title": "Install the virtual camera",
        "vcam.fix.intro": "Zoom, Meet and Teams need a virtual camera device on your system to see MirrorLab.",
        "vcam.fix.none": "All set: nothing is missing.",
        "vcam.fix.copy": "Copy",
        "vcam.fix.close": "Close",
        "state.off": "OFF",
        "state.live": "LIVE",
        "state.covered": "COVERED",
        "state.starting": "STARTING",
        "idle.title": "The camera is off",
        "idle.body": "Press “Turn camera on”. Everything is processed on your machine and nothing is uploaded.",
        "starting.models": "Preparing the vision models. The first run downloads about 12 MB.",
        "error.title": "The camera could not be started",
        "error.output": "You can still use “Preview only” to try MirrorLab without a virtual camera.",
        "error.tk": "This Python installation has no Tk. On Debian and Ubuntu: sudo apt install python3-tk",
        "about": "About",
        "about.body": "A virtual camera for video calls: background blur, auto-framing, studio light and hand-gesture control. It runs on your machine and sends no video anywhere.",
        "about.created": "Created by TrinaxCode",
        "about.license": "Source code under the MIT licence.",
        "about.repo": "GitHub repository",
        "about.web": "Website",
        "language": "Language",
        "footer.created": "Created by TrinaxCode",
        "fps": "{fps:.0f} fps",
        "shortcuts": "P cover · B background · S snapshot",
    },
}


def translate(language: str, key: str, **values: object) -> str:
    """Look ``key`` up in ``language``, falling back to English and then to the key itself."""
    table = STRINGS.get(language) or STRINGS["en"]
    text = table.get(key) or STRINGS["en"].get(key) or key
    return text.format(**values) if values else text


def _windows_ui_language() -> str:
    """Primary language of the Windows UI, or ``""`` when it cannot be read."""
    try:
        lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        return ""
    return "es" if (lang_id & 0x3FF) == 0x0A else "en"


def detect_language() -> str:
    """Spanish when the system says so, English otherwise.

    GUI launches (a macOS app, a Windows shortcut) do not inherit a shell's ``LANG``,
    so the environment is only one of the places to look.
    """
    for name in ("LC_ALL", "LC_MESSAGES", "LANGUAGE", "LANG"):
        value = os.environ.get(name, "")
        if value:
            return "es" if value.lower().startswith("es") else "en"
    if sys.platform == "win32":
        found = _windows_ui_language()
        if found:
            return found
    try:
        current = locale.getlocale()[0] or ""
    except ValueError:
        current = ""
    return "es" if current.lower().startswith("es") else "en"
