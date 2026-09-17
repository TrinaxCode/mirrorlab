"""Configuration layering, validation and environment overrides."""

from __future__ import annotations

import json

import pytest

from mirrorlab.config import DEFAULTS, Config, config_paths, load_config_file


def test_defaults_are_valid():
    config = Config()
    assert config.camera_index == 0
    assert config.filter == "original"
    assert config.enable_face and config.enable_hands
    assert config.effects == []


def test_every_default_key_is_a_field():
    """A key in DEFAULTS that is not a dataclass field would be silently ignored."""
    from dataclasses import fields

    names = {f.name for f in fields(Config)}
    assert set(DEFAULTS) == names


def test_unknown_key_is_rejected_with_a_helpful_message():
    with pytest.raises(ValueError) as excinfo:
        Config.from_mapping({"camra_index": 1})
    message = str(excinfo.value)
    assert "camra_index" in message
    assert "mirrorlab config --list" in message


@pytest.mark.parametrize(
    "overrides, fragment",
    [
        ({"camera_fps": 0}, "camera_fps"),
        ({"min_face_confidence": 1.5}, "min_face_confidence"),
        ({"model_complexity": 7}, "model_complexity"),
        ({"theme": "neon"}, "theme"),
        ({"snapshot_format": "bmp"}, "snapshot_format"),
        ({"camera_backend": "magic"}, "camera_backend"),
        ({"expression_smoothing": -1}, "expression_smoothing"),
        ({"effects": "sunglasses"}, "effects"),
    ],
)
def test_invalid_values_are_rejected(overrides, fragment):
    with pytest.raises(ValueError) as excinfo:
        Config.from_mapping(overrides)
    assert fragment in str(excinfo.value)


def test_with_overrides_returns_a_new_frozen_instance():
    base = Config()
    changed = base.with_overrides(filter="cartoon", camera_index=2)
    assert changed.filter == "cartoon"
    assert changed.camera_index == 2
    assert base.filter == "original", "the original config must never mutate"
    import dataclasses

    with pytest.raises(dataclasses.FrozenInstanceError):
        base.filter = "sepia"  # type: ignore[misc]


def test_with_overrides_ignores_none():
    base = Config()
    assert base.with_overrides(filter=None) == base


def test_roundtrip_through_json(tmp_path):
    config = Config().with_overrides(filter="cartoon+vignette", effects=["dog"], theme="magma")
    path = config.save(tmp_path / "mirrorlab.json")
    reloaded = Config.load(path, use_env=False)
    assert reloaded == config


def test_load_config_file_rejects_non_mapping(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(ValueError):
        load_config_file(path)


def test_env_overrides_are_coerced(monkeypatch):
    monkeypatch.setenv("MIRRORLAB_FILTER", "sketch")
    monkeypatch.setenv("MIRRORLAB_CAMERA_INDEX", "3")
    monkeypatch.setenv("MIRRORLAB_MIRROR", "false")
    monkeypatch.setenv("MIRRORLAB_EFFECTS", "dog, crown")
    config = Config.load(use_env=True)
    assert config.filter == "sketch"
    assert config.camera_index == 3
    assert config.mirror is False
    assert config.effects == ["dog", "crown"]


def test_env_override_rejects_a_bad_boolean(monkeypatch):
    monkeypatch.setenv("MIRRORLAB_MIRROR", "maybe")
    with pytest.raises(ValueError):
        Config.load(use_env=True)


def test_config_paths_are_absolute_and_ordered():
    paths = config_paths()
    assert paths, "at least one search path is required"
    assert all(p.is_absolute() for p in paths)


def test_to_dict_is_json_serialisable():
    json.dumps(Config().to_dict())
