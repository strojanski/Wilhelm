"""Fit a logistic-regression fracture classifier on cached MedSigLIP embeddings.

Uses the same 80/20 split as the notebook (test_size=0.20, random_state=1).

Run from vision_classifier/scripts/:
    python train.py
    python train.py --embeddings ../embeddings.npz --out ../fracture_classifier_v4.pkl
"""

import argparse
import pickle
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--embeddings", type=Path, default=Path("../embeddings.npz"))
    ap.add_argument("--out",        type=Path, default=Path("../fracture_classifier_v4.pkl"))
    args = ap.parse_args()

    data = np.load(args.embeddings)
    X, y = data["X"], data["y"]
    print(f"Loaded embeddings {X.shape}, labels {y.shape}")
    print(f"Class balance: fractured={int(y.sum())} ({y.mean():.1%})")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, stratify=y, random_state=1
    )
    print(f"\nTraining set (80%): {len(y_train)}  |  Fracture rate: {y_train.mean():.1%}")
    print(f"Final Test set (20%): {len(y_test)}  |  Fracture rate: {y_test.mean():.1%}")

    clf = LogisticRegression(
        max_iter=2000,
        C=1.0,
        class_weight="balanced",
        solver="lbfgs",
    )
    clf.fit(X_train, y_train)

    test_probs = clf.predict_proba(X_test)[:, 1]
    print(f"\nTest AUC: {roc_auc_score(y_test, test_probs):.4f}")

    with open(args.out, "wb") as f:
        pickle.dump(clf, f)
    print(f"Saved → {args.out.resolve()}")


if __name__ == "__main__":
    main()
