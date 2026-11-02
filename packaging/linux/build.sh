#!/usr/bin/env bash
# Package the PyInstaller output (dist/MirrorLab) for Linux: a tarball and a .deb.
#
#   packaging/linux/build.sh <version> [dist-dir]
#
# Produces dist-dir/MirrorLab-<version>-linux-x86_64.tar.gz and
# dist-dir/mirrorlab_<version>_amd64.deb. Run it after `pyinstaller packaging/mirrorlab.spec`.
set -euo pipefail

version="${1:?usage: build.sh <version> [dist-dir]}"
dist="${2:-dist}"
root="$(cd "$(dirname "$0")/../.." && pwd)"
arch="$(uname -m)"
case "$arch" in
  x86_64) deb_arch=amd64 ;;
  aarch64) deb_arch=arm64 ;;
  *) deb_arch="$arch" ;;
esac

app="$dist/MirrorLab"
[ -x "$app/MirrorLab" ] || { echo "missing $app/MirrorLab: run pyinstaller first" >&2; exit 1; }

# -- tarball -----------------------------------------------------------------
tar -C "$dist" -czf "$dist/MirrorLab-$version-linux-$arch.tar.gz" MirrorLab
echo "wrote $dist/MirrorLab-$version-linux-$arch.tar.gz"

# -- .deb --------------------------------------------------------------------
stage="$(mktemp -d)"
trap 'rm -rf "$stage"' EXIT
install -d "$stage/opt/mirrorlab" "$stage/usr/bin" "$stage/usr/share/applications" \
  "$stage/usr/share/icons/hicolor/512x512/apps" "$stage/DEBIAN"
cp -a "$app/." "$stage/opt/mirrorlab/"
ln -s /opt/mirrorlab/MirrorLab "$stage/usr/bin/mirrorlab-studio"
install -m 644 "$root/packaging/linux/mirrorlab.desktop" "$stage/usr/share/applications/mirrorlab.desktop"
install -m 644 "$root/packaging/icons/mirrorlab-512.png" "$stage/usr/share/icons/hicolor/512x512/apps/mirrorlab.png"

size_kb="$(du -sk "$stage" | cut -f1)"
cat > "$stage/DEBIAN/control" <<CONTROL
Package: mirrorlab
Version: $version
Section: video
Priority: optional
Architecture: $deb_arch
Installed-Size: $size_kb
Depends: libgl1, libegl1, libgles2, libglib2.0-0 | libglib2.0-0t64
Recommends: v4l2loopback-dkms
Maintainer: TrinaxCode <trinaxcode@users.noreply.github.com>
Homepage: https://github.com/TrinaxCode/mirrorlab
Description: Virtual camera with background blur, auto-framing and gesture control
 MirrorLab publishes your webcam as a virtual camera for Zoom, Meet, Teams,
 Discord and OBS, with background blur, auto-framing, studio light, a privacy
 shutter and hand-gesture control. It runs on the CPU and sends no video anywhere.
 Publishing to a virtual camera needs the v4l2loopback kernel module.
CONTROL

dpkg-deb --root-owner-group --build "$stage" "$dist/mirrorlab_${version}_${deb_arch}.deb" >/dev/null
echo "wrote $dist/mirrorlab_${version}_${deb_arch}.deb"
