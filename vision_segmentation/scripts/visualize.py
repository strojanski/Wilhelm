"""Visualize SAM-Med2D predictions on FracAtlas X-rays with semantic injury annotations."""

import json
import sys
from pathlib import Path

import cv2
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image

DATA_DIR = Path("../data/FracAtlas")
COCO_JSON = DATA_DIR / "Annotations/COCO JSON/COCO_fracture_masks.json"
IMG_DIR = DATA_DIR / "images/Fractured"
PRED_DIR = DATA_DIR / "predictions"
META_CSV = DATA_DIR / "dataset.csv"
OUT_DIR = DATA_DIR / "visualizations"

MASK_COLOR = np.array([255, 60, 60], dtype=np.uint8)   # red overlay for prediction
GT_COLOR   = np.array([60, 255, 60], dtype=np.uint8)   # green overlay for ground truth
ALPHA = 0.45


def load_coco():
    with open(COCO_JSON) as f:
        coco = json.load(f)
    id_to_meta = {img["id"]: img for img in coco["images"]}

    annotations = {}  # stem → list of {bbox, segmentation}
    for ann in coco["annotations"]:
        meta = id_to_meta[ann["image_id"]]
        stem = Path(meta["file_name"]).stem
        H, W = meta["height"], meta["width"]
        annotations.setdefault(stem, {"H": H, "W": W, "anns": []})
        x, y, w, h = ann["bbox"]
        annotations[stem]["anns"].append({
            "bbox": [x, y, x + w, y + h],
            "segmentation": ann["segmentation"],
        })
    return annotations


def render_gt_mask(anns_info):
    H, W = anns_info["H"], anns_info["W"]
    mask = np.zeros((H, W), dtype=np.uint8)
    for ann in anns_info["anns"]:
        for poly in ann["segmentation"]:
            pts = np.array(poly, dtype=np.int32).reshape(-1, 2)
            cv2.fillPoly(mask, [pts], 1)
    return mask


def overlay_mask(img_rgb, mask, color, alpha):
    out = img_rgb.copy()
    region = mask.astype(bool)
    out[region] = (alpha * color + (1 - alpha) * img_rgb[region]).astype(np.uint8)
    return out


def bbox_location(bbox, W, H):
    """Describe bounding box location in human terms."""
    x1, y1, x2, y2 = bbox
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    h_pos = "left" if cx < W / 2 else "right"
    v_pos = "upper" if cy < H / 2 else "lower"
    size_pct = 100 * (x2 - x1) * (y2 - y1) / (W * H)
    return f"{v_pos}-{h_pos}", size_pct


def build_description(stem, meta_row, anns_info):
    parts = []

    # Body part
    body_parts = [p for p in ["hand", "leg", "hip", "shoulder"] if meta_row.get(p, 0)]
    if meta_row.get("mixed", 0):
        body_parts = ["multiple regions"]
    part_str = " & ".join(body_parts).upper() if body_parts else "UNKNOWN REGION"
    parts.append(f"Body part: {part_str}")

    # View
    views = [v for v in ["frontal", "lateral", "oblique"] if meta_row.get(v, 0)]
    if views:
        parts.append(f"View: {', '.join(views)}")

    # Fracture count and locations
    n = int(meta_row.get("fracture_count", len(anns_info["anns"])))
    W, H = anns_info["W"], anns_info["H"]
    parts.append(f"Fractures detected: {n}")

    locations = []
    for ann in anns_info["anns"]:
        loc, size_pct = bbox_location(ann["bbox"], W, H)
        locations.append(f"{loc} ({size_pct:.1f}% of image)")
    if locations:
        parts.append("Locations: " + " | ".join(locations))

    # Hardware
    if meta_row.get("hardware", 0):
        parts.append("Note: Hardware/implant visible")

    # Multi-scan
    if meta_row.get("multiscan", 0):
        parts.append("Note: Multi-scan image")

    return "\n".join(parts)


def visualize_sample(stem, anns_info, meta_row, show_gt=True):
    img_path = IMG_DIR / f"{stem}.jpg"
    pred_path = PRED_DIR / f"{stem}.png"

    if not img_path.exists():
        return False

    img = np.array(Image.open(img_path).convert("RGB"))
    H, W = img.shape[:2]

    has_pred = pred_path.exists()
    has_gt = show_gt

    # Build overlaid image
    vis = img.copy()
    if has_gt:
        gt_mask = render_gt_mask(anns_info)
        if gt_mask.shape != (H, W):
            gt_mask = cv2.resize(gt_mask, (W, H), interpolation=cv2.INTER_NEAREST)
        vis = overlay_mask(vis, gt_mask, GT_COLOR, ALPHA)

    if has_pred:
        pred = (np.array(Image.open(pred_path).convert("L")) > 127).astype(np.uint8)
        if pred.shape != (H, W):
            pred = cv2.resize(pred, (W, H), interpolation=cv2.INTER_NEAREST)
        vis = overlay_mask(vis, pred, MASK_COLOR, ALPHA)

    # Draw bounding boxes
    for ann in anns_info["anns"]:
        x1, y1, x2, y2 = [int(v) for v in ann["bbox"]]
        cv2.rectangle(vis, (x1, y1), (x2, y2), (255, 200, 0), max(2, H // 500))

    description = build_description(stem, meta_row, anns_info)

    fig, axes = plt.subplots(1, 2, figsize=(16, 8))
    fig.patch.set_facecolor("#1a1a1a")

    # Left: original
    axes[0].imshow(img, cmap="gray" if img.ndim == 2 else None)
    axes[0].set_title("Original X-Ray", color="white", fontsize=13, pad=8)
    axes[0].axis("off")

    # Right: overlay
    axes[1].imshow(vis)
    axes[1].set_title("Segmentation Overlay", color="white", fontsize=13, pad=8)
    axes[1].axis("off")

    # Legend
    legend_handles = []
    if has_gt:
        legend_handles.append(mpatches.Patch(color=np.array(GT_COLOR) / 255, label="Ground truth"))
    if has_pred:
        legend_handles.append(mpatches.Patch(color=np.array(MASK_COLOR) / 255, label="SAM-Med2D prediction"))
    legend_handles.append(mpatches.Patch(color=(1, 0.78, 0), label="Fracture bbox"))
    if legend_handles:
        axes[1].legend(handles=legend_handles, loc="lower right",
                       facecolor="#333333", labelcolor="white", fontsize=9)

    # Semantic description box
    fig.text(0.5, 0.01, description, ha="center", va="bottom",
             fontsize=10, color="white",
             bbox=dict(boxstyle="round,pad=0.5", facecolor="#333333", alpha=0.8),
             family="monospace")

    plt.suptitle(stem, color="white", fontsize=11, y=0.99)
    plt.tight_layout(rect=[0, 0.12, 1, 0.99])

    out_path = OUT_DIR / f"{stem}.png"
    plt.savefig(out_path, dpi=120, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return True


def main():
    for path in [COCO_JSON, META_CSV, IMG_DIR]:
        if not path.exists():
            sys.exit(f"ERROR: {path} not found.")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading annotations and metadata ...")
    coco_anns = load_coco()
    meta_df = pd.read_csv(META_CSV, index_col="image_id")

    # Default: visualize first 20 fractured images (or pass --all to do all)
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="Visualize all fractured images")
    parser.add_argument("--n", type=int, default=20, help="Number of samples (default 20)")
    parser.add_argument("--no-gt", action="store_true", help="Hide ground-truth overlay")
    args = parser.parse_args()

    stems = list(coco_anns.keys())
    if not args.all:
        stems = stems[: args.n]

    print(f"Visualizing {len(stems)} images → {OUT_DIR}\n")
    saved = 0
    for stem in stems:
        image_id = f"{stem}.jpg"
        meta_row = meta_df.loc[image_id].to_dict() if image_id in meta_df.index else {}
        if visualize_sample(stem, coco_anns[stem], meta_row, show_gt=not args.no_gt):
            saved += 1

    print(f"Done. Saved {saved} visualizations to {OUT_DIR.resolve()}")


if __name__ == "__main__":
    main()
