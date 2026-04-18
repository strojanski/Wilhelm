# Fracture Classifier

Binary fracture classifier for the RadiAI triage pipeline. Uses pre-computed **MedSigLIP-448** embeddings (1152-D) + a trained MLP head — no transformer needed at inference time.

Trained on FracAtlas (4,083 X-rays, ~17% fractured). Threshold calibrated to ≥90% recall.

---

## Quick Start

### 1. Environment

```
cd vision_classifier
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Build the embedding cache (once)

Converts the pre-computed MedSigLIP embeddings into a fast lookup table.
After this step MedSigLIP is never loaded at inference.

```
cd scripts
python build_cache.py --data-dir ..\data\FracAtlas\FracAtlas
```

### 3. Start the API

```
uvicorn api:app --reload --port 8001
```

Expected startup output:
```
Embedding cache: 4083 images (MedSigLIP not needed)
Loading classifier from fracture_classifier_v3_0.91auc.pkl ...
Ready.
```

### 4. Run inference on an image

```
python infer.py --image ..\data\FracAtlas\FracAtlas\images\Fractured\IMG0000019.jpg --image-id IMG0000019.jpg
```

`--image-id` matches the filename to a cached embedding (instant lookup).
Without it the API falls back to running MedSigLIP (slow, requires the model files).

---

## API

**POST** `http://localhost:8001/classify`

Request:
```json
{
  "image_b64": "<base64-encoded image>",
  "image_id":  "IMG0000019.jpg",
  "true_label": "fractured"
}
```
`image_id` and `true_label` are optional.

Response:
```json
{
  "prob_fractured":       0.848,
  "send_to_segmentation": true,
  "overlay_b64":          "<base64 JPEG>"
}
```

- `prob_fractured` — raw probability 0–1
- `send_to_segmentation` — `true` when `prob >= 0.0853` (≥90% recall threshold)
- `overlay_b64` — the X-ray with red/green border and probability drawn on it

**GET** `http://localhost:8001/health`

---

## Files

| File | Purpose |
|------|---------|
| `scripts/build_cache.py` | Build `embedding_cache.pkl` from npz + dataset.csv |
| `scripts/api.py` | FastAPI service (port 8001) |
| `scripts/infer.py` | Call the API on one image, show overlay |
| `scripts/model.py` | Embedding cache loader + MLP inference |
| `scripts/evaluate.py` | Reproduce test metrics from the notebook |
| `scripts/train.py` | Retrain the MLP head from embeddings |
| `fracture_classifier_v3_0.91auc.pkl` | Trained MLP classifier |
| `data/fracatlas_medsiglip_embeddings.npz` | Pre-computed embeddings (4083 × 1152) |
| `embedding_cache.pkl` | Built by `build_cache.py` — filename → embedding lookup |
