"""Evaluate the fracture classifier on the held-out test set.

Loads images directly, runs one MedSigLIP forward pass per image,
feeds the embedding to the classifier. No pre-cached embeddings needed.

Run from vision_classifier/scripts/:
    python evaluate.py --data-dir ..\..\data\FracAtlas
    python evaluate.py --data-dir ..\..\data\FracAtlas --target-recall 0.85
"""

import argparse
import os
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from PIL import Image, ImageFile
from sklearn.metrics import (
    average_precision_score,
    classification_report,
    confusion_matrix,
    precision_recall_curve,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import train_test_split
from tqdm import tqdm

ImageFile.LOAD_TRUNCATED_IMAGES = True

CLF_PATH = Path("../fracture_classifier_v3_0.91auc.pkl")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir",      type=Path, required=True)
    ap.add_argument("--classifier",    type=Path, default=CLF_PATH)
    ap.add_argument("--target-recall", type=float, default=0.90)
    ap.add_argument("--no-plots",      action="store_true")
    args = ap.parse_args()

    if not args.classifier.exists():
        sys.exit(f"Classifier not found: {args.classifier}")

    csv_path  = args.data_dir / "dataset.csv"
    image_dir = args.data_dir / "images"
    if not csv_path.exists():
        sys.exit(f"dataset.csv not found in {args.data_dir}")

    # ── Load model ────────────────────────────────────────────────────────────
    from model import load_model, predict
    load_model(clf_path=args.classifier)

    # ── Build image path map ──────────────────────────────────────────────────
    image_paths = {}
    for root, _, files in os.walk(image_dir):
        for f in files:
            if f.lower().endswith((".jpg", ".jpeg", ".png")):
                image_paths[f] = Path(root) / f

    df = pd.read_csv(csv_path)
    df["path"] = df["image_id"].apply(lambda x: image_paths.get(x))
    df = df.dropna(subset=["path"]).reset_index(drop=True)

    X_ids = df.index.values
    y     = df["fractured"].values.astype(int)

    # ── Recreate the exact 80/20 split from the notebook ─────────────────────
    _, test_idx, _, y_test = train_test_split(
        X_ids, y, test_size=0.20, stratify=y, random_state=1
    )
    test_df = df.iloc[test_idx].reset_index(drop=True)

    print(f"Test set: {len(test_df)} images  (fracture rate {y_test.mean():.1%})\n")

    # ── One forward pass per test image ──────────────────────────────────────
    probs = []
    for _, row in tqdm(test_df.iterrows(), total=len(test_df), desc="Embedding+classifying"):
        img  = Image.open(row["path"])
        prob = predict(img)
        probs.append(prob)

    probs = np.array(probs)

    # ── Clinical threshold: target recall ─────────────────────────────────────
    precisions, recalls, thresholds = precision_recall_curve(y_test, probs)
    valid = np.where(recalls[:-1] >= args.target_recall)[0]
    if len(valid) > 0:
        clinical_threshold = thresholds[valid[-1]]
        op_idx = valid[-1]
    else:
        print(f"WARNING: Could not reach {args.target_recall*100:.0f}% recall — using 0.5")
        clinical_threshold = 0.5
        op_idx = None

    print(f"For >= {args.target_recall*100:.0f}% Recall, threshold: {clinical_threshold:.4f}\n")

    clinical_preds = (probs >= clinical_threshold).astype(int)

    print("--- CLINICAL TRIAGE REPORT ---")
    print(classification_report(y_test, clinical_preds,
                                target_names=["Not fractured", "Fractured"]))

    if args.no_plots:
        return

    # ── Plots ─────────────────────────────────────────────────────────────────
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))

    fpr, tpr, _ = roc_curve(y_test, probs)
    auc = roc_auc_score(y_test, probs)
    axes[0].plot(fpr, tpr, label=f"AUC = {auc:.4f}", color="darkorange")
    axes[0].plot([0, 1], [0, 1], "k--", alpha=0.4)
    axes[0].set_xlabel("False Positive Rate")
    axes[0].set_ylabel("True Positive Rate")
    axes[0].set_title("ROC Curve")
    axes[0].legend()

    ap_score = average_precision_score(y_test, probs)
    axes[1].plot(recalls, precisions, label=f"AP = {ap_score:.4f}", color="purple")
    if op_idx is not None:
        axes[1].plot(recalls[op_idx], precisions[op_idx], "ro", markersize=8,
                     label="Clinical Operating Point")
    axes[1].set_xlabel("Recall")
    axes[1].set_ylabel("Precision")
    axes[1].set_title("Precision-Recall Curve")
    axes[1].legend()

    cm = confusion_matrix(y_test, clinical_preds)
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", ax=axes[2],
                xticklabels=["Not fractured", "Fractured"],
                yticklabels=["Not fractured", "Fractured"])
    axes[2].set_xlabel("Predicted")
    axes[2].set_ylabel("True")
    axes[2].set_title(f"Confusion Matrix (Threshold={clinical_threshold:.3f})")

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
