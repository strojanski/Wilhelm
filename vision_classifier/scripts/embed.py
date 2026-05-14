"""Extract MedSigLIP embeddings for FracAtlas images.

Input is a local FracAtlas directory containing `dataset.csv` and `images/`.
Output is an ignored `.npz` file with arrays `X` and `y`; keep it out of Git.

Example:
    python vision_classifier/scripts/embed.py \
        --data-dir C:\\Users\\Erik\\Documents\\FracAtlas\\FracAtlas \
        --out vision_classifier/data/fracatlas_medsiglip_embeddings.npz
"""

from __future__ import annotations

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

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = ROOT / "data/FracAtlas"
DEFAULT_OUT = ROOT / "vision_classifier/data/fracatlas_medsiglip_embeddings.npz"
DEFAULT_MODEL = "google/medsiglip-448"


def scan_image_paths(image_root: Path) -> dict[str, Path]:
    paths = {}
    for root, _, files in os.walk(image_root):
        for filename in files:
            if filename.lower().endswith((".jpg", ".jpeg", ".png")):
                paths[filename] = Path(root) / filename
    return paths


def build_dataset(data_dir: Path) -> list[dict]:
    """Return plain image records to avoid pyarrow image-casting issues."""
    csv_path = data_dir / "dataset.csv"
    image_root = data_dir / "images"
    if not csv_path.exists():
        sys.exit(f"ERROR: {csv_path} not found.")
    if not image_root.exists():
        sys.exit(f"ERROR: {image_root} not found.")

    image_paths = scan_image_paths(image_root)
    df = pd.read_csv(csv_path)
    df["image"] = df["image_id"].apply(
        lambda image_id: str(image_paths.get(image_id)) if image_id in image_paths else None
    )

    missing = int(df["image"].isna().sum())
    if missing:
        print(f"WARNING: {missing} images from CSV were not found on disk; dropping them.")
        df = df.dropna(subset=["image"]).reset_index(drop=True)

    print(f"Loaded {len(df)} samples ({int(df['fractured'].sum())} fractured).")
    return [
        {
            "image_id": row.image_id,
            "image_path": Path(row.image),
            "fractured": int(row.fractured),
        }
        for row in df.itertuples(index=False)
    ]


def as_numpy_embedding(output) -> np.ndarray:
    if hasattr(output, "pooler_output"):
        output = output.pooler_output
    elif not isinstance(output, torch.Tensor):
        output = output[0]
    return output.float().cpu().numpy()


@torch.no_grad()
def embed_images_lazy(dataset, processor, model, device, dtype, batch_size=8) -> np.ndarray:
    all_embs = []
    progress = tqdm(
        total=len(dataset),
        desc=f"Embedding on {device}",
        unit="img",
        dynamic_ncols=True,
    )
    try:
        for start in range(0, len(dataset), batch_size):
            end = min(start + batch_size, len(dataset))
            batch = [
                Image.open(dataset[i]["image_path"]).convert("RGB")
                for i in range(start, end)
            ]
            progress.set_postfix(batch=f"{start + 1}-{end}", batch_size=len(batch))
            inputs = processor(images=batch, return_tensors="pt").to(device)
            inputs["pixel_values"] = inputs["pixel_values"].to(dtype)
            output = model.get_image_features(**inputs)
            all_embs.append(as_numpy_embedding(output))
            progress.update(len(batch))
            del batch, inputs, output
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            gc.collect()
    finally:
        progress.close()
    return np.concatenate(all_embs, axis=0)


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--hf-token", default=os.environ.get("HF_TOKEN"))
    ap.add_argument("--overwrite", action="store_true")
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    if args.out.exists() and not args.overwrite:
        print(f"{args.out} already exists. Pass --overwrite to recompute.")
        return

    from transformers import AutoModel, AutoProcessor

    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32
    print(f"Device: {device} | dtype: {dtype}")

    print(f"Loading {args.model} ...")
    processor = AutoProcessor.from_pretrained(args.model, token=args.hf_token)
    model = AutoModel.from_pretrained(args.model, torch_dtype=dtype, token=args.hf_token).to(device)
    model.eval()

    ds = build_dataset(args.data_dir)
    X = embed_images_lazy(ds, processor, model, device, dtype, batch_size=args.batch_size)
    y = np.array([record["fractured"] for record in ds], dtype=np.int64)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.out, X=X, y=y)
    print(f"Saved embeddings {X.shape} + labels {y.shape} -> {args.out.resolve()}")


if __name__ == "__main__":
    main()
