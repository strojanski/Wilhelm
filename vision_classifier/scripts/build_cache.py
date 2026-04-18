"""Build an embedding cache from the pre-computed MedSigLIP npz + FracAtlas dataset.csv.

Assumes rows in the npz match rows in dataset.csv (same order as embedding extraction).
Run once; the API then uses this cache instead of loading MedSigLIP.

Run from vision_classifier/scripts/:
    python build_cache.py --data-dir ..\data\FracAtlas\FracAtlas
"""

import argparse
import pickle
from pathlib import Path

import numpy as np
import pandas as pd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir",   type=Path, required=True)
    ap.add_argument("--embeddings", type=Path, default=Path("../data/fracatlas_medsiglip_embeddings.npz"))
    ap.add_argument("--out",        type=Path, default=Path("../embedding_cache.pkl"))
    args = ap.parse_args()

    data = np.load(args.embeddings)
    X, y = data["X"], data["y"]
    print(f"Embeddings: {X.shape}  labels: {y.shape}")

    df = pd.read_csv(args.data_dir / "dataset.csv").reset_index(drop=True)

    if len(df) != len(X):
        print(f"WARNING: CSV has {len(df)} rows, npz has {len(X)} — sizes differ, ordering may be off.")
    else:
        print(f"Both have {len(X)} entries — assuming same row order.")

    cache = {row["image_id"]: X[i] for i, row in df.iterrows()}

    with open(args.out, "wb") as f:
        pickle.dump(cache, f)

    print(f"Saved {len(cache)} entries → {args.out.resolve()}")
    print(f"Example keys: {list(cache.keys())[:3]}")


if __name__ == "__main__":
    main()
