"""
FastAPI classifier service — mirrors vision_segmentation/scripts/api.py structure.

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

MODEL_DIR = Path(os.getenv("MODEL_DIR", str(Path(__file__).parent.parent / "medsiglip-448")))
CLF_PATH  = Path(os.getenv("CLF_PATH",  str(Path(__file__).parent.parent / "fracture_classifier_v3_0.91auc.pkl")))

# Calibrated to ≥90% recall on the FracAtlas test set.
# Controls whether the backend should forward this image to the segmentation service.
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
    print(f"Segmentation threshold: {SEGMENTATION_THRESHOLD}")


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


def draw_overlay(img: Image.Image, prob: float, send_to_segmentation: bool, true_label: Optional[str] = None) -> Image.Image:
    """Draw probability on the image. Border is red when above segmentation threshold, green otherwise."""
    out   = img.convert("RGB").copy()
    draw  = ImageDraw.Draw(out)
    W, H  = out.size

    color = (220, 50, 50) if send_to_segmentation else (50, 180, 50)

    border = max(4, H // 80)
    draw.rectangle([0, 0, W - 1, H - 1], outline=color, width=border)

    label   = f"{prob*100:.1f}%"
    font_sz = max(16, H // 20)
    try:
        font = ImageFont.truetype("arial.ttf", font_sz)
    except Exception:
        font = ImageFont.load_default()

    padding = font_sz // 2
    bbox    = draw.textbbox((0, 0), label, font=font)
    tw, th  = bbox[2] - bbox[0], bbox[3] - bbox[1]

    draw.rectangle([padding - 4, padding - 4, padding + tw + 4, padding + th + 4], fill=color)
    draw.text((padding, padding), label, fill=(255, 255, 255), font=font)

    if true_label:
        gt_text = f"GT: {true_label}"
        draw.rectangle([padding - 4, padding + th + 8, padding + tw + 4, padding + 2 * th + 12],
                       fill=(30, 30, 30))
        draw.text((padding, padding + th + 8), gt_text, fill=(220, 220, 220), font=font)

    return out


# ── Schemas ────────────────────────────────────────────────────────────────────

class ClassifyRequest(BaseModel):
    image_b64:  str
    true_label: Optional[str] = None   # "fractured" | "normal" — optional, for overlay only


class ClassifyResponse(BaseModel):
    prob_fractured:        float   # raw probability of fracture (0–1)
    send_to_segmentation:  bool    # True when prob >= 0.0853 (≥90% recall threshold)
    overlay_b64:           str     # JPEG with probability drawn on it (base64)


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {
        "status":                 "ok",
        "segmentation_threshold": SEGMENTATION_THRESHOLD,
        "classifier":             CLF_PATH.name,
        "model":                  MODEL_DIR.name,
    }


@app.post("/classify", response_model=ClassifyResponse)
def classify(req: ClassifyRequest):
    from model import predict
    img  = decode_image(req.image_b64)
    prob = predict(img)

    send_to_segmentation = prob >= SEGMENTATION_THRESHOLD
    overlay = draw_overlay(img, prob, send_to_segmentation, true_label=req.true_label)

    return ClassifyResponse(
        prob_fractured       = round(prob, 4),
        send_to_segmentation = send_to_segmentation,
        overlay_b64          = encode_image(overlay),
    )
