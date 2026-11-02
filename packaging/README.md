# Packaging the desktop app

MirrorLab's desktop app is frozen with [PyInstaller](https://pyinstaller.org) and wrapped in
one installer per system. CI does all of this on every `v*` tag
([`.github/workflows/release.yml`](../.github/workflows/release.yml)); the steps below are the
same ones, for building on your own machine.

PyInstaller cannot cross-compile: build on the system you are targeting.

| System | Output | Tooling |
| --- | --- | --- |
| Linux | `mirrorlab_<version>_amd64.deb`, `MirrorLab-<version>-linux-x86_64.tar.gz` | `dpkg-deb` |
| Windows | `MirrorLab-<version>-windows-setup.exe`, `MirrorLab-<version>-windows-portable.zip` | [Inno Setup 6](https://jrsoftware.org/isinfo.php) |
| macOS | `MirrorLab-<version>-macos-arm64.dmg` | `hdiutil`, `codesign` (ad-hoc) |

## Build

```bash
python3 -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install ".[vcam,packaging]"
pyinstaller --noconfirm --clean packaging/mirrorlab.spec    # -> dist/MirrorLab (and MirrorLab.app on macOS)
```

Then check the frozen app before you wrap it:

```bash
dist/MirrorLab/MirrorLab --self-test self-test.json          # imports, models, 20 frames; exit 0 = healthy
python packaging/gui_smoke.py dist/MirrorLab/MirrorLab       # opens the window, waits for a frame
```

Package it:

```bash
packaging/linux/build.sh 2.2.0 dist       # .deb + .tar.gz
packaging/macos/build.sh 2.2.0 dist       # .dmg
iscc /DAppVersion=2.2.0 packaging\windows\mirrorlab.iss     # setup .exe
```

The version passed to the scripts must match `src/mirrorlab/version.py`; CI refuses a tag that
does not.

## Layout

| Path | What it is |
| --- | --- |
| `mirrorlab.spec` | The PyInstaller recipe (collects MediaPipe, pyvirtualcam and their data files) |
| `desktop_entry.py` | The frozen entry point |
| `gui_smoke.py` | Starts the app headlessly and waits for the first preview frame |
| `icons/` | The icon as SVG, PNG, `.ico` and `.icns` |
| `linux/` | `build.sh` and the `.desktop` launcher |
| `macos/build.sh` | The `.dmg` |
| `windows/mirrorlab.iss` | The Inno Setup script |

## Things to know

- **Licence.** The bundle includes `pyvirtualcam` (GPL-2.0), so the binaries are GPL-2.0. The
  source in the repository stays MIT. See [THIRD_PARTY_LICENSES.md](../THIRD_PARTY_LICENSES.md).
- **macOS is not notarised.** The app is ad-hoc signed so Apple silicon will run it, but
  notarisation needs a paid Apple Developer ID. The first launch is right-click, *Open*.
- **Windows is not code-signed**, so SmartScreen may warn on first run.
- **Models are not bundled.** They are downloaded on first use, verified against a pinned
  SHA-256, and cached in the user's data folder.
- **A virtual camera driver is still a separate install** (v4l2loopback on Linux, OBS on
  Windows and macOS). The app detects a missing driver and says what to install.
