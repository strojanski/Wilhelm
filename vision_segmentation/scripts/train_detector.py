"""
Train a YOLOv8 fracture detector on FracAtlas.
Converts COCO annotations → YOLO format, then trains YOLOv8n.

Run from the scripts/ directory:
    pip install ultralytics
    python train_detector.py
"""

import json
import shutil
from pathlib import Path

import yaml
from PIL import Image

DATA_DIR  = Path("../data/FracAtlas")
COCO_JSON = DATA_DIR / "Annotations/COCO JSON/COCO_fracture_masks.json"
IMG_DIR   = DATA_DIR / "images/Fractured"
SPLIT_DIR = DATA_DIR / "Utilities/Fracture Split"
OUT_DIR   = DATA_DIR / "detector_dataset"
RUNS_DIR  = DATA_DIR / "detector_runs"


def load_coco():
    with open(COCO_JSON) as f:
        coco = json.load(f)
    id_to_img  = {img["id"]: img for img in coco["images"]}
    stem_to_anns: dict[str, list] = {}
    for ann in coco["annotations"]:
        img  = id_to_img[ann["image_id"]]
        stem = Path(img["file_name"]).stem
        stem_to_anns.setdefault(stem, [])
        x, y, w, h = ann["bbox"]
        iw, ih = img["width"], img["height"]
        # YOLO: cx cy w h normalised
        stem_to_anns[stem].append((
            (x + w / 2) / iw,
            (y + h / 2) / ih,
            w / iw,
            h / ih,
        ))
    return stem_to_anns


def read_split(name: str) -> list[str]:
    p = SPLIT_DIR / f"{name}.csv"
    if not p.exists():
        return []
    lines = p.read_text().splitlines()
    return [Path(l.strip()).stem for l in lines[1:] if l.strip()]  # skip header


def write_split(stems: list[str], split: str, stem_to_anns: dict):
    img_out   = OUT_DIR / "images" / split
    label_out = OUT_DIR / "labels" / split
    img_out.mkdir(parents=True, exist_ok=True)
    label_out.mkdir(parents=True, exist_ok=True)

    for stem in stems:
        src = IMG_DIR / f"{stem}.jpg"
        if not src.exists():
            continue
        shutil.copy2(src, img_out / f"{stem}.jpg")
        boxes = stem_to_anns.get(stem, [])
        label_path = label_out / f"{stem}.txt"
        with open(label_path, "w") as f:
            for cx, cy, w, h in boxes:
                f.write(f"0 {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}\n")


def build_dataset(stem_to_anns: dict):
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)

    train_stems = read_split("train")
    val_stems   = read_split("valid")
    test_stems  = read_split("test")

    # Fallback: if no split files, do 80/20 from all fractured images
    if not train_stems:
        all_stems = sorted(stem_to_anns.keys())
        cut = int(len(all_stems) * 0.8)
        train_stems, val_stems = all_stems[:cut], all_stems[cut:]

    print(f"Train: {len(train_stems)}  Val: {len(val_stems)}  Test: {len(test_stems)}")

    write_split(train_stems, "train", stem_to_anns)
    write_split(val_stems,   "val",   stem_to_anns)
    if test_stems:
        write_split(test_stems, "test", stem_to_anns)

    dataset_yaml = {
        "path": str(OUT_DIR.resolve()),
        "train": "images/train",
        "val":   "images/val",
        "nc":    1,
        "names": ["fracture"],
    }
    yaml_path = OUT_DIR / "dataset.yaml"
    with open(yaml_path, "w") as f:
        yaml.dump(dataset_yaml, f)
    print(f"Dataset written to {OUT_DIR}")
    return yaml_path


def train(yaml_path: Path):
    from ultralytics import YOLO

    model = YOLO("yolov8n.pt")  # nano — fast to train, small enough for CPU inference
    model.train(
        data=str(yaml_path),
        epochs=50,
        imgsz=512,
        batch=8,
        project=str(RUNS_DIR),
        name="fracture_det",
        exist_ok=True,
        patience=10,
        cache=False,
    )
    best = RUNS_DIR / "fracture_det" / "weights" / "best.pt"
    print(f"\nBest weights: {best}")
    return best


if __name__ == "__main__":
    print("Loading COCO annotations…")
    stem_to_anns = load_coco()
    print(f"Found annotations for {len(stem_to_anns)} images")

    print("Building YOLO dataset…")
    yaml_path = build_dataset(stem_to_anns)

    print("Training YOLOv8n…")
    best = train(yaml_path)
    print(f"\nDone. Checkpoint at: {best}")
    print("Copy this path into api.py DETECTOR_CHECKPOINT to activate.")
