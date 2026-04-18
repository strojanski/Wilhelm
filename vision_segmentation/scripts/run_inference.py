"""Run SAM-Med2D zero-shot inference on FracAtlas fractured images using COCO bounding boxes."""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from tqdm import tqdm

CHECKPOINT = Path("../SAM-Med2D/sam-med2d_b.pth")
DATA_DIR = Path("../data/FracAtlas")
COCO_JSON = DATA_DIR / "Annotations/COCO JSON/COCO_fracture_masks.json"
IMG_DIR = DATA_DIR / "images/Fractured"
PRED_DIR = DATA_DIR / "predictions"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


def check_setup():
    if not CHECKPOINT.exists():
        sys.exit(
            "ERROR: SAM-Med2D checkpoint not found.\n\n"
            "Setup steps:\n"
            "  1. git clone https://github.com/OpenGVLab/SAM-Med2D\n"
            "  2. cd SAM-Med2D && pip install -e . && cd ..\n"
            "  3. Download sam-med2d_b.pth from https://github.com/OpenGVLab/SAM-Med2D/releases\n"
            "     and place it at SAM-Med2D/sam-med2d_b.pth\n"
        )
    if not COCO_JSON.exists():
        sys.exit(f"ERROR: COCO annotations not found at {COCO_JSON}")


def load_model():
    try:
        from segment_anything import sam_model_registry
        from segment_anything.predictor_sammed import SammedPredictor
    except ImportError:
        sys.exit("ERROR: segment_anything not importable. Check SAM-Med2D setup.")

    args = argparse.Namespace(
        image_size=256,
        sam_checkpoint=str(CHECKPOINT),
        encoder_adapter=True,
    )

    print(f"Loading SAM-Med2D from {CHECKPOINT} on {DEVICE} ...")
    model = sam_model_registry["vit_b"](args)
    model.eval()
    model.to(DEVICE)
    print("Model loaded.\n")
    return SammedPredictor(model)


def load_annotations():
    """Return {image_stem: {"file_name": ..., "bboxes": [[x1,y1,x2,y2], ...]}}"""
    with open(COCO_JSON) as f:
        coco = json.load(f)

    id_to_meta = {img["id"]: img for img in coco["images"]}

    entries = {}
    for ann in coco["annotations"]:
        img = id_to_meta[ann["image_id"]]
        stem = Path(img["file_name"]).stem
        x, y, w, h = ann["bbox"]
        bbox_xyxy = [x, y, x + w, y + h]
        if stem not in entries:
            entries[stem] = {"file_name": img["file_name"], "bboxes": []}
        entries[stem]["bboxes"].append(bbox_xyxy)

    return entries


def union_bbox(bboxes):
    """Merge multiple [x1,y1,x2,y2] boxes into one enclosing box."""
    arr = np.array(bboxes)
    return [arr[:, 0].min(), arr[:, 1].min(), arr[:, 2].max(), arr[:, 3].max()]


def main():
    check_setup()
    predictor = load_model()
    annotations = load_annotations()
    PRED_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Running inference on {len(annotations)} fractured images ...\n")
    skipped = 0

    for stem, meta in tqdm(annotations.items(), unit="img"):
        pred_path = PRED_DIR / f"{stem}.png"
        if pred_path.exists():
            skipped += 1
            continue

        img_path = IMG_DIR / meta["file_name"]
        if not img_path.exists():
            print(f"  WARNING: image not found: {img_path}")
            continue

        img = np.array(Image.open(img_path).convert("RGB"))
        bbox = np.array(union_bbox(meta["bboxes"]), dtype=float)

        with torch.no_grad():
            predictor.set_image(img)
            masks, _, _ = predictor.predict(box=bbox, multimask_output=False)

        Image.fromarray((masks[0].astype(np.uint8) * 255)).save(pred_path)

    new_preds = len(annotations) - skipped
    print(f"\nDone. New predictions: {new_preds} | Skipped (exist): {skipped}")
    print(f"Saved to {PRED_DIR.resolve()}")


if __name__ == "__main__":
    main()
