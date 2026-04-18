"""
Full inference pipeline: MedSigLIP classifier → YOLOv8 detector → SAM-Med2D segmentor.

For every image in FracAtlas:
  1. Classifier (from embedding cache) → P(fracture)
  2. If predicted fractured: YOLO → bbox proposals → SAM → masks
  3. Write one JSON per image + summary CSV

Run from vision_inference/:
    python run_pipeline.py --limit 5        # quick test
    python run_pipeline.py                  # full dataset
    python run_pipeline.py --conf 0.3 --out my_output/
"""

import argparse
import csv
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from PIL import Image
from tqdm import tqdm

# ── Paths ──────────────────────────────────────────────────────────────────────

ROOT           = Path(__file__).parent.parent
CACHE_PATH     = ROOT / "vision_classifier/embedding_cache.pkl"
CLF_PATH       = ROOT / "vision_classifier/fracture_classifier_v3_0.91auc.pkl"
YOLO_WEIGHTS   = ROOT / "vision_segmentation/weights/best.pt"
SAM_CHECKPOINT = ROOT / "vision_segmentation/SAM-Med2D/sam-med2d_b.pth"
DATA_DIR       = ROOT / "vision_segmentation/data/FracAtlas"
SPLIT_DIR      = DATA_DIR / "Utilities/Fracture Split"
DATASET_CSV    = DATA_DIR / "dataset.csv"
IMG_DIRS       = [DATA_DIR / "images/Fractured", DATA_DIR / "images/Non_fractured"]

THRESHOLD = 0.0853   # classifier probability threshold (≥90% recall from training)
DEVICE    = "cuda" if torch.cuda.is_available() else "cpu"


# ── Loaders ───────────────────────────────────────────────────────────────────

def load_classifier():
    print(f"Loading embedding cache from {CACHE_PATH} …")
    with open(CACHE_PATH, "rb") as f:
        emb_cache = pickle.load(f)
    print(f"  {len(emb_cache)} embeddings loaded")

    print(f"Loading classifier from {CLF_PATH} …")
    try:
        import joblib
        clf = joblib.load(CLF_PATH)
    except Exception:
        with open(CLF_PATH, "rb") as f:
            clf = pickle.load(f)
    return emb_cache, clf


def load_detector():
    from ultralytics import YOLO
    print(f"Loading YOLO from {YOLO_WEIGHTS} …")
    return YOLO(str(YOLO_WEIGHTS))


def load_sam():
    import argparse as ap
    from segment_anything import sam_model_registry
    from segment_anything.predictor_sammed import SammedPredictor

    print(f"Loading SAM-Med2D on {DEVICE} …")
    args = ap.Namespace(
        image_size=256,
        sam_checkpoint=str(SAM_CHECKPOINT),
        encoder_adapter=True,
    )
    model = sam_model_registry["vit_b"](args)
    model.eval()
    model.to(DEVICE)
    return SammedPredictor(model)


def load_splits() -> dict:
    split_index = {}
    for name in ["train", "valid", "test"]:
        p = SPLIT_DIR / f"{name}.csv"
        if not p.exists():
            continue
        key = "val" if name == "valid" else name
        for line in p.read_text().splitlines()[1:]:
            stem = Path(line.strip()).stem
            if stem:
                split_index[stem] = key
    return split_index


def load_meta() -> pd.DataFrame:
    if DATASET_CSV.exists():
        return pd.read_csv(DATASET_CSV, index_col="image_id")
    return pd.DataFrame()


def all_images() -> list[Path]:
    imgs = []
    for d in IMG_DIRS:
        if d.exists():
            imgs.extend(sorted(d.glob("*.jpg")))
    return imgs


# ── Per-image inference ───────────────────────────────────────────────────────

def run_image(img_path: Path, emb_cache: dict, clf, detector, predictor,
              split_index: dict, meta_df: pd.DataFrame,
              mask_dir: Path, yolo_conf: float) -> dict:
    stem     = img_path.stem
    id_key   = stem + ".jpg"

    # ── GT label ──
    has_gt = False
    if not meta_df.empty and id_key in meta_df.index:
        has_gt = bool(meta_df.loc[id_key, "fractured"])

    # ── Classifier ──
    if id_key not in emb_cache:
        return None  # no embedding — skip
    emb   = emb_cache[id_key].reshape(1, -1)
    proba = clf.predict_proba(emb)[0]          # [P(normal), P(fracture)]
    prob_fracture = float(proba[1])
    predicted     = prob_fracture > THRESHOLD

    # ── YOLO + SAM ──
    detections = []
    if predicted:
        img_np = np.array(Image.open(img_path).convert("RGB"))
        H, W   = img_np.shape[:2]

        yolo_res = detector.predict(img_np, conf=yolo_conf, verbose=False)[0]
        boxes    = yolo_res.boxes.xyxy.cpu().numpy()  if len(yolo_res.boxes) else []
        confs    = yolo_res.boxes.conf.cpu().numpy()  if len(yolo_res.boxes) else []

        if len(boxes):
            with torch.no_grad():
                predictor.set_image(img_np)
                for i, (box, yconf) in enumerate(zip(boxes, confs)):
                    x1, y1, x2, y2 = map(float, box[:4])
                    masks, scores, _ = predictor.predict(
                        box=np.array([x1, y1, x2, y2]),
                        multimask_output=True,
                    )
                    best  = int(np.argmax(scores))
                    mask  = masks[best].astype(np.uint8)
                    score = float(scores[best])

                    mask_filename = f"{stem}_det{i}.png"
                    Image.fromarray(mask * 255).save(mask_dir / mask_filename)

                    detections.append({
                        "det_id":    i,
                        "yolo_bbox": [round(x1), round(y1), round(x2), round(y2)],
                        "yolo_conf": round(float(yconf), 4),
                        "sam_score": round(score, 4),
                        "mask_path": f"masks/{mask_filename}",
                    })

    return {
        "image_id":       stem,
        "split":          split_index.get(stem, ""),
        "has_fracture_gt": has_gt,
        "classifier": {
            "prob_normal":        round(float(proba[0]), 4),
            "prob_fracture":      round(prob_fracture, 4),
            "predicted_fracture": predicted,
            "threshold":          THRESHOLD,
        },
        "detections": detections,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out",   default="output",  help="Output directory")
    parser.add_argument("--conf",  type=float, default=0.25, help="YOLO confidence threshold")
    parser.add_argument("--limit", type=int,   default=None, help="Process only first N images")
    args = parser.parse_args()

    out_dir  = Path(args.out)
    res_dir  = out_dir / "results"
    mask_dir = out_dir / "masks"
    res_dir.mkdir(parents=True, exist_ok=True)
    mask_dir.mkdir(parents=True, exist_ok=True)

    # Load all models
    emb_cache, clf = load_classifier()
    detector       = load_detector()
    predictor      = load_sam()
    split_index    = load_splits()
    meta_df        = load_meta()
    images         = all_images()

    if args.limit:
        images = images[:args.limit]

    print(f"\nRunning pipeline on {len(images)} images  (device={DEVICE})\n")

    summary_rows = []
    for img_path in tqdm(images, unit="img"):
        result = run_image(
            img_path, emb_cache, clf, detector, predictor,
            split_index, meta_df, mask_dir, args.conf,
        )
        if result is None:
            continue

        # Write per-image JSON
        json_path = res_dir / f"{result['image_id']}.json"
        with open(json_path, "w") as f:
            json.dump(result, f, indent=2)

        # Accumulate summary row
        dets = result["detections"]
        summary_rows.append({
            "image_id":          result["image_id"],
            "split":             result["split"],
            "has_fracture_gt":   result["has_fracture_gt"],
            "prob_fracture":     result["classifier"]["prob_fracture"],
            "predicted_fracture": result["classifier"]["predicted_fracture"],
            "n_detections":      len(dets),
            "yolo_bboxes":       json.dumps([d["yolo_bbox"] for d in dets]),
            "sam_scores":        json.dumps([d["sam_score"]  for d in dets]),
        })

    # Write summary CSV
    csv_path = out_dir / "summary.csv"
    if summary_rows:
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=summary_rows[0].keys())
            writer.writeheader()
            writer.writerows(summary_rows)

    print(f"\nDone.")
    print(f"  JSON results : {res_dir}")
    print(f"  Mask PNGs    : {mask_dir}")
    print(f"  Summary CSV  : {csv_path}")

    # Quick stats
    if summary_rows:
        n_pred = sum(1 for r in summary_rows if r["predicted_fracture"])
        n_gt   = sum(1 for r in summary_rows if r["has_fracture_gt"])
        print(f"\n  Processed    : {len(summary_rows)}")
        print(f"  GT fractured : {n_gt}")
        print(f"  Predicted    : {n_pred}")


if __name__ == "__main__":
    main()
