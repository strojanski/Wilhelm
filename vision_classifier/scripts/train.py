"""Train a fracture classifier head on cached MedSigLIP embeddings.

Training is intentionally kept out of Docker. First extract embeddings with
`embed.py`, then train either the current logistic-regression style head or the
MLP head ported from `bone_fracture_classifier_medsiglip.ipynb`.

Example:
    python vision_classifier/scripts/train.py \
        --embeddings vision_classifier/data/fracatlas_medsiglip_embeddings.npz \
        --head mlp \
        --out vision_classifier/fracture_classifier_v4.pkl \
        --metadata-out vision_classifier/fracture_classifier_v4.json
"""

from __future__ import annotations

import argparse
import csv
import json
import pickle
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    classification_report,
    confusion_matrix,
    precision_recall_curve,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.neural_network import MLPClassifier
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EMBEDDINGS = ROOT / "vision_classifier/data/fracatlas_medsiglip_embeddings.npz"
DEFAULT_OUT = ROOT / "vision_classifier/fracture_classifier_v4.pkl"
DEFAULT_MODEL_ID = "google/medsiglip-448"


def build_classifier(head: str, random_state: int):
    if head == "logreg":
        return LogisticRegression(
            max_iter=2000,
            C=1.0,
            class_weight="balanced",
            solver="lbfgs",
        )
    if head == "mlp":
        return MLPClassifier(
            hidden_layer_sizes=(512, 256, 64),
            activation="relu",
            solver="adam",
            alpha=1e-5,
            learning_rate_init=0.001,
            max_iter=500,
            early_stopping=True,
            validation_fraction=0.15,
            random_state=random_state,
        )
    raise ValueError(f"Unknown classifier head: {head}")


def build_mlp_search_candidates(random_state: int) -> list[dict[str, Any]]:
    hidden_layers = [
        (256,),
        (512,),
        (1024,),
        (512, 256),
        (1024, 512),
        (512, 256, 64),
    ]
    alphas = [1e-6, 1e-5, 1e-4, 1e-3]
    learning_rates = [5e-4, 1e-3, 2e-3]

    candidates = []
    for layers in hidden_layers:
        for alpha in alphas:
            for learning_rate in learning_rates:
                candidates.append(
                    {
                        "hidden_layer_sizes": layers,
                        "alpha": alpha,
                        "learning_rate_init": learning_rate,
                        "random_state": random_state,
                    }
                )
    return candidates


def sample_candidates(
    candidates: list[dict[str, Any]],
    n_iter: int,
    random_state: int,
) -> list[dict[str, Any]]:
    if n_iter <= 0 or n_iter >= len(candidates):
        return candidates

    baseline = {
        "hidden_layer_sizes": (512, 256, 64),
        "alpha": 1e-5,
        "learning_rate_init": 0.001,
        "random_state": random_state,
    }
    remaining = [candidate for candidate in candidates if candidate != baseline]
    rng = random.Random(random_state)
    sampled = rng.sample(remaining, n_iter - 1)
    return [baseline, *sampled]


def run_mlp_search(
    X_train: np.ndarray,
    y_train: np.ndarray,
    *,
    candidates: list[dict[str, Any]],
    cv_folds: int,
    scoring: str,
    random_state: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cv = StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=random_state)
    rows = []

    for candidate_id, params in enumerate(
        tqdm(candidates, desc="MLP search", unit="candidate", dynamic_ncols=True),
        start=1,
    ):
        roc_scores = []
        ap_scores = []
        for fold_train, fold_val in cv.split(X_train, y_train):
            clf = build_classifier("mlp", random_state=random_state)
            clf.set_params(**params)
            clf.fit(X_train[fold_train], y_train[fold_train])
            val_probs = clf.predict_proba(X_train[fold_val])[:, 1]
            roc_scores.append(float(roc_auc_score(y_train[fold_val], val_probs)))
            ap_scores.append(float(average_precision_score(y_train[fold_val], val_probs)))

        rows.append(
            {
                "candidate_id": candidate_id,
                "mean_test_roc_auc": float(np.mean(roc_scores)),
                "std_test_roc_auc": float(np.std(roc_scores)),
                "mean_test_average_precision": float(np.mean(ap_scores)),
                "std_test_average_precision": float(np.std(ap_scores)),
                "params": params,
            }
        )

    score_key = f"mean_test_{scoring}"
    rows = sorted(rows, key=lambda row: row[score_key], reverse=True)
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank
    return rows, rows[0]["params"]


def write_search_results(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sorted_rows = sorted(rows, key=lambda row: int(row["rank"]))
    fieldnames = [
        "rank",
        "candidate_id",
        "mean_test_roc_auc",
        "std_test_roc_auc",
        "mean_test_average_precision",
        "std_test_average_precision",
        "params",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in sorted_rows:
            writer.writerow(
                {
                    **{key: row.get(key) for key in fieldnames if key != "params"},
                    "params": json.dumps(row["params"], sort_keys=True),
                }
            )


def select_threshold_for_recall(
    y_true: np.ndarray,
    probs: np.ndarray,
    target_recall: float,
) -> tuple[float, dict[str, float]]:
    precision, recall, thresholds = precision_recall_curve(y_true, probs)
    if len(thresholds) == 0:
        return 0.5, {"precision": 0.0, "recall": 0.0}

    valid = np.where(recall[:-1] >= target_recall)[0]
    idx = int(valid[-1]) if len(valid) else int(np.argmax(recall[:-1]))
    threshold = float(thresholds[idx])
    return threshold, {
        "precision": float(precision[idx]),
        "recall": float(recall[idx]),
    }


def save_pickle(obj: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import joblib

        joblib.dump(obj, path)
    except Exception:
        with path.open("wb") as f:
            pickle.dump(obj, f)


def save_metadata(metadata: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--embeddings", type=Path, default=DEFAULT_EMBEDDINGS)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--metadata-out", type=Path)
    ap.add_argument("--head", choices=["logreg", "mlp"], default="logreg")
    ap.add_argument("--target-recall", type=float, default=0.90)
    ap.add_argument("--test-size", type=float, default=0.20)
    ap.add_argument("--random-state", type=int, default=42)
    ap.add_argument("--model-id", default=DEFAULT_MODEL_ID)
    ap.add_argument("--search", action="store_true", help="Run CV hyperparameter search before final fit")
    ap.add_argument("--search-iter", type=int, default=16, help="MLP candidates to evaluate; <=0 means full grid")
    ap.add_argument("--search-cv", type=int, default=3, help="Stratified CV folds for search")
    ap.add_argument(
        "--search-scoring",
        choices=["roc_auc", "average_precision"],
        default="roc_auc",
    )
    ap.add_argument("--search-out", type=Path)
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    metadata_out = args.metadata_out or args.out.with_suffix(".json")

    data = np.load(args.embeddings)
    X, y = data["X"], data["y"].astype(np.int64)
    print(f"Loaded embeddings {X.shape}, labels {y.shape}")
    print(f"Class balance: fractured={int(y.sum())} ({y.mean():.1%})")

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=args.test_size,
        stratify=y,
        random_state=args.random_state,
    )
    print(f"\nTraining set: {len(y_train)} | Fracture rate: {y_train.mean():.1%}")
    print(f"Test set:     {len(y_test)} | Fracture rate: {y_test.mean():.1%}")

    search_metadata = None
    best_params = None
    if args.search:
        if args.head != "mlp":
            raise SystemExit("--search currently supports --head mlp only.")
        search_out = args.search_out or args.out.with_suffix(".search.csv")
        candidates = sample_candidates(
            build_mlp_search_candidates(args.random_state),
            n_iter=args.search_iter,
            random_state=args.random_state,
        )
        print(
            f"\nSearching {len(candidates)} MLP candidates "
            f"with {args.search_cv}-fold CV ({args.search_scoring}) ..."
        )
        search_rows, best_params = run_mlp_search(
            X_train,
            y_train,
            candidates=candidates,
            cv_folds=args.search_cv,
            scoring=args.search_scoring,
            random_state=args.random_state,
        )
        write_search_results(search_rows, search_out)
        top = search_rows[0]
        print(f"\nBest CV {args.search_scoring}: {top[f'mean_test_{args.search_scoring}']:.4f}")
        print(f"Best params: {best_params}")
        print(f"Saved search results -> {search_out.resolve()}")
        search_metadata = {
            "enabled": True,
            "scoring": args.search_scoring,
            "cv_folds": int(args.search_cv),
            "n_candidates": int(len(candidates)),
            "results_path": str(search_out),
            "best_params": best_params,
            "best_cv_roc_auc": top["mean_test_roc_auc"],
            "best_cv_average_precision": top["mean_test_average_precision"],
        }

    clf = build_classifier(args.head, args.random_state)
    if best_params:
        clf.set_params(**best_params)
    print(f"\nTraining {args.head} classifier ...")
    clf.fit(X_train, y_train)

    test_probs = clf.predict_proba(X_test)[:, 1]
    threshold, threshold_metrics = select_threshold_for_recall(
        y_test,
        test_probs,
        args.target_recall,
    )
    y_pred = (test_probs >= threshold).astype(np.int64)

    roc_auc = float(roc_auc_score(y_test, test_probs))
    avg_precision = float(average_precision_score(y_test, test_probs))
    cm = confusion_matrix(y_test, y_pred)

    print(f"\nTest ROC AUC:           {roc_auc:.4f}")
    print(f"Average precision:      {avg_precision:.4f}")
    print(f"Selected threshold:     {threshold:.6f}")
    print(f"Threshold precision:    {threshold_metrics['precision']:.4f}")
    print(f"Threshold recall:       {threshold_metrics['recall']:.4f}")
    print("\nConfusion matrix:")
    print(cm)
    print("\nClassification report:")
    print(classification_report(y_test, y_pred, digits=4))

    save_pickle(clf, args.out)

    metadata = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model_id": args.model_id,
        "head": args.head,
        "classifier_path": str(args.out),
        "embeddings_path": str(args.embeddings),
        "feature_dim": int(X.shape[1]),
        "n_samples": int(len(y)),
        "n_train": int(len(y_train)),
        "n_test": int(len(y_test)),
        "class_balance": {
            "fractured": int(y.sum()),
            "non_fractured": int(len(y) - y.sum()),
            "fracture_rate": float(y.mean()),
        },
        "threshold": threshold,
        "target_recall": float(args.target_recall),
        "threshold_precision": threshold_metrics["precision"],
        "threshold_recall": threshold_metrics["recall"],
        "roc_auc": roc_auc,
        "average_precision": avg_precision,
        "test_size": float(args.test_size),
        "random_state": int(args.random_state),
    }
    if search_metadata:
        metadata["search"] = search_metadata
    save_metadata(metadata, metadata_out)

    print(f"\nSaved classifier -> {args.out.resolve()}")
    print(f"Saved metadata   -> {metadata_out.resolve()}")


if __name__ == "__main__":
    main()
