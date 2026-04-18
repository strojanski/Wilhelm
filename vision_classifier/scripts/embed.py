"""Extract MedSigLIP embeddings for every FracAtlas image → embeddings.npz.

Ported from the `embed_images_lazy` cell in
`fracatlas_medsiglip_classifier (1).ipynb`. Lazy batching keeps RAM flat on
Colab T4 / laptop CPU.

Run from the scripts/ directory:
    python embed.py --data-dir ../../data/FracAtlas --out embeddings.npz
"""

import argparse
import gc
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from PIL import Image, ImageFile
from tqdm import tqdm

ImageFile.LOAD_TRUNCATED_IMAGES = True

DEFAULT_DATA_DIR = Path("../../data/FracAtlas")
DEFAULT_OUT = Path("embeddings.npz")
DEFAULT_MODEL = "google/medsiglip-448"


def scan_image_paths(image_root: Path) -> dict:
    paths = {}
    for root, _, files in os.walk(image_root):
        for f in files:
            if f.lower().endswith((".jpg", ".jpeg", ".png")):
                paths[f] = Path(root) / f
    return paths


def build_dataset(data_dir: Path):
    """Return an HF Dataset with `image` (PIL) and `fractured` (int) columns."""
    from datasets import Dataset, Image as hf_Image

    csv_path = data_dir / "dataset.csv"
    image_root = data_dir / "images"
    if not csv_path.exists():
        sys.exit(f"ERROR: {csv_path} not found. Run download_data.py first.")
    if not image_root.exists():
        sys.exit(f"ERROR: {image_root} not found. Run download_data.py first.")

    image_paths = scan_image_paths(image_root)
    df = pd.read_csv(csv_path)
    df["image"] = df["image_id"].apply(lambda x: str(image_paths.get(x)) if x in image_paths else None)

    missing = df["image"].isna().sum()
    if missing:
        print(f"WARNING: {missing} images from CSV not on disk — dropping.")
        df = df.dropna(subset=["image"]).reset_index(drop=True)

    print(f"Loaded {len(df)} samples ({int(df['fractured'].sum())} fractured).")
    ds = Dataset.from_pandas(df).cast_column("image", hf_Image())
    return ds


@torch.no_grad()
def embed_images_lazy(dataset, processor, model, device, dtype, batch_size=8):
    all_embs = []
    for start in tqdm(range(0, len(dataset), batch_size), desc="Embedding"):
        end = min(start + batch_size, len(dataset))
        batch = [dataset[i]["image"].convert("RGB") for i in range(start, end)]
        inputs = processor(images=batch, return_tensors="pt").to(device)
        inputs["pixel_values"] = inputs["pixel_values"].to(dtype)
        out = model.get_image_features(**inputs)
        all_embs.append(out.float().cpu().numpy())
        del batch, inputs, out
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()
    return np.concatenate(all_embs, axis=0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--batch-size", type=int, default=8)
    args = ap.parse_args()

    if args.out.exists():
        print(f"{args.out} already exists. Delete it to recompute. Exiting.")
        return

    from transformers import AutoModel, AutoProcessor

    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32
    print(f"Device: {device} | dtype: {dtype}")

    print(f"Loading {args.model} ...")
    processor = AutoProcessor.from_pretrained(args.model)
    model = AutoModel.from_pretrained(args.model, dtype=dtype).to(device)
    model.eval()

    ds = build_dataset(args.data_dir)

    X = embed_images_lazy(ds, processor, model, device, dtype, batch_size=args.batch_size)
    y = np.array(ds["fractured"], dtype=np.int64)

    np.savez_compressed(args.out, X=X, y=y)
    print(f"Saved embeddings {X.shape} + labels {y.shape} → {args.out.resolve()}")


if __name__ == "__main__":
    main()
