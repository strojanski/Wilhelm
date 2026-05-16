"""Run the full real-time classifier -> detector -> segmentor pipeline.

For every image in the configured dataset:
  1. MedSigLIP embeds the actual image pixels.
  2. The classifier head scores P(fracture).
  3. If predicted fractured, YOLO proposes boxes and SAM-Med2D creates masks.
  4. One JSON per image plus a summary CSV are written to the output folder.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from PIL import Image
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from vision_classifier.runtime import FractureClassifier

MODEL_DIR = ROOT / "vision_classifier/medsiglip-448"
CLF_PATH = ROOT / "vision_classifier/fracture_classifier_v3_0.91auc.pkl"
CLF_METADATA_PATH = CLF_PATH.with_suffix(".json")
YOLO_WEIGHTS = ROOT / "vision_segmentation/weights/best.pt"
SAM_SRC = ROOT / "vision_segmentation/SAM-Med2D"
SAM_CHECKPOINT = SAM_SRC / "sam-med2d_b.pth"
DATA_DIR = ROOT / "vision_segmentation/data/FracAtlas"
SPLIT_DIR = DATA_DIR / "Utilities/Fracture Split"
DATASET_CSV = DATA_DIR / "dataset.csv"
IMG_DIRS = [DATA_DIR / "images/Fractured", DATA_DIR / "images/Non_fractured"]

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


def load_classifier(model_dir: Path, clf_path: Path, metadata_path: Path) -> FractureClassifier:
    return FractureClassifier.load(
        model_dir=model_dir,
        classifier_path=clf_path,
        metadata_path=metadata_path,
        allow_remote_model=True,
    )


def load_detector():
    from ultralytics import YOLO

    print(f"Loading YOLO from {YOLO_WEIGHTS} ...")
    return YOLO(str(YOLO_WEIGHTS))


def load_sam():
    import argparse as ap

    sys.path.insert(0, str(SAM_SRC))
    from segment_anything import sam_model_registry
    from segment_anything.predictor_sammed import SammedPredictor

    print(f"Loading SAM-Med2D on {DEVICE} ...")
    args = ap.Namespace(
        image_size=256,
        sam_checkpoint=str(SAM_CHECKPOINT),
        encoder_adapter=True,
    )
    model = sam_model_registry["vit_b"](args)
    model.eval()
    model.to(DEVICE)
    return SammedPredictor(model)


def load_splits() -> dict[str, str]:
    split_index = {}
    for name in ["train", "valid", "test"]:
        path = SPLIT_DIR / f"{name}.csv"
        if not path.exists():
            continue
        key = "val" if name == "valid" else name
        for line in path.read_text().splitlines()[1:]:
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
    for directory in IMG_DIRS:
        if directory.exists():
            imgs.extend(sorted(directory.glob("*.jpg")))
    return imgs


def run_image(
    img_path: Path,
    classifier: FractureClassifier,
    detector,
    predictor,
    split_index: dict[str, str],
    meta_df: pd.DataFrame,
    mask_dir: Path,
    yolo_conf: float,
) -> dict:
    stem = img_path.stem
    image_id = f"{stem}.jpg"

    has_gt = False
    if not meta_df.empty and image_id in meta_df.index:
        has_gt = bool(meta_df.loc[image_id, "fractured"])

    img = Image.open(img_path)
    prediction = classifier.predict(img, image_id=image_id)
    prob_fracture = prediction.prob_fracture
    predicted = prediction.predicted_fracture

    detections = []
    if predicted:
        img_np = np.array(img.convert("RGB"))
        yolo_res = detector.predict(img_np, conf=yolo_conf, verbose=False)[0]
        boxes = yolo_res.boxes.xyxy.cpu().numpy() if len(yolo_res.boxes) else []
        confs = yolo_res.boxes.conf.cpu().numpy() if len(yolo_res.boxes) else []

        if len(boxes):
            with torch.no_grad():
                predictor.set_image(img_np)
                for i, (box, yconf) in enumerate(zip(boxes, confs)):
                    x1, y1, x2, y2 = map(float, box[:4])
                    masks, scores, _ = predictor.predict(
                        box=np.array([x1, y1, x2, y2]),
                        multimask_output=True,
                    )
                    best = int(np.argmax(scores))
                    mask = masks[best].astype(np.uint8)
                    score = float(scores[best])

                    mask_filename = f"{stem}_det{i}.png"
                    Image.fromarray(mask * 255).save(mask_dir / mask_filename)

                    detections.append({
                        "det_id": i,
                        "yolo_bbox": [round(x1), round(y1), round(x2), round(y2)],
                        "yolo_conf": round(float(yconf), 4),
                        "sam_score": round(score, 4),
                        "mask_path": f"masks/{mask_filename}",
                    })

    return {
        "image_id": stem,
        "split": split_index.get(stem, ""),
        "has_fracture_gt": has_gt,
        "classifier": {
            "prob_normal": round(1.0 - prob_fracture, 4),
            "prob_fracture": round(prob_fracture, 4),
            "predicted_fracture": predicted,
            "threshold": round(classifier.threshold, 6),
        },
        "detections": detections,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="output", help="Output directory")
    parser.add_argument("--conf", type=float, default=0.25, help="YOLO confidence threshold")
    parser.add_argument("--limit", type=int, default=None, help="Process only first N images")
    parser.add_argument("--model-dir", type=Path, default=MODEL_DIR)
    parser.add_argument("--classifier", type=Path, default=CLF_PATH)
    parser.add_argument("--metadata", type=Path, default=CLF_METADATA_PATH)
    args = parser.parse_args()

    out_dir = Path(args.out)
    res_dir = out_dir / "results"
    mask_dir = out_dir / "masks"
    res_dir.mkdir(parents=True, exist_ok=True)
    mask_dir.mkdir(parents=True, exist_ok=True)

    classifier = load_classifier(args.model_dir, args.classifier, args.metadata)
    detector = load_detector()
    predictor = load_sam()
    split_index = load_splits()
    meta_df = load_meta()
    images = all_images()

    if args.limit:
        images = images[:args.limit]

    print(f"\nRunning pipeline on {len(images)} images (device={DEVICE})\n")

    summary_rows = []
    for img_path in tqdm(images, unit="img"):
        result = run_image(
            img_path,
            classifier,
            detector,
            predictor,
            split_index,
            meta_df,
            mask_dir,
            args.conf,
        )

        json_path = res_dir / f"{result['image_id']}.json"
        json_path.write_text(json.dumps(result, indent=2))

        detections = result["detections"]
        summary_rows.append({
            "image_id": result["image_id"],
            "split": result["split"],
            "has_fracture_gt": result["has_fracture_gt"],
            "prob_fracture": result["classifier"]["prob_fracture"],
            "predicted_fracture": result["classifier"]["predicted_fracture"],
            "n_detections": len(detections),
            "yolo_bboxes": json.dumps([det["yolo_bbox"] for det in detections]),
            "sam_scores": json.dumps([det["sam_score"] for det in detections]),
        })

    csv_path = out_dir / "summary.csv"
    if summary_rows:
        with csv_path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=summary_rows[0].keys())
            writer.writeheader()
            writer.writerows(summary_rows)

    print("\nDone.")
    print(f"  JSON results : {res_dir}")
    print(f"  Mask PNGs    : {mask_dir}")
    print(f"  Summary CSV  : {csv_path}")

    if summary_rows:
        n_pred = sum(1 for row in summary_rows if row["predicted_fracture"])
        n_gt = sum(1 for row in summary_rows if row["has_fracture_gt"])
        print(f"\n  Processed    : {len(summary_rows)}")
        print(f"  GT fractured : {n_gt}")
        print(f"  Predicted    : {n_pred}")


if __name__ == "__main__":
    main()
