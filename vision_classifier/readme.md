# Fracture Classifier

Binary fracture classifier tooling for the Wilhelm vision pipeline.

Production inference now runs the uploaded image pixels through MedSigLIP-448 in
real time, then passes the embedding to a sklearn-compatible classifier head.
The old `embedding_cache.pkl` shortcut is still available for debugging, but it
is disabled by default.

## Production Artifacts

The Docker image expects these files inside the image:

| Path | Purpose |
| --- | --- |
| `vision_classifier/medsiglip-448/` | Local MedSigLIP model snapshot, downloaded during Docker build |
| `vision_classifier/fracture_classifier_v3_0.91auc.pkl` | Default production classifier head |
| `vision_classifier/fracture_classifier_v3_0.91auc.json` | Optional metadata with threshold and metrics |
| `vision_segmentation/weights/best.pt` | YOLO fracture detector |
| `vision_segmentation/SAM-Med2D/` | SAM-Med2D source and checkpoint |

## Extract Embeddings Locally

Run this outside Docker after downloading FracAtlas locally:

```powershell
$env:HF_TOKEN = "hf_..."
python vision_classifier/scripts/embed.py `
  --data-dir C:\Users\Erik\Documents\FracAtlas\FracAtlas `
  --out vision_classifier/data/fracatlas_medsiglip_embeddings.npz
```

`vision_classifier/data/` is ignored by Git.

## Train A Classifier Head

Logistic regression keeps the older simple path:

```powershell
python vision_classifier/scripts/train.py `
  --embeddings vision_classifier/data/fracatlas_medsiglip_embeddings.npz `
  --head logreg `
  --out vision_classifier/fracture_classifier_v4.pkl `
  --metadata-out vision_classifier/fracture_classifier_v4.json
```

The notebook MLP path is:

```powershell
python vision_classifier/scripts/train.py `
  --embeddings vision_classifier/data/fracatlas_medsiglip_embeddings.npz `
  --head mlp `
  --target-recall 0.90 `
  --out vision_classifier/fracture_classifier_v4.pkl `
  --metadata-out vision_classifier/fracture_classifier_v4.json
```

For the first real MLP pass, run a small CV hyperparameter search on the
training split before the final held-out test evaluation:

```powershell
python vision_classifier/scripts/train.py `
  --embeddings vision_classifier/data/fracatlas_medsiglip_embeddings.npz `
  --head mlp `
  --search `
  --search-iter 16 `
  --search-cv 3 `
  --search-scoring roc_auc `
  --target-recall 0.90 `
  --out vision_classifier/fracture_classifier_v4.pkl `
  --metadata-out vision_classifier/fracture_classifier_v4.json `
  --search-out vision_classifier/data/mlp_search_v4.csv
```

After validating metrics, either set `CLF_PATH` and `CLF_METADATA_PATH`, or
promote the new artifact by replacing the default `.pkl` and committing the
approved classifier head and metadata.

## Standalone Classifier API

This is optional; the main app uses `vision/vision_api.py`.

```powershell
cd vision_classifier/scripts
uvicorn api:app --reload --port 8001
```

`USE_EMBEDDING_CACHE=true` enables the old filename-cache lookup for local
debugging only.
