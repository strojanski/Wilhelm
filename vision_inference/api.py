"""Compatibility wrapper for the integrated vision API.

The production FastAPI app lives in `vision/vision_api.py`. This module keeps
the old `uvicorn api:app` entrypoint working from `vision_inference/` without
duplicating the classifier/segmentation pipeline.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VISION_DIR = ROOT / "vision"
if str(VISION_DIR) not in sys.path:
    sys.path.insert(0, str(VISION_DIR))

from vision_api import app
