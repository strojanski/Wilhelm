"""Download FracAtlas from HuggingFace and save images, masks, and bbox annotations locally."""

import json
import sys
from pathlib import Path

from datasets import load_dataset
from PIL import Image
from tqdm import tqdm

DATASET_ID = "yh0701/FracAtlas_dataset"
OUT_DIR = Path("data/fracatlas")

IMAGE_FIELD = "image"
MASK_FIELD = "mask"
BBOX_FIELD = "bbox"
FRACTURE_FIELD = "fracture"


def _find_field(features, candidates):
    for name in candidates:
        if name in features:
            return name
    return None


def save_split(split_name, split_data, features):
    image_field = _find_field(features, [IMAGE_FIELD, "img", "x_ray"])
    mask_field = _find_field(features, [MASK_FIELD, "seg_mask", "segmentation"])
    bbox_field = _find_field(features, [BBOX_FIELD, "bboxes", "box", "annotation"])

    if image_field is None:
        print(f"  WARNING: no image field found in {list(features.keys())}")
    if mask_field is None:
        print(f"  WARNING: no mask field found in {list(features.keys())}")
    if bbox_field is None:
        print(f"  WARNING: no bbox field found — bounding boxes will not be saved")

    img_dir = OUT_DIR / split_name / "images"
    mask_dir = OUT_DIR / split_name / "masks"
    img_dir.mkdir(parents=True, exist_ok=True)
    mask_dir.mkdir(parents=True, exist_ok=True)

    annotations = []

    for idx, sample in enumerate(tqdm(split_data, desc=f"  {split_name}", unit="img")):
        sample_id = f"{idx:05d}"

        if image_field and sample[image_field] is not None:
            img = sample[image_field]
            if not isinstance(img, Image.Image):
                img = Image.fromarray(img)
            img.save(img_dir / f"{sample_id}.png")

        if mask_field and sample[mask_field] is not None:
            mask = sample[mask_field]
            if not isinstance(mask, Image.Image):
                mask = Image.fromarray(mask)
            mask.save(mask_dir / f"{sample_id}.png")

        entry = {"id": sample_id}
        if FRACTURE_FIELD in features:
            entry["fracture"] = sample[FRACTURE_FIELD]
        if bbox_field and sample[bbox_field] is not None:
            entry["bbox"] = sample[bbox_field]
        annotations.append(entry)

    ann_path = OUT_DIR / split_name / "annotations.json"
    with open(ann_path, "w") as f:
        json.dump(annotations, f, indent=2)

    print(f"  Saved {len(annotations)} samples → {OUT_DIR / split_name}")
    if annotations and "bbox" in annotations[0]:
        print(f"  Example bboxes: {[a['bbox'] for a in annotations[:3]]}")

    return len(annotations)


def main():
    print(f"Loading {DATASET_ID} ...")
    try:
        ds = load_dataset(DATASET_ID)
    except Exception as e:
        sys.exit(f"Failed to load dataset: {e}")

    print(f"\nDataset info:")
    print(f"  Splits : {list(ds.keys())}")
    print(f"  Features: {ds[list(ds.keys())[0]].features}\n")

    features = ds[list(ds.keys())[0]].features
    total = 0
    for split_name, split_data in ds.items():
        total += save_split(split_name, split_data, features)

    print(f"\nDone. Total images saved: {total}")
    print(f"Output: {OUT_DIR.resolve()}")


if __name__ == "__main__":
    main()
