"""FastAPI vision inference service: fracture classification and segmentation."""

from __future__ import annotations

import base64
import io
import os
import sys
from pathlib import Path
from typing import List

import httpx
import numpy as np
import torch
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
from pydantic import BaseModel

ROOT = Path(os.environ.get("MODEL_ROOT", Path(__file__).parent.parent))
CLF_PATH = Path(os.environ.get("CLF_PATH", ROOT / "vision_classifier/fracture_classifier_v3_0.91auc.pkl"))
CLF_METADATA_PATH = Path(os.environ.get("CLF_METADATA_PATH", CLF_PATH.with_suffix(".json")))
CACHE_PATH = Path(os.environ.get("CACHE_PATH", ROOT / "vision_classifier/embedding_cache.pkl"))
MEDSIGLIP_MODEL_DIR = Path(os.environ.get("MEDSIGLIP_MODEL_DIR", ROOT / "vision_classifier/medsiglip-448"))
YOLO_WEIGHTS = Path(os.environ.get("YOLO_WEIGHTS", ROOT / "vision_segmentation/weights/best.pt"))
SAM_CHECKPOINT = Path(os.environ.get("SAM_CHECKPOINT", ROOT / "vision_segmentation/SAM-Med2D/sam-med2d_b.pth"))
SAM_SRC = Path(os.environ.get("SAM_SRC", ROOT / "vision_segmentation/SAM-Med2D"))

THRESHOLD_ENV = os.environ.get("FRACTURE_THRESHOLD")
THRESHOLD = float(THRESHOLD_ENV) if THRESHOLD_ENV else None
REQUESTED_DEVICE = os.environ.get("VISION_DEVICE", "cuda" if torch.cuda.is_available() else "cpu").lower()
if REQUESTED_DEVICE == "cuda" and not torch.cuda.is_available():
    raise RuntimeError("VISION_DEVICE=cuda was requested, but torch.cuda.is_available() is false.")
DEVICE = REQUESTED_DEVICE
USE_EMBEDDING_CACHE = os.environ.get("USE_EMBEDDING_CACHE", "false").lower() in {"1", "true", "yes"}
ALLOW_REMOTE_MEDSIGLIP = os.environ.get("ALLOW_REMOTE_MEDSIGLIP", "false").lower() in {"1", "true", "yes"}

sys.path.insert(0, str(ROOT))
from vision_classifier.runtime import DEFAULT_THRESHOLD, FractureClassifier

app = FastAPI(title="Vision Inference API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_resources: dict = {}


@app.on_event("startup")
def load_models() -> None:
    print("Loading real-time MedSigLIP fracture classifier ...")
    _resources["classifier"] = FractureClassifier.load(
        model_dir=MEDSIGLIP_MODEL_DIR,
        classifier_path=CLF_PATH,
        metadata_path=CLF_METADATA_PATH,
        cache_path=CACHE_PATH,
        use_cache=USE_EMBEDDING_CACHE,
        threshold=THRESHOLD,
        allow_remote_model=ALLOW_REMOTE_MEDSIGLIP,
        device=DEVICE,
    )

    print("Loading YOLO ...")
    from ultralytics import YOLO

    _resources["detector"] = YOLO(str(YOLO_WEIGHTS))

    print(f"Loading SAM-Med2D on {DEVICE} ...")
    import argparse as ap

    sys.path.insert(0, str(SAM_SRC))
    from segment_anything import sam_model_registry
    from segment_anything.predictor_sammed import SammedPredictor

    args = ap.Namespace(
        image_size=256,
        sam_checkpoint=str(SAM_CHECKPOINT),
        encoder_adapter=True,
    )
    model = sam_model_registry["vit_b"](args)
    model.eval()
    model.to(DEVICE)
    _resources["predictor"] = SammedPredictor(model)
    print("All models loaded.")


class Segment(BaseModel):
    ann_id: int
    bbox: List[int]
    iou_score: float
    mask_b64: str


class AnalyzeResponse(BaseModel):
    segments: List[Segment]
    prob_fracture: float
    predicted_fracture: bool


class AnalyzeUrlRequest(BaseModel):
    image_url: str


def _run_inference(img: Image.Image, filename: str, yolo_conf: float = 0.25) -> AnalyzeResponse:
    detector = _resources["detector"]
    predictor = _resources["predictor"]
    classifier = _resources["classifier"]

    classification = classifier.predict(img, image_id=filename)
    prob_fracture = classification.prob_fracture
    predicted = classification.predicted_fracture

    img_np = np.array(img.convert("RGB"))
    segments: list[Segment] = []

    if predicted:
        yolo_res = detector.predict(img_np, conf=yolo_conf, verbose=False)[0]
        boxes = yolo_res.boxes.xyxy.cpu().numpy() if len(yolo_res.boxes) else []
        confs = yolo_res.boxes.conf.cpu().numpy() if len(yolo_res.boxes) else []

        if len(boxes):
            with torch.no_grad():
                predictor.set_image(img_np)
                for i, (box, _) in enumerate(zip(boxes, confs)):
                    x1, y1, x2, y2 = map(float, box[:4])
                    masks, scores, _ = predictor.predict(
                        box=np.array([x1, y1, x2, y2]),
                        multimask_output=True,
                    )
                    best = int(np.argmax(scores))
                    score = float(scores[best])
                    mask = masks[best].astype(np.uint8) * 255
                    buf = io.BytesIO()
                    Image.fromarray(mask).save(buf, format="PNG")
                    mask_b64 = base64.b64encode(buf.getvalue()).decode()
                    segments.append(
                        Segment(
                            ann_id=i,
                            bbox=[round(x1), round(y1), round(x2), round(y2)],
                            iou_score=round(score, 4),
                            mask_b64=mask_b64,
                        )
                    )

    return AnalyzeResponse(
        segments=segments,
        prob_fracture=round(prob_fracture, 4),
        predicted_fracture=predicted,
    )


@app.get("/health")
def health() -> dict:
    classifier = _resources.get("classifier")
    return {
        "status": "ok",
        "device": DEVICE,
        "threshold": classifier.threshold if classifier else (THRESHOLD or DEFAULT_THRESHOLD),
        "cached_embeddings": classifier.cache_size if classifier else 0,
        "classifier": CLF_PATH.name,
        "medsiglip_model_dir": str(MEDSIGLIP_MODEL_DIR),
        "real_time_classifier": True,
    }


@app.post("/analyze-url", response_model=AnalyzeResponse)
def analyze_url(req: AnalyzeUrlRequest) -> AnalyzeResponse:
    """Fetch image from URL and run the full classifier -> detector -> segmentor pipeline."""
    filename = Path(req.image_url).name
    try:
        resp = httpx.get(req.image_url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch image: {e}")

    try:
        img = Image.open(io.BytesIO(resp.content))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image: {e}")

    return _run_inference(img, filename)
