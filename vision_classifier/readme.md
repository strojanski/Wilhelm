# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Binary fracture classifier for the RadiAI triage pipeline. Frozen **MedSigLIP-448** vision encoder (medical-specialised SigLIP, 1152-D embeddings) + a lightweight `LogisticRegression` head fit on those embeddings. Trained on FracAtlas (4,083 X-rays, ~17% fractured); test AUC 0.89 / recall-for-fractured 0.72 at default 0.5 threshold. The head is tiny and CPU-fast — the encoder is the expensive bit.

In the wider system this service is the **root of the triage tree**: classify first, and only forward to the segmentation service if the positive probability clears a recall-oriented threshold.

## Environment Setup

```bash
# Activate virtual environment
.venv\Scripts\activate      # Windows
source .venv/bin/activate    # Unix

pip install -r requirements.txt

# Accept the gated-model terms at https://huggingface.co/google/medsiglip-448
# then authenticate once:
huggingface-cli login
```

## Running the Pipeline

```bash
cd scripts
python download_data.py                         # FracAtlas -> ../../data/FracAtlas/  (skipped if shared with vision_segmentation)
python embed.py --out embeddings.npz            # MedSigLIP features, ~few min on T4
python train.py --embeddings embeddings.npz \
                --out ../fracture_classifier_v4.pkl
python evaluate.py --classifier ../fracture_classifier_v3_0.91auc.pkl
```

`train.py` writes the held-out split to `test_split.npz` so `evaluate.py` scores the same images the notebook reported numbers for.

## Running the API

```bash
cd scripts
uvicorn api:app --reload --port 8001
```

Env vars (all optional):

| Var | Default | Purpose |
|-----|---------|---------|
| `MEDSIGLIP_MODEL` | `google/medsiglip-448` | HF model id for the encoder |
| `CLF_PATH` | `../fracture_classifier_v3_0.91auc.pkl` | Pickled sklearn head |
| `FRACTURE_THRESHOLD` | `0.35` | Probability gate; `above_threshold=true` triggers segmentation in `/triage` |
| `SEGMENTATION_URL` | `http://localhost:8000` | Where `/triage` forwards positives |

### Endpoints

All inputs are JSON `{image_b64: str}` (data-URL prefixes accepted).

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Liveness + loaded-state + threshold |
| POST | `/embed` | Raw 1152-D MedSigLIP feature vector |
| POST | `/classify` | `prob_fractured`, `predicted`, `above_threshold` |
| POST | `/triage` | Classify; if `above_threshold`, forward image to segmentation and return both payloads. On segmentation error, returns classification + `segmentation: {error}` (never 500s) |

`/triage` accepts an optional `run_segmentation: bool` to override the threshold gate (force-on or force-off) — useful for UI-driven workflows.

## Architecture

**Encoder:** `google/medsiglip-448` (frozen). Loaded once at startup via `AutoProcessor` + `AutoModel`. `model.get_image_features(**inputs)` → (1, 1152) embedding.

**Head:** scikit-learn `LogisticRegression(max_iter=2000, C=1.0, class_weight="balanced", solver="lbfgs")`. Pickled to a single file. `class_weight="balanced"` compensates for the ~17% fracture rate in FracAtlas.

**Why a linear head instead of fine-tuning?** MedSigLIP is pretrained on 33M medical image/text pairs — its image features separate fracture / non-fracture nearly linearly on FracAtlas. A linear probe reaches AUC 0.89 with no GPU training. Full fine-tuning (LoRA on the ViT, etc.) is possible but was out of scope for the hackathon.

**Threshold choice:** test recall for fractured is 0.72 at the standard 0.5 operating point; lowering the API default to 0.35 biases the triage gate toward higher recall at the cost of precision — appropriate when a false-negative (missed fracture) is worse than a false-positive (unnecessary segmentation call).

## Key Patterns

```python
# Same shape used by both scripts/embed.py and scripts/api.py
@torch.no_grad()
def embed(pil_img):
    inputs = processor(images=[pil_img.convert("RGB")], return_tensors="pt").to(device)
    inputs["pixel_values"] = inputs["pixel_values"].to(dtype)
    return model.get_image_features(**inputs).float().cpu().numpy()  # (1, 1152)

prob = clf.predict_proba(embed(pil_img))[0, 1]
```

## Files

- `scripts/download_data.py` — fetches FracAtlas to the shared `../data/FracAtlas/` path; no-op if already present
- `scripts/embed.py` — MedSigLIP embeddings → `embeddings.npz`
- `scripts/train.py` — stratified 70/15/15 split, LogReg fit, saves pickle + `test_split.npz`
- `scripts/evaluate.py` — loads pickle + held-out split, prints AUC / AP / classification report
- `scripts/api.py` — FastAPI service (see Endpoints)
- `fracture_classifier_v3_0.91auc.pkl` — known-good checkpoint (default for the API)
- `fracatlas_medsiglip_classifier (1).ipynb` — Colab exploratory notebook; this scripts/ layout is the extracted version of it
