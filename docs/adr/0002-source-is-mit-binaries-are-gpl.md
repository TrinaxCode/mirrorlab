# 2. The source is MIT; the packaged apps are GPL-2.0

- Status: accepted
- Date: 2026-11-02

## Context

MirrorLab's code is MIT. Publishing a frame as a system camera needs `pyvirtualcam`, which is
GPL-2.0. A Python install can keep that optional (`pip install "mirrorlab[vcam]"`), but a
double-click desktop app has to work without extra steps, so the installers bundle it.

## Decision

- The repository stays MIT, and `pyvirtualcam` stays an opt-in extra for source installs.
- The installers published on the release page bundle `pyvirtualcam`, so they are distributed
  under GPL-2.0, with the complete corresponding source in this repository at the release tag.
- This is stated on the download page, in the README, in the release notes and in
  `THIRD_PARTY_LICENSES.md`.

## Consequences

Anyone who wants MIT-only terms can build from source without the `vcam` extra. MIT code may
be included in a GPL-2.0 combined work, so there is no conflict. If a subprocess bridge to a
separate virtual-camera helper replaces the library, the installers can return to MIT.
