"""Unit tests for the pure studio components: settings, state, background, framing, light, privacy.

Nothing here needs a camera, a model, a display or the network.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from mirrorlab.studio.background import (
    BackgroundProcessor,
    TemporalMask,
    blur_background,
    composite,
    cover_resize,
)
from mirrorlab.studio.framing import AutoFramer, face_boxes, union_box
from mirrorlab.studio.light import StudioLight, gamma_lut
from mirrorlab.studio.privacy import AwayDetector, PrivacyShutter, render_card
from mirrorlab.studio.settings import PROFILES, StudioSettings
from mirrorlab.studio.state import StudioState, parse_action


def textured(height: int = 120, width: int = 160) -> np.ndarray:
    ys, xs = np.mgrid[0:height, 0:width]
    image = np.stack([(xs * 3) % 256, (ys * 5) % 256, (xs + ys) % 256], axis=-1)
    return image.astype(np.uint8)


# --------------------------------------------------------------------------- #
# settings
# --------------------------------------------------------------------------- #
class TestSettings:
    def test_defaults_are_valid(self):
        settings = StudioSettings()
        assert settings.width % 2 == 0 and settings.height % 2 == 0

    def test_unknown_key_is_rejected_with_the_valid_keys(self):
        with pytest.raises(ValueError, match="Unknown studio setting"):
            StudioSettings.from_mapping({"backgroud": "blur"})

    @pytest.mark.parametrize(
        "bad",
        [
            {"background": "sepia"},
            {"width": 1281},
            {"fps": 0},
            {"blur_strength": 2},
            {"mask_smoothing": 1.0},
            {"max_zoom": 9},
            {"privacy_mode": "pink"},
            {"away_after": -1},
            {"dwell": {"open_palm": 99}},
            {"bindings": {"fist": ""}},
        ],
    )
    def test_invalid_values_are_rejected(self, bad):
        with pytest.raises(ValueError):
            StudioSettings.from_mapping(bad)

    def test_every_builtin_profile_is_valid(self):
        for name in PROFILES:
            assert StudioSettings.load(profile=name)

    def test_unknown_profile_lists_the_available_ones(self):
        with pytest.raises(ValueError, match="meeting"):
            StudioSettings.load(profile="nope")

    def test_precedence_is_profile_then_file_then_overrides(self, tmp_path):
        path = tmp_path / "studio.json"
        path.write_text(json.dumps({"blur_strength": 31, "background": "off"}))
        settings = StudioSettings.load(path, profile="meeting", overrides={"blur_strength": 99})
        assert settings.auto_frame is True  # from the profile
        assert settings.background == "off"  # the file beats the profile
        assert settings.blur_strength == 99  # an explicit override beats the file

    def test_user_profiles_in_the_file(self, tmp_path):
        path = tmp_path / "studio.json"
        path.write_text(json.dumps({"profiles": {"podcast": {"background": "green", "auto_frame": True}}}))
        settings = StudioSettings.load(path, profile="podcast")
        assert settings.background == "green" and settings.auto_frame

    def test_none_overrides_are_ignored(self):
        assert StudioSettings.load(overrides={"background": None}).background == "off"

    def test_roundtrip_through_json(self):
        original = StudioSettings.load(profile="privacy")
        assert StudioSettings.from_mapping(json.loads(original.to_json())) == original


# --------------------------------------------------------------------------- #
# state and actions
# --------------------------------------------------------------------------- #
class TestState:
    def test_parse_action(self):
        assert parse_action("Background:Blur") == ("background", "blur")
        assert parse_action("privacy") == ("privacy", "")

    def test_privacy_toggles_and_sets(self):
        state = StudioState()
        assert state.apply_action("privacy").ok and state.privacy
        assert state.apply_action("privacy").ok and not state.privacy
        state.apply_action("privacy:on")
        state.apply_action("privacy:on")
        assert state.privacy  # explicit 'on' is idempotent, not a toggle
        assert not state.apply_action("privacy:maybe").ok

    def test_background_validation(self):
        state = StudioState()
        assert state.apply_action("background:blur").ok and state.background == "blur"
        assert not state.apply_action("background:sepia").ok
        assert state.background == "blur"  # a rejected action changes nothing

    def test_replace_needs_an_image(self):
        state = StudioState()
        assert not state.apply_action("background:replace").ok
        state.has_replace_image = True
        assert state.apply_action("background:replace").ok

    def test_background_next_skips_unusable_modes(self):
        state = StudioState()
        seen = []
        for _ in range(4):
            state.apply_action("background_next")
            seen.append(state.background)
        assert seen == ["blur", "off", "blur", "off"]  # no 'replace' without an image
        state.has_replace_image = True
        state.background = "blur"
        state.apply_action("background_next")
        assert state.background == "replace"

    def test_from_settings_reports_replace_without_image_honestly(self):
        settings = StudioSettings.from_mapping({"background": "replace"})
        assert StudioState.from_settings(settings, has_replace_image=False).background == "blur"
        assert StudioState.from_settings(settings, has_replace_image=True).background == "replace"

    def test_reactions_queue_and_drain(self):
        state = StudioState()
        assert state.apply_action("reaction:love").ok
        assert not state.apply_action("reaction:unicorn").ok
        assert state.drain_reactions() == ["love"]
        assert state.drain_reactions() == []

    def test_unknown_action_never_raises(self):
        assert not StudioState().apply_action("rm -rf /").ok
        assert not StudioState().apply_action("").ok

    def test_noop_does_not_count_as_a_change(self):
        state = StudioState()
        state.apply_action("noop")
        assert state.changes == 0


# --------------------------------------------------------------------------- #
# background
# --------------------------------------------------------------------------- #
class TestBackground:
    def test_composite_extremes(self):
        fg, bg = np.full((8, 8, 3), 200, np.uint8), np.full((8, 8, 3), 10, np.uint8)
        assert np.array_equal(composite(fg, bg, np.ones((8, 8), np.float32)), fg)
        assert np.array_equal(composite(fg, bg, np.zeros((8, 8), np.float32)), bg)
        half = composite(fg, bg, np.full((8, 8), 0.5, np.float32))
        assert abs(int(half[0, 0, 0]) - 105) <= 1

    def test_blur_preserves_shape_and_reduces_detail(self):
        frame = textured()
        blurred = blur_background(frame, 51)
        assert blurred.shape == frame.shape
        assert blurred.astype(float).std() < frame.astype(float).std()

    def test_cover_resize_crops_instead_of_stretching(self):
        image = np.zeros((100, 400, 3), np.uint8)
        image[:, 150:250] = 255  # a centred bright block, 100 px wide
        out = cover_resize(image, (100, 100))
        assert out.shape == (100, 100, 3)
        assert out.min() == 255  # only the central block survives a cover crop

    def test_off_returns_the_same_frame(self):
        frame = textured()
        assert BackgroundProcessor("off").apply(frame, None) is frame

    def test_fail_closed_when_no_mask(self):
        """The central privacy guarantee: no mask must never mean 'show the room'."""
        frame = textured()
        for mode in ("blur", "replace", "green", "black"):
            processor = BackgroundProcessor(mode)
            out = processor.apply(frame, None)
            assert not np.array_equal(out, frame), mode
            assert processor.fail_closed_frames == 1
            assert out.astype(float).std() < frame.astype(float).std(), mode

    def test_person_pixels_are_kept_and_background_is_replaced(self):
        frame = textured()
        mask = np.zeros(frame.shape[:2], np.float32)
        mask[:, :80] = 1.0  # left half is "person"
        out = BackgroundProcessor("black", smoothing=0.0).apply(frame, mask)
        assert np.array_equal(out[:, :70], frame[:, :70])
        assert out[:, 90:].max() == 0

    def test_green_mode_uses_chroma_green(self):
        frame = textured()
        out = BackgroundProcessor("green", smoothing=0.0).apply(frame, np.zeros(frame.shape[:2], np.float32))
        assert tuple(out[5, 5]) == (0, 177, 64)

    def test_replace_without_a_readable_image_falls_back_to_blur(self, tmp_path):
        processor = BackgroundProcessor("replace", image_path=str(tmp_path / "missing.jpg"))
        assert not processor.has_image
        frame = textured()
        out = processor.apply(frame, np.zeros(frame.shape[:2], np.float32))
        assert out.shape == frame.shape

    def test_replace_uses_the_image(self, tmp_path):
        import cv2

        path = tmp_path / "bg.png"
        cv2.imwrite(str(path), np.full((50, 50, 3), (10, 200, 30), np.uint8))
        processor = BackgroundProcessor("replace", image_path=str(path), smoothing=0.0)
        assert processor.has_image
        frame = textured()
        out = processor.apply(frame, np.zeros(frame.shape[:2], np.float32))
        assert tuple(out[3, 3]) == (10, 200, 30)

    def test_low_resolution_mask_is_scaled_to_the_frame(self):
        frame = textured(120, 160)
        mask = np.ones((12, 16), np.float32)
        out = BackgroundProcessor("blur", smoothing=0.0).apply(frame, mask)
        assert out.shape == frame.shape
        assert np.array_equal(out, frame)  # an all-person mask changes nothing

    def test_temporal_mask_smooths_shimmer_but_follows_real_motion(self):
        temporal = TemporalMask(smoothing=0.6)
        temporal.update(np.full((4, 4), 0.5, np.float32))
        small = temporal.update(np.full((4, 4), 0.6, np.float32))
        assert 0.5 < small[0, 0] < 0.6  # a small change is damped
        jump = temporal.update(np.full((4, 4), 1.0, np.float32))
        assert jump[0, 0] > 0.9  # a large change (the subject moved) is trusted

    def test_temporal_mask_resets_on_shape_change(self):
        temporal = TemporalMask(0.9)
        temporal.update(np.zeros((4, 4), np.float32))
        assert temporal.update(np.ones((8, 8), np.float32)).max() == 1.0


# --------------------------------------------------------------------------- #
# framing
# --------------------------------------------------------------------------- #
class TestFraming:
    BOX = (0.55, 0.20, 0.70, 0.45)  # a face right of centre

    def test_union_box(self):
        assert union_box([]) is None
        assert union_box([(0.1, 0.2, 0.3, 0.4), (0.5, 0.1, 0.6, 0.9)]) == (0.1, 0.1, 0.6, 0.9)

    def test_face_boxes_falls_back_to_landmarks(self):
        class Face:
            bbox = None
            landmarks = np.array([[0.2, 0.3, 0], [0.4, 0.5, 0]])

        assert face_boxes([Face()]) == [(0.2, 0.3, 0.4, 0.5)]

    def test_starts_at_full_frame_and_frames_the_first_face_immediately(self):
        framer = AutoFramer((640, 360))
        rect = framer.update([], now=0.0)
        assert (rect.w, rect.h) == (640, 360)
        rect = framer.update([self.BOX], now=0.1)
        assert rect.w < 640 and rect.h < 360

    def test_crop_keeps_the_frame_aspect_ratio_and_stays_inside(self):
        framer = AutoFramer((640, 360))
        for index in range(60):
            rect = framer.update([self.BOX], now=index / 30)
            assert rect.w / rect.h == pytest.approx(640 / 360, rel=1e-6)
            assert rect.x >= -1e-6 and rect.y >= -1e-6
            assert rect.x + rect.w <= 640 + 1e-6 and rect.y + rect.h <= 360 + 1e-6

    def test_zoom_is_bounded(self):
        framer = AutoFramer((640, 360), max_zoom=1.5)
        tiny = (0.50, 0.50, 0.52, 0.53)
        for index in range(120):
            framer.update([tiny], now=index / 30)
        assert framer.zoom <= 1.5 + 1e-6

    def test_deadzone_ignores_small_jitter(self):
        framer = AutoFramer((640, 360))
        for index in range(90):
            framer.update([self.BOX], now=index / 30)
        before = framer.update([self.BOX], now=3.1)
        jittered = (self.BOX[0] + 0.004, self.BOX[1] + 0.004, self.BOX[2] + 0.004, self.BOX[3] + 0.004)
        after = framer.update([jittered], now=3.2)
        assert abs(after.x - before.x) < 0.5 and abs(after.y - before.y) < 0.5

    def test_is_frame_rate_independent(self):
        def run(rate: int) -> float:
            framer = AutoFramer((640, 360))
            framer.update([(0.2, 0.2, 0.3, 0.4)], now=0.0)
            for index in range(1, rate + 1):  # one simulated second
                framer.update([(0.7, 0.3, 0.8, 0.5)], now=index / rate)
            return framer.zoom

        assert run(15) == pytest.approx(run(60), rel=0.05)

    def test_holds_then_eases_back_when_the_face_is_lost(self):
        framer = AutoFramer((640, 360), hold=1.0)
        for index in range(60):
            framer.update([self.BOX], now=index / 30)
        zoomed = framer.zoom
        assert zoomed > 1.05
        framer.update([], now=2.5)  # lost, still inside the hold window
        assert framer.zoom == pytest.approx(zoomed, rel=0.05)
        for index in range(1, 200):
            framer.update([], now=2.5 + index / 30)
        assert framer.zoom == pytest.approx(1.0, abs=0.02)

    def test_crop_is_identity_for_the_full_frame(self):
        framer = AutoFramer((160, 120))
        frame = textured()
        assert framer.crop(frame, framer.update([], now=0.0)) is frame

    def test_crop_returns_the_original_size(self):
        framer = AutoFramer((160, 120))
        rect = framer.update([(0.4, 0.3, 0.6, 0.5)], now=0.0)
        assert framer.crop(textured(), rect).shape == (120, 160, 3)

    def test_reset_returns_to_the_full_frame(self):
        framer = AutoFramer((640, 360))
        framer.update([self.BOX], now=0.0)
        framer.reset()
        assert framer.zoom == 1.0


# --------------------------------------------------------------------------- #
# light
# --------------------------------------------------------------------------- #
class TestLight:
    BOX = (0.3, 0.2, 0.7, 0.8)

    def test_gamma_lut_endpoints_and_direction(self):
        assert gamma_lut(0.5)[0] == 0 and gamma_lut(0.5)[255] == 255
        assert gamma_lut(0.5)[100] > 100 > gamma_lut(2.0)[100]

    def test_dark_face_is_brightened(self):
        frame = np.full((120, 160, 3), 40, np.uint8)
        light = StudioLight(strength=1.0)
        out = light.apply(frame, self.BOX, now=0.0)
        assert out.mean() > frame.mean() and light.gamma < 1.0

    def test_bright_face_is_darkened_but_bounded(self):
        frame = np.full((120, 160, 3), 250, np.uint8)
        light = StudioLight(strength=1.0)
        light.apply(frame, self.BOX, now=0.0)
        assert 1.0 < light.gamma <= 1.25

    def test_black_frame_is_ignored(self):
        """A covered lens carries no exposure information; do not blow it out."""
        light = StudioLight(strength=1.0)
        light.apply(np.zeros((120, 160, 3), np.uint8), self.BOX, now=0.0)
        assert light.gamma == 1.0

    def test_no_face_holds_the_current_correction(self):
        light = StudioLight(strength=1.0)
        light.apply(np.full((120, 160, 3), 40, np.uint8), self.BOX, now=0.0)
        held = light.gamma
        light.apply(np.full((120, 160, 3), 40, np.uint8), None, now=0.5)
        assert light.gamma == held

    def test_correction_is_smoothed_over_time(self):
        light = StudioLight(strength=1.0, tau=1.0)
        dark = np.full((120, 160, 3), 40, np.uint8)
        light.apply(dark, self.BOX, now=0.0)
        settled = light.gamma
        light.apply(np.full((120, 160, 3), 200, np.uint8), self.BOX, now=0.033)
        assert abs(light.gamma - settled) < 0.05  # one bright frame barely moves it

    def test_strength_zero_is_a_no_op(self):
        frame = np.full((120, 160, 3), 40, np.uint8)
        assert StudioLight(strength=0.0).apply(frame, self.BOX, now=0.0) is frame


# --------------------------------------------------------------------------- #
# privacy
# --------------------------------------------------------------------------- #
class TestPrivacy:
    def test_open_shutter_is_transparent(self):
        frame = textured()
        assert PrivacyShutter().apply(frame, now=0.0) is frame

    @pytest.mark.parametrize("mode", ["card", "black", "blur"])
    def test_closed_shutter_leaks_no_camera_pixels(self, mode):
        """When fully closed, the output must not depend on the camera frame at all."""
        shutter = PrivacyShutter(mode=mode, fade=0.0)
        shutter.set_closed(True)
        a = shutter.apply(textured(), now=0.0)
        b = shutter.apply(np.full((120, 160, 3), 255, np.uint8), now=0.1)
        if mode == "blur":
            assert a.astype(float).std() < textured().astype(float).std()
        else:
            assert np.array_equal(a, b)

    def test_fade_passes_through_intermediate_levels(self):
        shutter = PrivacyShutter(mode="black", fade=1.0)
        shutter.set_closed(True)
        levels = []
        for step in range(0, 13):
            shutter.apply(textured(), now=step * 0.1)
            levels.append(shutter.level)
        assert levels[0] == 0.0 and levels[-1] == 1.0
        assert all(b >= a for a, b in zip(levels, levels[1:]))
        assert any(0.0 < level < 1.0 for level in levels)

    def test_force_covers_without_touching_the_users_state(self):
        shutter = PrivacyShutter(mode="black", fade=0.0)
        out = shutter.apply(textured(), now=0.0, force=True)
        assert out.max() == 0 and shutter.closed is False
        assert shutter.apply(textured(), now=0.1, force=False).max() > 0

    def test_toggle(self):
        shutter = PrivacyShutter()
        assert shutter.toggle() is True and shutter.toggle() is False

    def test_card_renders_independently_of_any_frame(self):
        card = render_card((320, 180), "Be right back")
        assert card.shape == (180, 320, 3) and card.max() > card.min()

    def test_card_shrinks_long_text_to_fit(self):
        assert render_card((200, 100), "x" * 80).shape == (100, 200, 3)


class TestAwayDetector:
    def test_triggers_after_the_timeout_and_clears_on_return(self):
        away = AwayDetector(timeout=2.0)
        assert away.update(False, now=0.0) is False
        assert away.update(False, now=1.9) is False
        assert away.update(False, now=2.0) is True
        assert away.update(True, now=2.1) is False

    def test_a_brief_return_resets_the_clock(self):
        away = AwayDetector(timeout=2.0)
        away.update(False, now=0.0)
        away.update(True, now=1.5)
        assert away.update(False, now=3.0) is False  # clock restarted at 3.0

    def test_zero_timeout_disables_it(self):
        assert AwayDetector(0.0).update(False, now=999.0) is False
