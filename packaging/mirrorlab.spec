# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller recipe for MirrorLab Studio on Windows, macOS and Linux.

Build from the repository root (the same command on every system):

    pip install ".[vcam,packaging]"
    pyinstaller --noconfirm --clean packaging/mirrorlab.spec

The result is ``dist/MirrorLab/`` (and ``dist/MirrorLab.app`` on macOS). The
installers in ``packaging/`` wrap that folder; see packaging/README.md.
"""

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files

ROOT = Path(SPECPATH).resolve().parent  # noqa: F821 - provided by PyInstaller
ICONS = ROOT / "packaging" / "icons"

datas, binaries, hiddenimports = [], [], []
for package in ("mediapipe", "pyvirtualcam"):
    try:
        pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
    except Exception:  # pyvirtualcam is optional: the app then runs preview-only
        continue
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden
datas += collect_data_files("mirrorlab")

# Things that get pulled in transitively but that the app never uses.
excludes = ["pytest", "IPython", "notebook", "scipy", "pandas", "PyQt5", "PyQt6", "PySide2", "PySide6"]

if sys.platform == "win32":
    icon = str(ICONS / "mirrorlab.ico")
elif sys.platform == "darwin":
    icon = str(ICONS / "mirrorlab.icns")
else:
    icon = None

analysis = Analysis(  # noqa: F821
    [str(ROOT / "packaging" / "desktop_entry.py")],
    pathex=[str(ROOT / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)
archive = PYZ(analysis.pure)  # noqa: F821

executable = EXE(  # noqa: F821
    archive,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="MirrorLab",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=icon,
)

bundle = COLLECT(  # noqa: F821
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="MirrorLab",
)

if sys.platform == "darwin":
    app = BUNDLE(  # noqa: F821
        bundle,
        name="MirrorLab.app",
        icon=str(ICONS / "mirrorlab.icns"),
        bundle_identifier="io.github.trinaxcode.mirrorlab",
        info_plist={
            "CFBundleName": "MirrorLab",
            "CFBundleDisplayName": "MirrorLab",
            "CFBundleShortVersionString": "2.2.0",
            "CFBundleVersion": "2.2.0",
            "NSHighResolutionCapable": True,
            "LSApplicationCategoryType": "public.app-category.video",
            "NSCameraUsageDescription": "MirrorLab reads your camera to apply background, framing and light effects. Video never leaves your computer.",
            "NSHumanReadableCopyright": "MIT © 2026 TrinaxCode",
        },
    )
