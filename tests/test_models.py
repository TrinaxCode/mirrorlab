"""Model downloads: the pinned SHA-256 must be enforced and must never poison the cache."""

from __future__ import annotations

import hashlib
import io
import re

import pytest

from mirrorlab.detectors import models
from mirrorlab.detectors.models import MODELS, ModelIntegrityError, ModelSpec, download_model, ensure_model


class _FakeResponse(io.BytesIO):
    def __init__(self, payload: bytes) -> None:
        super().__init__(payload)
        self.headers = {"Content-Length": str(len(payload))}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


PAYLOAD = b"\x00MODEL" * 400  # > 1 KiB so the cheap validity check accepts it


@pytest.fixture
def served(monkeypatch, tmp_path):
    """Serve PAYLOAD for any URL and cache into a temp directory."""
    monkeypatch.setenv("MIRRORLAB_MODELS", str(tmp_path))
    monkeypatch.delenv("MIRRORLAB_MODEL_VERIFY", raising=False)
    monkeypatch.setattr(models.urllib.request, "urlopen", lambda *a, **k: _FakeResponse(PAYLOAD))
    monkeypatch.setattr(models, "model_search_paths", lambda: [tmp_path])
    return tmp_path


def _spec(sha256: str) -> ModelSpec:
    return ModelSpec("toy", "toy.task", "https://example.invalid/toy.task", 0.001, "test", sha256)


def test_every_shipped_model_pins_a_sha256():
    for key, spec in MODELS.items():
        assert re.fullmatch(r"[0-9a-f]{64}", spec.sha256), f"{key} has no valid SHA-256"


def test_a_matching_checksum_is_accepted(served, monkeypatch):
    monkeypatch.setitem(MODELS, "toy", _spec(hashlib.sha256(PAYLOAD).hexdigest()))
    path = download_model("toy")
    assert path.read_bytes() == PAYLOAD


def test_a_mismatch_is_rejected_and_nothing_is_cached(served, monkeypatch):
    monkeypatch.setitem(MODELS, "toy", _spec("0" * 64))
    with pytest.raises(ModelIntegrityError, match="pinned checksum"):
        download_model("toy")
    assert not (served / "toy.task").exists()
    assert not list(served.glob(".download-*")), "temp file must be cleaned up"


def test_ensure_model_degrades_instead_of_crashing_on_a_mismatch(served, monkeypatch):
    monkeypatch.setitem(MODELS, "toy", _spec("0" * 64))
    assert ensure_model("toy") is None


def test_verification_can_be_disabled_explicitly(served, monkeypatch):
    monkeypatch.setitem(MODELS, "toy", _spec("0" * 64))
    monkeypatch.setenv("MIRRORLAB_MODEL_VERIFY", "0")
    assert download_model("toy").exists()
