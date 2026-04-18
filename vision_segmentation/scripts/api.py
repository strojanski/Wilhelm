"""
FastAPI backend for RadiAI — privacy-preserving X-ray triage.
Loads SAM-Med2D once at startup; all inference runs on Flare confidential compute.

Run from the scripts/ directory:
    uvicorn api:app --reload --port 8000
"""

import argparse
import base64
import io
import json
import sys
from pathlib import Path
from typing import Optional

# Add SAM-Med2D to path so `segment_anything` can be imported without install
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "SAM-Med2D"))

import cv2
import httpx
import numpy as np
import pandas as pd
import torch
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
from pydantic import BaseModel

# ── Config ─────────────────────────────────────────────────────────────────────

DATA_DIR   = Path("../data/FracAtlas")
CHECKPOINT = Path("../SAM-Med2D/sam-med2d_b.pth")
COCO_JSON  = DATA_DIR / "Annotations/COCO JSON/COCO_fracture_masks.json"
META_CSV   = DATA_DIR / "dataset.csv"
IMG_DIRS   = [DATA_DIR / "images/Fractured", DATA_DIR / "images/Non_fractured"]
DEVICE     = "cuda" if torch.cuda.is_available() else "cpu"

PROBE_COLOR = [60, 160, 255]   # blue overlay for manual bbox probes

# ── App & state ────────────────────────────────────────────────────────────────

app = FastAPI(title="RadiAI API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

predictor  = None
meta_df    = None
coco_index = None   # stem → {H, W, anns:[{id, bbox, segmentation}]}


@app.on_event("startup")
def load_resources():
    global predictor, meta_df, coco_index

    from segment_anything import sam_model_registry
    from segment_anything.predictor_sammed import SammedPredictor

    args = argparse.Namespace(
        image_size=256,
        sam_checkpoint=str(CHECKPOINT),
        encoder_adapter=True,
    )
    model = sam_model_registry["vit_b"](args)
    model.eval()
    model.to(DEVICE)
    predictor = SammedPredictor(model)
    print(f"SAM-Med2D loaded on {DEVICE}")

    if META_CSV.exists():
        meta_df = pd.read_csv(META_CSV, index_col="image_id")

    if COCO_JSON.exists():
        with open(COCO_JSON) as f:
            coco = json.load(f)
        id_to_meta = {img["id"]: img for img in coco["images"]}
        coco_index = {}
        for ann in coco["annotations"]:
            m = id_to_meta[ann["image_id"]]
            stem = Path(m["file_name"]).stem
            x, y, w, h = ann["bbox"]
            coco_index.setdefault(stem, {"H": m["height"], "W": m["width"], "anns": []})
            coco_index[stem]["anns"].append({
                "id": ann["id"],
                "bbox": [x, y, x + w, y + h],
                "segmentation": ann["segmentation"],
            })

# ── Utility ────────────────────────────────────────────────────────────────────

def find_image(stem: str) -> Optional[Path]:
    for d in IMG_DIRS:
        for ext in [".jpg", ".jpeg", ".png"]:
            p = d / f"{stem}{ext}"
            if p.exists():
                return p
    return None


def to_b64(arr: np.ndarray, fmt="PNG") -> str:
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format=fmt)
    return base64.b64encode(buf.getvalue()).decode()


def mask_to_b64(mask: np.ndarray) -> str:
    return to_b64((mask * 255).astype(np.uint8))


def build_overlay(img: np.ndarray, mask: np.ndarray, color: list,
                  alpha: float = 0.45) -> np.ndarray:
    out = img.copy()
    region = mask.astype(bool)
    out[region] = (alpha * np.array(color) + (1 - alpha) * img[region]).astype(np.uint8)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(out, contours, -1, tuple(color), max(2, img.shape[0] // 400))
    return out


def get_meta(stem: str) -> dict:
    if meta_df is None:
        return {}
    key = f"{stem}.jpg"
    return meta_df.loc[key].to_dict() if key in meta_df.index else {}


def crop_b64_from_mask(img: np.ndarray, mask: np.ndarray, pad: int = 20) -> Optional[str]:
    ys, xs = np.where(mask)
    if not len(xs):
        return None
    H, W = img.shape[:2]
    x1 = max(0, int(xs.min()) - pad);  y1 = max(0, int(ys.min()) - pad)
    x2 = min(W, int(xs.max()) + pad);  y2 = min(H, int(ys.max()) + pad)
    return to_b64(img[y1:y2, x1:x2], fmt="JPEG")


def build_report_prompt(image_id: str, patient: dict, detections: list,
                        triage: Optional[dict] = None) -> str:
    meta       = get_meta(image_id)
    body_parts = [p for p in ["hand", "leg", "hip", "shoulder"] if meta.get(p, 0)]
    views      = [v for v in ["frontal", "lateral", "oblique"]  if meta.get(v, 0)]

    age        = patient.get("age", "unknown")
    sex        = patient.get("sex", "unknown")
    complaint  = patient.get("complaint", "")
    comorbid   = ", ".join(patient.get("comorbidities", [])) or "none"
    meds       = ", ".join(patient.get("medications", [])) or "none"

    part_str   = ", ".join(body_parts) if body_parts else "unknown region"
    view_str   = ", ".join(views) if views else "unknown view"
    n_det      = len(detections)
    confs      = [round(d.get("iou_score", 0) * 100, 1) for d in detections]
    conf_str   = ", ".join(f"{c}%" for c in confs) if confs else "N/A"

    urgency    = triage.get("urgency", "unknown").upper() if triage else "UNKNOWN"

    return (
        f"You are a radiology AI assistant. Analyse the following clinical case.\n\n"
        f"PATIENT: {age}-year-old {sex}. Chief complaint: {complaint or 'not specified'}.\n"
        f"Comorbidities: {comorbid}. Current medications: {meds}.\n\n"
        f"IMAGING: {part_str} X-ray, {view_str} view.\n"
        f"AI triage: {urgency}.\n"
        f"SAM-Med2D detected {n_det} region(s) of interest (confidence: {conf_str}).\n"
        f"{'Surgical hardware visible.' if meta.get('hardware', 0) else ''}\n\n"
        f"Provide a structured radiology report with sections:\n"
        f"1. FINDINGS — describe each detected region, location, and appearance.\n"
        f"2. IMPRESSION — synthesise the most likely diagnosis.\n"
        f"3. RECOMMENDATION — suggest next clinical steps.\n"
        f"Consider the patient's comorbidities and medications in your assessment."
    )


def build_stub_report(image_id: str, patient: dict, detections: list,
                      triage: Optional[dict] = None) -> dict:
    meta       = get_meta(image_id)
    body_parts = [p for p in ["hand", "leg", "hip", "shoulder"] if meta.get(p, 0)]
    part_str   = " / ".join(body_parts) if body_parts else "bone"
    n          = len(detections)
    confs      = [round(d.get("iou_score", 0) * 100) for d in detections]
    avg_conf   = round(sum(confs) / len(confs)) if confs else 0

    comorbid   = patient.get("comorbidities", [])
    meds       = patient.get("medications", [])
    age        = patient.get("age", "")

    osteo_note = ""
    if "Osteoporosis" in comorbid:
        osteo_note = " Reduced bone density consistent with known osteoporosis increases fracture risk."
    steroid_note = ""
    if "Corticosteroids" in meds:
        steroid_note = " Long-term corticosteroid use may contribute to bone fragility."

    findings = (
        f"SAM-Med2D identified {n} region{'s' if n != 1 else ''} of interest "
        f"in this {part_str} radiograph (mean model confidence {avg_conf}%)."
        f"{osteo_note}{steroid_note}"
        + (" Surgical hardware is present." if meta.get("hardware", 0) else "")
    )

    urgency = triage.get("urgency", "unknown") if triage else "unknown"
    impression = (
        f"Findings are consistent with {'acute ' if urgency == 'high' else ''}"
        f"{part_str} fracture.{' Urgent clinical correlation recommended.' if urgency == 'high' else ''}"
    )

    age_note = f" given patient age ({age})" if age else ""
    rec = (
        f"Urgent orthopaedic review recommended{age_note}. "
        if urgency == "high" else
        f"Clinical correlation with patient symptoms advised. "
    )
    if "Osteoporosis" in comorbid:
        rec += "Consider bone density assessment and fracture prevention protocol."

    patient_ctx_parts = []
    if age:
        patient_ctx_parts.append(f"Age {age}")
    if patient.get("sex"):
        patient_ctx_parts.append(patient["sex"])
    if comorbid:
        patient_ctx_parts.append("Comorbidities: " + ", ".join(comorbid))
    if meds:
        patient_ctx_parts.append("Medications: " + ", ".join(meds))
    if patient.get("complaint"):
        patient_ctx_parts.append("Complaint: " + patient["complaint"])

    return {
        "findings":        findings,
        "impression":      impression,
        "recommendation":  rec,
        "patient_context": " · ".join(patient_ctx_parts) or "No history provided",
        "generated_by":    "stub",   # change to "gemma" when wired
    }


# ── Request / Response models ──────────────────────────────────────────────────

class ClassifyRequest(BaseModel):
    image_id: str


class ProbeRequest(BaseModel):
    image_id: str
    bbox: list[float]           # [x1, y1, x2, y2] in original image coords
    anomaly_type: str = "custom"


class ProbeResult(BaseModel):
    mask_b64: str
    all_masks_b64: list[str]
    iou_scores: list[float]
    best_index: int
    overlay_b64: str
    crop_b64: Optional[str]


class PresegmentResult(BaseModel):
    segments: list[dict]
    overlay_b64: str


class ReportRequest(BaseModel):
    image_id: str
    patient: dict               # {age, sex, complaint, comorbidities, medications}
    detections: list[dict]      # segments from presegment
    triage: Optional[dict] = None


class AnalyzeUrlRequest(BaseModel):
    image_url: str              # full URL to the X-ray image (served by Wilhelm backend)


class SegmentFromUrlRequest(BaseModel):
    image_url: str
    bbox: list[float]           # [x1, y1, x2, y2]


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "device": DEVICE, "model_loaded": predictor is not None}


@app.get("/images")
def list_images():
    stems = []
    for d in IMG_DIRS:
        if d.exists():
            stems.extend(p.stem for p in sorted(d.glob("*.jpg")))
    return {"image_ids": stems, "count": len(stems)}


@app.get("/image/{image_id}")
def get_image(image_id: str):
    img_path = find_image(image_id)
    if not img_path:
        raise HTTPException(404, f"Image '{image_id}' not found")

    img  = np.array(Image.open(img_path).convert("RGB"))
    meta = get_meta(image_id)
    body_parts = [p for p in ["hand", "leg", "hip", "shoulder"] if meta.get(p, 0)]
    views      = [v for v in ["frontal", "lateral", "oblique"]  if meta.get(v, 0)]

    return {
        "image_b64":       to_b64(img, fmt="JPEG"),
        "width":           img.shape[1],
        "height":          img.shape[0],
        "body_part":       body_parts,
        "view":            views,
        "hardware_present": bool(meta.get("hardware", 0)),
        "fractured":       bool(meta.get("fractured", image_id in (coco_index or {}))),
    }


@app.post("/classify")
def classify(req: ClassifyRequest):
    """
    Triage stub: is this scan normal? How urgent?
    Replace the body with a real classifier forward pass when the model is ready.
    The classifier should be loaded at startup (global, like `predictor`) and run
    a forward pass on the full image here.
    """
    # ── STUB ── replace below with: result = classifier_model(load_img(req.image_id))
    meta      = get_meta(req.image_id)
    fractured = bool(meta.get("fractured", req.image_id in (coco_index or {})))
    body_parts = [p for p in ["hand", "leg", "hip", "shoulder"] if meta.get(p, 0)]
    return {
        "normal":       not fractured,
        "urgency":      "high" if fractured else "low",
        "anomaly_hint": "Possible fracture detected" if fractured else "No anomaly detected",
        "confidence":   0.91 if fractured else 0.88,
        "body_part":    body_parts,
    }


@app.post("/segment", response_model=ProbeResult)
def segment(req: ProbeRequest):
    """
    Probe a user-drawn bounding box. One call per drawn region — no per-click calls.
    """
    if not predictor:
        raise HTTPException(503, "Model not loaded")

    img_path = find_image(req.image_id)
    if not img_path:
        raise HTTPException(404, f"Image '{req.image_id}' not found")

    img = np.array(Image.open(img_path).convert("RGB"))

    with torch.no_grad():
        predictor.set_image(img)
        masks, iou_scores, _ = predictor.predict(
            box=np.array(req.bbox, dtype=float),
            multimask_output=True,
        )

    best_idx  = int(np.argmax(iou_scores))
    best_mask = masks[best_idx].astype(np.uint8)

    return ProbeResult(
        mask_b64=mask_to_b64(best_mask),
        all_masks_b64=[mask_to_b64(m.astype(np.uint8)) for m in masks],
        iou_scores=[round(float(s), 4) for s in iou_scores],
        best_index=best_idx,
        overlay_b64=to_b64(build_overlay(img, best_mask, PROBE_COLOR), fmt="JPEG"),
        crop_b64=crop_b64_from_mask(img, best_mask),
    )


def grid_detect(img: np.ndarray, grid: int = 8,
                iou_thresh: float = 0.7,
                nms_thresh: float = 0.7,
                min_area: float = 0.002,
                max_area: float = 0.40) -> list[dict]:
    """
    Zero-shot automatic detection via dense point grid.
    Image encoder runs once; each grid point queries the decoder only.
    """
    H, W = img.shape[:2]
    xs = [int(W * (i + 0.5) / grid) for i in range(grid)]
    ys = [int(H * (i + 0.5) / grid) for i in range(grid)]
    candidates: list[tuple[np.ndarray, float]] = []

    with torch.no_grad():
        predictor.set_image(img)
        for cy in ys:
            for cx in xs:
                masks, scores, _ = predictor.predict(
                    point_coords=np.array([[cx, cy]], dtype=float),
                    point_labels=np.array([1]),
                    multimask_output=True,
                )
                best  = int(np.argmax(scores))
                score = float(scores[best])
                if score < iou_thresh:
                    continue
                mask = masks[best].astype(np.uint8)
                frac = mask.sum() / (H * W)
                if not (min_area <= frac <= max_area):
                    continue
                candidates.append((mask, score))

    candidates.sort(key=lambda t: -t[1])
    kept: list[tuple[np.ndarray, float]] = []
    for mask, score in candidates:
        suppress = any(
            (mask & km).sum() / max((mask | km).sum(), 1) > nms_thresh
            for km, _ in kept
        )
        if not suppress:
            kept.append((mask, score))

    return [{"mask": m, "score": s} for m, s in kept]


@app.get("/presegment/{image_id}", response_model=PresegmentResult)
def presegment(image_id: str):
    """
    Zero-shot fracture detection — no GT prompts used.
    SAM-Med2D encoder runs once; grid points query the decoder; greedy NMS deduplicates.
    """
    if not predictor:
        raise HTTPException(503, "Model not loaded")

    img_path = find_image(image_id)
    if not img_path:
        raise HTTPException(404, f"Image '{image_id}' not found")

    img   = np.array(Image.open(img_path).convert("RGB"))
    H, W  = img.shape[:2]
    color = [255, 60, 60]   # red — AI prediction

    detections = grid_detect(img)
    if not detections:
        raise HTTPException(404, f"No high-confidence regions detected in '{image_id}'")

    composite = img.copy()
    segments  = []
    for i, det in enumerate(detections):
        mask = det["mask"]
        composite = build_overlay(composite, mask, color, alpha=0.35)
        ys, xs = np.where(mask)
        bbox = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())] if len(xs) else [0, 0, W, H]
        segments.append({
            "ann_id":    i,
            "bbox":      bbox,
            "mask_b64":  mask_to_b64(mask),
            "iou_score": round(det["score"], 4),
            "crop_b64":  crop_b64_from_mask(img, mask),
        })

    return PresegmentResult(
        segments=segments,
        overlay_b64=to_b64(composite, fmt="JPEG"),
    )


@app.get("/gt_overlay/{image_id}")
def get_gt_overlay(image_id: str):
    """Render COCO polygon GT masks as green overlay + raw mask for IoU."""
    img_path = find_image(image_id)
    if not img_path:
        raise HTTPException(404, f"Image '{image_id}' not found")
    if not coco_index or image_id not in coco_index:
        raise HTTPException(404, f"No GT annotations for '{image_id}'")

    img = np.array(Image.open(img_path).convert("RGB"))
    H, W = img.shape[:2]

    full_mask  = np.zeros((H, W), dtype=np.uint8)
    per_region = []

    for ann in coco_index[image_id]["anns"]:
        region_mask = np.zeros((H, W), dtype=np.uint8)
        for poly in ann["segmentation"]:
            pts = np.array(poly, dtype=np.int32).reshape(-1, 2)
            cv2.fillPoly(region_mask, [pts], 1)
            cv2.fillPoly(full_mask,   [pts], 1)
        per_region.append({
            "ann_id":   ann["id"],
            "bbox":     ann["bbox"],
            "mask_b64": mask_to_b64(region_mask),
        })

    overlay = build_overlay(img, full_mask, [60, 220, 100], alpha=0.45)
    return {
        "overlay_b64":  to_b64(overlay, fmt="JPEG"),
        "mask_b64":     mask_to_b64(full_mask),
        "regions":      per_region,
        "region_count": len(per_region),
    }


def _load_image_from_url(url: str) -> np.ndarray:
    """Fetch an image from a URL and return it as an RGB numpy array."""
    try:
        resp = httpx.get(url, timeout=15)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        raise HTTPException(502, f"Failed to fetch image from Wilhelm: {e}")
    img = np.array(Image.open(io.BytesIO(resp.content)).convert("RGB"))
    return img


@app.post("/analyze-url", response_model=PresegmentResult)
def analyze_url(req: AnalyzeUrlRequest):
    """
    Zero-shot fracture detection on an image served by Wilhelm backend.
    The Spring backend calls this with the X-ray download URL; the model runs
    inference and returns all detected fracture regions with overlays.
    """
    if not predictor:
        raise HTTPException(503, "Model not loaded")

    img = _load_image_from_url(req.image_url)
    H, W = img.shape[:2]
    color = [255, 60, 60]

    detections = grid_detect(img)
    if not detections:
        return PresegmentResult(segments=[], overlay_b64=to_b64(img, fmt="JPEG"))

    composite = img.copy()
    segments = []
    for i, det in enumerate(detections):
        mask = det["mask"]
        composite = build_overlay(composite, mask, color, alpha=0.35)
        ys, xs = np.where(mask)
        bbox = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())] if len(xs) else [0, 0, W, H]
        segments.append({
            "ann_id":    i,
            "bbox":      bbox,
            "mask_b64":  mask_to_b64(mask),
            "iou_score": round(det["score"], 4),
            "crop_b64":  crop_b64_from_mask(img, mask),
        })

    return PresegmentResult(
        segments=segments,
        overlay_b64=to_b64(composite, fmt="JPEG"),
    )


@app.post("/segment-url", response_model=ProbeResult)
def segment_url(req: SegmentFromUrlRequest):
    """
    Segment a user-drawn bounding box on an image fetched by URL.
    Used by the correction UI when a user draws a new region.
    """
    if not predictor:
        raise HTTPException(503, "Model not loaded")

    img = _load_image_from_url(req.image_url)

    with torch.no_grad():
        predictor.set_image(img)
        masks, iou_scores, _ = predictor.predict(
            box=np.array(req.bbox, dtype=float),
            multimask_output=True,
        )

    best_idx = int(np.argmax(iou_scores))
    best_mask = masks[best_idx].astype(np.uint8)

    return ProbeResult(
        mask_b64=mask_to_b64(best_mask),
        all_masks_b64=[mask_to_b64(m.astype(np.uint8)) for m in masks],
        iou_scores=[round(float(s), 4) for s in iou_scores],
        best_index=best_idx,
        overlay_b64=to_b64(build_overlay(img, best_mask, PROBE_COLOR), fmt="JPEG"),
        crop_b64=crop_b64_from_mask(img, best_mask),
    )


@app.post("/report")
def generate_report(req: ReportRequest):
    """
    Generate a structured clinical report from patient history + AI detections.
    Currently returns a structured stub.
    To wire Gemma: replace build_stub_report() with a call to the Gemma API,
    passing build_report_prompt() as the text prompt and the first detection's
    crop_b64 as the image.
    """
    prompt = build_report_prompt(req.image_id, req.patient, req.detections, req.triage)
    report = build_stub_report(req.image_id, req.patient, req.detections, req.triage)
    return {"report": report, "prompt": prompt}
