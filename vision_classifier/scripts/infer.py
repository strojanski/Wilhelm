"""Run inference on FracAtlas images and visualize results.

Mirrors notebook cell 13 (predict_fracture) and cell 34 (grid of images).

Run from vision_classifier/:
    python scripts/infer.py --data-dir ../data/FracAtlas
    python scripts/infer.py --data-dir ../data/FracAtlas --n 8
    python scripts/infer.py --image path/to/xray.jpg
"""

import argparse
import os
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image, ImageFile

ImageFile.LOAD_TRUNCATED_IMAGES = True

CLF_PATH = Path("../fracture_classifier_v3_0.91auc.pkl")


def load_fracatlas(data_dir: Path):
    from datasets import Dataset
    from datasets import Image as hf_Image

    csv_path  = data_dir / "dataset.csv"
    image_dir = data_dir / "images"
    if not csv_path.exists():
        sys.exit(f"dataset.csv not found in {data_dir}")

    image_paths = {}
    for root, _, files in os.walk(image_dir):
        for f in files:
            if f.lower().endswith((".jpg", ".jpeg", ".png")):
                image_paths[f] = os.path.join(root, f)

    df = pd.read_csv(csv_path)
    df["image"] = df["image_id"].apply(lambda x: image_paths.get(x))
    df = df.dropna(subset=["image"]).reset_index(drop=True)
    return Dataset.from_pandas(df).cast_column("image", hf_Image()), df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir",   type=Path, default=None)
    ap.add_argument("--image",      type=Path, default=None)
    ap.add_argument("--n",          type=int,  default=8,
                    help="Number of random samples to visualize")
    ap.add_argument("--classifier", type=Path, default=CLF_PATH)
    ap.add_argument("--threshold",  type=float, default=0.5)
    ap.add_argument("--seed",       type=int,  default=0)
    args = ap.parse_args()

    if not args.data_dir and not args.image:
        ap.error("Provide --data-dir or --image")

    from model import load_model, predict
    load_model(clf_path=args.classifier)

    # ── Single image ──────────────────────────────────────────────────────────
    if args.image:
        if not args.image.exists():
            sys.exit(f"Not found: {args.image}")
        img  = Image.open(args.image)
        prob = predict(img)
        label = "FRACTURED" if prob >= args.threshold else "normal"
        print(f"P(fracture): {prob:.4f}  →  {label}")

        plt.figure(figsize=(4, 4))
        plt.imshow(img, cmap="gray")
        plt.title(f"P(fracture)={prob:.2f}  [{label}]")
        plt.axis("off")
        plt.tight_layout()
        plt.show()
        return

    # ── Dataset grid (same as notebook cell 34) ───────────────────────────────
    print(f"Loading FracAtlas from {args.data_dir} ...")
    full, df = load_fracatlas(args.data_dir)
    print(f"Loaded {len(full)} images.\n")

    rng     = np.random.RandomState(args.seed)
    indices = rng.choice(len(full), min(args.n, len(full)), replace=False)

    cols = min(4, args.n)
    rows = (len(indices) + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 4, rows * 4))
    axes = np.array(axes).flatten()

    print(f"{'Image':<30} {'True':<16} {'P(fracture)':>12}  Predicted")
    print("-" * 72)

    for ax, idx in zip(axes, indices):
        sample   = full[int(idx)]
        img      = sample["image"]
        prob     = predict(img)
        true_lbl = "Fractured" if sample["fractured"] == 1 else "Not fractured"
        predicted = "FRACTURED" if prob >= args.threshold else "normal"
        name     = df.iloc[int(idx)]["image_id"]

        color = "red" if predicted != true_lbl.split()[0].upper() and sample["fractured"] == 1 else "black"
        ax.imshow(img, cmap="gray")
        ax.set_title(f"True: {true_lbl}\nP(fracture)={prob:.2f}", color=color, fontsize=9)
        ax.axis("off")

        print(f"{name:<30} {true_lbl:<16} {prob:>12.4f}  {predicted}")

    for ax in axes[len(indices):]:
        ax.axis("off")

    plt.suptitle("Fracture classifier — MedSigLIP + LogReg", fontsize=12)
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
