# Vision Backend

TEE extension server plus FastAPI vision inference service for fracture
classification and segmentation.

The production flow is:

1. Fetch the uploaded X-ray from the backend URL.
2. Embed the actual pixels with local MedSigLIP-448.
3. Score the embedding with the sklearn classifier head.
4. Run YOLO plus SAM-Med2D only when `prob_fracture >= threshold`.
5. Return the same Spring-compatible response shape: `prob_fracture`,
   `predicted_fracture`, and `segments`.

## Docker Build

MedSigLIP is downloaded into the image at build time with a BuildKit secret.
First accept the MedSigLIP terms on Hugging Face:

https://huggingface.co/google/medsiglip-448

Then build from the repository root:

```powershell
$env:HF_TOKEN = "hf_..."
docker compose up --build vision-api
```

The token is used as a build secret and is not copied into the final image.
The vision image installs CUDA PyTorch by default and Compose requests the
NVIDIA GPU for `vision-api`. Set `VISION_DEVICE=cpu` and
`TORCH_INDEX=https://download.pytorch.org/whl/cpu` only when you intentionally
want a CPU-only build/run.

## Runtime Artifacts

| Path | Description |
| --- | --- |
| `/app/vision_classifier/medsiglip-448/` | Baked MedSigLIP model snapshot |
| `/app/vision_classifier/fracture_classifier_v3_0.91auc.pkl` | Default classifier head |
| `/app/vision_classifier/fracture_classifier_v3_0.91auc.json` | Optional threshold/metrics metadata |
| `/app/vision_segmentation/weights/best.pt` | YOLO detection weights |
| `/app/vision_segmentation/SAM-Med2D/` | SAM-Med2D source and checkpoint |

## Environment Variables

| Variable | Default | Description |
| --- | --- | --- |
| `VISION_API_URL` | `http://localhost:8000` | Where the TEE extension calls the FastAPI service |
| `MODEL_ROOT` | parent of `vision/` | Root for model path resolution |
| `MEDSIGLIP_MODEL_DIR` | `$MODEL_ROOT/vision_classifier/medsiglip-448` | Local MedSigLIP model folder |
| `CLF_PATH` | `$MODEL_ROOT/vision_classifier/fracture_classifier_v3_0.91auc.pkl` | Classifier head path |
| `CLF_METADATA_PATH` | `CLF_PATH` with `.json` suffix | Optional threshold/metrics metadata |
| `CACHE_PATH` | `$MODEL_ROOT/vision_classifier/embedding_cache.pkl` | Optional debug cache path |
| `USE_EMBEDDING_CACHE` | `false` | Enables old filename embedding cache mode |
| `VISION_DEVICE` | `cuda` in Docker | `cuda` or `cpu`; fails fast if CUDA is requested but unavailable |
| `FRACTURE_THRESHOLD` | metadata threshold, else `0.0853` | Overrides classifier decision threshold |
| `YOLO_WEIGHTS` | `$MODEL_ROOT/vision_segmentation/weights/best.pt` | YOLO weights path |
| `SAM_CHECKPOINT` | `$MODEL_ROOT/vision_segmentation/SAM-Med2D/sam-med2d_b.pth` | SAM-Med2D checkpoint path |
| `SAM_SRC` | `$MODEL_ROOT/vision_segmentation/SAM-Med2D` | SAM-Med2D source path |

## Endpoints

Direct FastAPI service:

```text
GET  /health
POST /analyze-url   body: { "image_url": "..." }
```

Analyze response:

```json
{
  "segments": [
    { "ann_id": 0, "bbox": [x1, y1, x2, y2], "iou_score": 0.91, "mask_b64": "..." }
  ],
  "prob_fracture": 0.73,
  "predicted_fracture": true
}
```

TEE extension:

```text
POST /action   VISION / ANALYZE
POST /action   VISION / HEALTH
GET  /state
```
