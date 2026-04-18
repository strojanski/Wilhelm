"""
FastAPI classifier service.

Run from vision_classifier/scripts/:
    uvicorn api:app --reload --port 8001
"""

import base64
import io
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel

# ── Config ─────────────────────────────────────────────────────────────────────

CLF_PATH  = Path(os.getenv("CLF_PATH", str(Path(__file__).parent.parent / "fracture_classifier_v3_0.91auc.pkl")))
MODEL_DIR = Path(os.getenv("MODEL_DIR", str(Path(__file__).parent.parent / "medsiglip-448")))

# Calibrated to ≥90% recall on the FracAtlas test set.
SEGMENTATION_THRESHOLD = 0.0853

# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(title="Fracture Classifier API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def load_resources():
    from model import load_model
    load_model(model_dir=MODEL_DIR, clf_path=CLF_PATH)


# ── Helpers ────────────────────────────────────────────────────────────────────

def decode_image(image_b64: str) -> Image.Image:
    if "," in image_b64 and image_b64.lstrip().startswith("data:"):
        image_b64 = image_b64.split(",", 1)[1]
    try:
        return Image.open(io.BytesIO(base64.b64decode(image_b64)))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image: {e}")


def encode_image(img: Image.Image, fmt="JPEG") -> str:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format=fmt)
    return base64.b64encode(buf.getvalue()).decode()


def draw_overlay(img: Image.Image, prob: float, above_threshold: bool,
                 true_label: Optional[str] = None) -> Image.Image:
    out  = img.convert("RGB").copy()
    draw = ImageDraw.Draw(out)
    W, H = out.size

    color  = (220, 50, 50) if above_threshold else (50, 180, 50)
    border = max(4, H // 80)
    draw.rectangle([0, 0, W - 1, H - 1], outline=color, width=border)

    label   = f"FRACTURE PROBABILITY: {prob * 100:.1f}%"
    padding = 8
    font_sz = max(16, W // 22)
    try:
        font = ImageFont.truetype("arial.ttf", font_sz)
    except Exception:
        font = ImageFont.load_default()

    bbox   = draw.textbbox((0, 0), label, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.rectangle([padding - 2, padding - 2, padding + tw + 2, padding + th + 2], fill=color)
    draw.text((padding, padding), label, fill=(255, 255, 255), font=font)

    if true_label:
        gt_text    = f"Ground truth: {true_label}"
        gt_bbox    = draw.textbbox((0, 0), gt_text, font=font)
        gt_w, gt_h = gt_bbox[2] - gt_bbox[0], gt_bbox[3] - gt_bbox[1]
        y2 = padding + th + 4
        draw.rectangle([padding - 2, y2 - 2, padding + gt_w + 2, y2 + gt_h + 2], fill=(30, 30, 30))
        draw.text((padding, y2), gt_text, fill=(220, 220, 220), font=font)

    return out


# ── Schemas ────────────────────────────────────────────────────────────────────

class ClassifyRequest(BaseModel):
    image_b64:  str
    image_id:   Optional[str] = None   # e.g. "IMG0000019.jpg" — uses cached embedding, skips MedSigLIP
    true_label: Optional[str] = None   # for overlay only


class ClassifyResponse(BaseModel):
    prob_fractured:       float   # 0–1
    send_to_segmentation: bool    # True when prob >= 0.0853
    overlay_b64:          str     # JPEG with probability drawn on it


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {
        "status":                 "ok",
        "segmentation_threshold": SEGMENTATION_THRESHOLD,
        "classifier":             CLF_PATH.name,
    }


@app.post("/classify", response_model=ClassifyResponse)
def classify(req: ClassifyRequest):
    from model import predict
    img  = decode_image(req.image_b64)
    prob = predict(img, image_id=req.image_id)

    above = prob >= SEGMENTATION_THRESHOLD
    return ClassifyResponse(
        prob_fractured       = round(prob, 4),
        send_to_segmentation = above,
        overlay_b64          = encode_image(draw_overlay(img, prob, above, req.true_label)),
    )
