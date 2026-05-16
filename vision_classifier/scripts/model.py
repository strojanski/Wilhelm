"""Compatibility wrapper for the reusable real-time classifier runtime."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from vision_classifier.runtime import FractureClassifier

MODEL_DIR = Path(__file__).parent.parent / "medsiglip-448"
CLF_PATH = Path(__file__).parent.parent / "fracture_classifier_v3_0.91auc.pkl"
CACHE_PATH = Path(__file__).parent.parent / "embedding_cache.pkl"
METADATA_PATH = CLF_PATH.with_suffix(".json")

_runtime: FractureClassifier | None = None


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def load_model(
    model_dir: Path = MODEL_DIR,
    clf_path: Path = CLF_PATH,
    cache_path: Path = CACHE_PATH,
    metadata_path: Path = METADATA_PATH,
    use_cache: bool | None = None,
    threshold: float | None = None,
    allow_remote_model: bool | None = None,
    device: str | None = None,
) -> None:
    """Load MedSigLIP and the sklearn classifier head.

    The old implementation silently used `embedding_cache.pkl` whenever it
    existed. That hid the real classifier behavior. Cache lookup is now opt-in
    through `USE_EMBEDDING_CACHE=true` or the `use_cache` argument.
    """

    global _runtime
    if use_cache is None:
        use_cache = _env_flag("USE_EMBEDDING_CACHE")
    if allow_remote_model is None:
        allow_remote_model = _env_flag("ALLOW_REMOTE_MEDSIGLIP", default=True)
    if device is None:
        device = os.environ.get("VISION_DEVICE")

    _runtime = FractureClassifier.load(
        model_dir=model_dir,
        classifier_path=clf_path,
        metadata_path=metadata_path,
        cache_path=cache_path,
        use_cache=use_cache,
        threshold=threshold,
        allow_remote_model=allow_remote_model,
        device=device,
    )
    print("Ready.\n")


def predict(pil_image, image_id: str | None = None) -> float:
    if _runtime is None:
        raise RuntimeError("Classifier is not loaded. Call load_model() first.")
    return _runtime.predict(pil_image, image_id=image_id).prob_fracture


def predict_batch(pil_images: list) -> list[float]:
    if _runtime is None:
        raise RuntimeError("Classifier is not loaded. Call load_model() first.")
    return [
        _runtime.predict(pil_image).prob_fracture
        for pil_image in pil_images
    ]


def cache_size() -> int:
    if _runtime is None:
        return 0
    return _runtime.cache_size
