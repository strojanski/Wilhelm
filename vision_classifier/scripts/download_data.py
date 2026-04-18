"""Download FracAtlas via Kaggle (same approach as the Colab notebook).

The notebook used:
    os.environ['KAGGLE_USERNAME'] = "..."
    os.environ['KAGGLE_KEY'] = "..."
    kaggle datasets download -d mahmudulhasantasin/fracatlas-original-dataset
    unzip fracatlas-original-dataset.zip -d ./fracatlas_data

This script does the same thing programmatically. Output goes to
../data/FracAtlas/ (shared with vision_segmentation).

Run from the vision_classifier/ directory:
    python scripts/download_data.py
    python scripts/download_data.py --out-dir ../data
"""

import argparse
import os
import sys
import zipfile
from pathlib import Path

KAGGLE_DATASET = "mahmudulhasantasin/fracatlas-original-dataset"
DEFAULT_OUT    = Path("../data")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT,
                    help="Parent folder to unzip into (FracAtlas/ will be created inside)")
    args = ap.parse_args()

    target = args.out_dir / "FracAtlas"
    if (target / "dataset.csv").exists():
        print(f"FracAtlas already present at {target.resolve()}. Skipping.")
        return

    # Check Kaggle credentials
    username = os.environ.get("KAGGLE_USERNAME")
    key      = os.environ.get("KAGGLE_KEY")
    if not username or not key:
        sys.exit(
            "Set your Kaggle credentials first:\n\n"
            "    set KAGGLE_USERNAME=your_username\n"
            "    set KAGGLE_KEY=your_api_key\n\n"
            "Get your key from https://www.kaggle.com/settings/account → API → Create New Token"
        )

    try:
        import kaggle  # noqa: F401 — triggers credential check
    except ImportError:
        sys.exit("kaggle package not found. Run:  pip install kaggle")

    from kaggle.api.kaggle_api_extended import KaggleApiExtended
    api = KaggleApiExtended()
    api.authenticate()

    zip_path = Path("fracatlas-original-dataset.zip")
    if not zip_path.exists():
        print(f"Downloading {KAGGLE_DATASET} ...")
        api.dataset_download_files(KAGGLE_DATASET, path=".", unzip=False)
        print("Downloaded.")
    else:
        print(f"Zip already exists at {zip_path.resolve()}, skipping download.")

    print(f"Unzipping to {args.out_dir.resolve()} ...")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(args.out_dir)

    if target.exists():
        print(f"\nDone. FracAtlas at {target.resolve()}")
        print(f"  dataset.csv : {(target / 'dataset.csv').exists()}")
        print(f"  images/     : {(target / 'images').exists()}")
    else:
        print(f"\nWARNING: Expected {target} not found after unzip.")
        print("Check the zip contents and adjust --out-dir if needed.")


if __name__ == "__main__":
    main()
