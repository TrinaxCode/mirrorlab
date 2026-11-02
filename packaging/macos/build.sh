#!/usr/bin/env bash
# Wrap dist/MirrorLab.app in a compressed disk image.
#
#   packaging/macos/build.sh <version> [dist-dir]
#
# The app is ad-hoc signed so that Apple Silicon will run it, but it is not
# notarised (that needs a paid Apple Developer ID): the first launch is
# right-click > Open. See packaging/README.md.
set -euo pipefail

version="${1:?usage: build.sh <version> [dist-dir]}"
dist="${2:-dist}"
app="$dist/MirrorLab.app"
[ -d "$app" ] || { echo "missing $app: run pyinstaller first" >&2; exit 1; }

codesign --force --deep --sign - "$app"

arch="$(uname -m)"
stage="$(mktemp -d)"
trap 'rm -rf "$stage"' EXIT
cp -R "$app" "$stage/"
ln -s /Applications "$stage/Applications"

out="$dist/MirrorLab-$version-macos-$arch.dmg"
rm -f "$out"
hdiutil create -volname "MirrorLab" -srcfolder "$stage" -ov -format UDZO "$out" >/dev/null
echo "wrote $out"
