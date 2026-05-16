"""Real-time MedSigLIP fracture classifier runtime.

This module intentionally keeps heavyweight imports inside loader methods so
unit tests can exercise runtime behavior with small fakes.
"""

from __future__ import annotations

import json
import pickle
from contextlib import nullcontext
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_MODEL_ID = "google/medsiglip-448"
DEFAULT_THRESHOLD = 0.0853


@dataclass(frozen=True)
class ClassifierPrediction:
    """A single fracture-classifier prediction."""

    prob_fracture: float
    predicted_fracture: bool
    threshold: float


@dataclass
class FractureClassifier:
    """MedSigLIP encoder plus a sklearn-compatible classifier head."""

    processor: Any
    model: Any
    classifier: Any
    threshold: float = DEFAULT_THRESHOLD
    device: str = "cpu"
    dtype: Any = None
    embedding_cache: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_components(
        cls,
        *,
        processor: Any,
        model: Any,
        classifier: Any,
        threshold: float | None = None,
        metadata_path: Path | None = None,
        cache_path: Path | None = None,
        use_cache: bool = False,
        device: str = "cpu",
        dtype: Any = None,
    ) -> "FractureClassifier":
        metadata = load_metadata(metadata_path)
        resolved_threshold = resolve_threshold(threshold, metadata)
        cache = load_embedding_cache(cache_path) if use_cache else {}
        return cls(
            processor=processor,
            model=model,
            classifier=classifier,
            threshold=resolved_threshold,
            device=device,
            dtype=dtype,
            embedding_cache=cache,
            metadata=metadata,
        )

    @classmethod
    def load(
        cls,
        *,
        model_dir: Path,
        classifier_path: Path,
        metadata_path: Path | None = None,
        cache_path: Path | None = None,
        use_cache: bool = False,
        threshold: float | None = None,
        model_id: str = DEFAULT_MODEL_ID,
        allow_remote_model: bool = False,
        device: str | None = None,
    ) -> "FractureClassifier":
        """Load the production classifier runtime.

        By default the MedSigLIP folder must already exist locally. This keeps
        patient-serving startup deterministic and avoids runtime HF downloads.
        """

        import torch
        from transformers import AutoModel, AutoProcessor

        device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        if device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA device was requested, but torch.cuda.is_available() is false.")
        dtype = torch.float16 if device == "cuda" else torch.float32

        if model_dir.exists():
            model_source: str | Path = model_dir
        elif allow_remote_model:
            model_source = model_id
        else:
            raise FileNotFoundError(
                f"MedSigLIP model directory not found: {model_dir}. "
                "Build/download it first or set allow_remote_model=True for development."
            )

        print(f"Loading MedSigLIP from {model_source} on {device} ...")
        processor = AutoProcessor.from_pretrained(model_source)
        model = AutoModel.from_pretrained(model_source, dtype=dtype).to(device)
        model.eval()

        print(f"Loading fracture classifier from {classifier_path} ...")
        classifier = load_classifier_head(classifier_path)

        runtime = cls.from_components(
            processor=processor,
            model=model,
            classifier=classifier,
            threshold=threshold,
            metadata_path=metadata_path,
            cache_path=cache_path,
            use_cache=use_cache,
            device=device,
            dtype=dtype,
        )
        print(
            "Fracture classifier ready "
            f"(threshold={runtime.threshold:.4f}, cache={runtime.cache_size})."
        )
        return runtime

    @property
    def cache_size(self) -> int:
        return len(self.embedding_cache)

    def predict(self, pil_image: Any, image_id: str | None = None) -> ClassifierPrediction:
        embedding = self._embedding_for_image(pil_image, image_id=image_id)
        prob = predict_probability(self.classifier, embedding)
        return ClassifierPrediction(
            prob_fracture=prob,
            predicted_fracture=prob >= self.threshold,
            threshold=self.threshold,
        )

    def _embedding_for_image(self, pil_image: Any, image_id: str | None = None) -> Any:
        if image_id and image_id in self.embedding_cache:
            cached = self.embedding_cache[image_id]
            return cached.reshape(1, -1) if hasattr(cached, "reshape") else [cached]
        return self.embed_batch([pil_image])

    def embed_batch(self, pil_images: list[Any]) -> Any:
        imgs = [img.convert("RGB") for img in pil_images]
        inputs = self.processor(images=imgs, return_tensors="pt").to(self.device)
        if self.dtype is not None and "pixel_values" in inputs:
            inputs["pixel_values"] = inputs["pixel_values"].to(self.dtype)

        with no_grad_context():
            out = self.model.get_image_features(**inputs)
            if hasattr(out, "pooler_output"):
                out = out.pooler_output
            elif not hasattr(out, "float"):
                out = out[0]
            return out.float().cpu().numpy()


def load_metadata(metadata_path: Path | None) -> dict[str, Any]:
    if not metadata_path or not metadata_path.exists():
        return {}
    with metadata_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def resolve_threshold(threshold: float | None, metadata: dict[str, Any]) -> float:
    if threshold is not None:
        return float(threshold)
    for key in ("threshold", "clinical_threshold", "segmentation_threshold"):
        if key in metadata:
            return float(metadata[key])
    return DEFAULT_THRESHOLD


def load_embedding_cache(cache_path: Path | None) -> dict[str, Any]:
    if not cache_path or not cache_path.exists():
        return {}
    with cache_path.open("rb") as f:
        return pickle.load(f)


def load_classifier_head(classifier_path: Path) -> Any:
    try:
        import joblib

        return joblib.load(classifier_path)
    except Exception:
        with classifier_path.open("rb") as f:
            return pickle.load(f)


def predict_probability(classifier: Any, embedding: Any) -> float:
    proba = classifier.predict_proba(embedding)
    return float(proba[0][1])


def no_grad_context():
    try:
        import torch

        return torch.no_grad()
    except ModuleNotFoundError:
        return nullcontext()
