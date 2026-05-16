"""Vision API entrypoint — selects the fracture-classifier backend.

CLASSIFIER_MODE=embeddings (default): legacy cached-embeddings + SAM pipeline.
  CPU-only, no Hugging Face token, no transformers/MedSigLIP import, no GPU
  requirement. This is master_local's unchanged behavior.

CLASSIFIER_MODE=live: real-time MedSigLIP FractureClassifier pipeline (opt-in).
"""

from __future__ import annotations

import os

CLASSIFIER_MODE = os.environ.get("CLASSIFIER_MODE", "embeddings").strip().lower()

if CLASSIFIER_MODE == "live":
    from vision_api_live import app  # noqa: F401
elif CLASSIFIER_MODE in ("", "embeddings"):
    from vision_api_embeddings import app  # noqa: F401
else:
    raise RuntimeError(
        f"Unknown CLASSIFIER_MODE={CLASSIFIER_MODE!r}; expected 'embeddings' or 'live'."
    )

__all__ = ["app"]
