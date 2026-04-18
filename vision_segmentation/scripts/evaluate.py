"""Evaluate SAM-Med2D predictions against FracAtlas ground-truth fracture masks."""

import csv
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from tqdm import tqdm

DATA_DIR = Path("../data/FracAtlas")
COCO_JSON = DATA_DIR / "Annotations/COCO JSON/COCO_fracture_masks.json"
PRED_DIR = DATA_DIR / "predictions"
RESULTS_CSV = DATA_DIR / "results.csv"
THRESHOLD = 127


def load_gt_masks():
    """Render COCO polygon segmentations to binary masks per image stem."""
    with open(COCO_JSON) as f:
        coco = json.load(f)

    id_to_meta = {img["id"]: img for img in coco["images"]}
    gt_masks = {}

    for ann in coco["annotations"]:
        img_meta = id_to_meta[ann["image_id"]]
        stem = Path(img_meta["file_name"]).stem
        H, W = img_meta["height"], img_meta["width"]

        if stem not in gt_masks:
            gt_masks[stem] = np.zeros((H, W), dtype=np.uint8)

        for poly in ann["segmentation"]:
            pts = np.array(poly, dtype=np.int32).reshape(-1, 2)
            cv2.fillPoly(gt_masks[stem], [pts], 1)

    return gt_masks


def iou(pred, gt):
    intersection = (pred & gt).sum()
    union = (pred | gt).sum()
    return float(intersection) / float(union) if union > 0 else float("nan")


def dice(pred, gt):
    intersection = (pred & gt).sum()
    denom = pred.sum() + gt.sum()
    return float(2 * intersection) / float(denom) if denom > 0 else float("nan")


def main():
    if not COCO_JSON.exists():
        sys.exit(f"ERROR: {COCO_JSON} not found.")
    if not PRED_DIR.exists():
        sys.exit("ERROR: No predictions directory. Run run_inference.py first.")

    print("Loading ground-truth masks ...")
    gt_masks = load_gt_masks()

    results = []
    for stem, gt in tqdm(gt_masks.items(), desc="Evaluating", unit="img"):
        pred_path = PRED_DIR / f"{stem}.png"
        if not pred_path.exists():
            continue

        pred = (np.array(Image.open(pred_path).convert("L")) > THRESHOLD).astype(np.uint8)

        if pred.shape != gt.shape:
            pred = cv2.resize(pred, (gt.shape[1], gt.shape[0]), interpolation=cv2.INTER_NEAREST)

        results.append({"id": stem, "iou": iou(pred, gt), "dice": dice(pred, gt)})

    if not results:
        sys.exit("No matched (prediction, GT) pairs found. Run run_inference.py first.")

    ious = [r["iou"] for r in results if not np.isnan(r["iou"])]
    dices = [r["dice"] for r in results if not np.isnan(r["dice"])]

    print(f"\n{'='*42}")
    print(f"  Evaluated : {len(results)} images")
    print(f"  Mean IoU  : {np.mean(ious):.4f}  (std {np.std(ious):.4f})")
    print(f"  Mean Dice : {np.mean(dices):.4f}  (std {np.std(dices):.4f})")
    print(f"  IoU  range: [{np.min(ious):.4f}, {np.max(ious):.4f}]")
    print(f"  Dice range: [{np.min(dices):.4f}, {np.max(dices):.4f}]")
    print(f"{'='*42}\n")

    with open(RESULTS_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "iou", "dice"])
        writer.writeheader()
        writer.writerows(results)
    print(f"Per-image results saved to {RESULTS_CSV.resolve()}")


if __name__ == "__main__":
    main()
