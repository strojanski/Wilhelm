"""Guards: default CLASSIFIER_MODE must not pull in MedSigLIP/transformers
or require CUDA, and an unknown mode must fail loudly."""

import importlib
import sys
from pathlib import Path

import pytest

VISION_DIR = str(Path(__file__).resolve().parents[1])


def _fresh_import(monkeypatch, mode):
    monkeypatch.setenv("CLASSIFIER_MODE", mode)
    if VISION_DIR not in sys.path:
        sys.path.insert(0, VISION_DIR)
    for name in ("vision_api", "vision_api_embeddings", "vision_api_live"):
        sys.modules.pop(name, None)
    sys.modules.pop("transformers", None)
    return importlib.import_module("vision_api")


def test_default_mode_is_embeddings_and_skips_transformers(monkeypatch):
    monkeypatch.delenv("CLASSIFIER_MODE", raising=False)
    if VISION_DIR not in sys.path:
        sys.path.insert(0, VISION_DIR)
    for name in ("vision_api", "vision_api_embeddings", "vision_api_live"):
        sys.modules.pop(name, None)
    sys.modules.pop("transformers", None)
    mod = importlib.import_module("vision_api")
    assert mod.app is not None
    assert "transformers" not in sys.modules
    assert "vision_classifier.runtime" not in sys.modules


def test_embeddings_mode_imports_without_transformers(monkeypatch):
    mod = _fresh_import(monkeypatch, "embeddings")
    assert mod.app is not None
    assert "transformers" not in sys.modules


def test_unknown_mode_raises(monkeypatch):
    monkeypatch.setenv("CLASSIFIER_MODE", "bogus")
    if VISION_DIR not in sys.path:
        sys.path.insert(0, VISION_DIR)
    for name in ("vision_api", "vision_api_embeddings", "vision_api_live"):
        sys.modules.pop(name, None)
    with pytest.raises(RuntimeError, match="Unknown CLASSIFIER_MODE"):
        importlib.import_module("vision_api")
