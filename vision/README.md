# Vision Backend

TEE extension server + FastAPI vision inference service for fracture detection.

## Folder structure

```
vision/
├── app/
│   ├── __init__.py
│   ├── config.py          # op types, commands, VISION_API_URL
│   └── handlers.py        # VISION/ANALYZE and VISION/HEALTH handlers
├── base/                  # TEE framework (server, types, encoding, crypto)
│   ├── server.py
│   ├── types.py
│   ├── encoding.py
│   └── crypto.py
├── models/                # ← CREATE THIS — put checkpoint files here
│   ├── vision_classifier/
│   │   ├── embedding_cache.pkl
│   │   └── fracture_classifier_v3_0.91auc.pkl
│   └── vision_segmentation/
│       ├── weights/
│       │   └── best.pt
│       └── SAM-Med2D/
│           ├── sam-med2d_b.pth
│           └── ... (SAM-Med2D source files)
├── vision_api.py          # FastAPI inference service (port 8000)
├── main.py                # TEE extension server (port 8080)
└── requirements.txt
```

## Checkpoint files to supply

| File | Description |
|------|-------------|
| `models/vision_classifier/embedding_cache.pkl` | Precomputed image embeddings |
| `models/vision_classifier/fracture_classifier_v3_0.91auc.pkl` | Trained LR classifier |
| `models/vision_segmentation/weights/best.pt` | YOLO detection weights |
| `models/vision_segmentation/SAM-Med2D/sam-med2d_b.pth` | SAM-Med2D checkpoint |
| `models/vision_segmentation/SAM-Med2D/` | SAM-Med2D source (clone from repo) |

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VISION_API_URL` | `http://localhost:8000` | Where the FastAPI service runs |
| `MODEL_ROOT` | parent of `vision/` | Root for model file resolution |
| `CACHE_PATH` | `$MODEL_ROOT/vision_classifier/embedding_cache.pkl` | Override cache path directly |
| `CLF_PATH` | `$MODEL_ROOT/vision_classifier/fracture_classifier_v3_0.91auc.pkl` | Override classifier path |
| `YOLO_WEIGHTS` | `$MODEL_ROOT/vision_segmentation/weights/best.pt` | Override YOLO weights path |
| `SAM_CHECKPOINT` | `$MODEL_ROOT/vision_segmentation/SAM-Med2D/sam-med2d_b.pth` | Override SAM checkpoint path |
| `SAM_SRC` | `$MODEL_ROOT/vision_segmentation/SAM-Med2D` | Override SAM source path |
| `FRACTURE_THRESHOLD` | `0.0853` | Classification decision threshold |
| `EXTENSION_PORT` | `8080` | TEE extension HTTP port |
| `SIGN_PORT` | `9090` | TEE signing port |

If you place checkpoints in `vision/models/`, set:

```bash
export MODEL_ROOT=/path/to/vision/models
```

## Setup

```bash
pip install -r requirements.txt
```

## Running

Start both services — the FastAPI service must be up before the TEE extension handles requests.

**Service 1 — Vision inference API (loads ML models)**
```bash
MODEL_ROOT=/path/to/vision/models uvicorn vision_api:app --port 8000
```

**Service 2 — TEE extension server**
```bash
python main.py
```

## Endpoints

### Via TEE extension (port 8080)

**POST /action** — `VISION / ANALYZE`

`originalMessage` must be a hex-encoded JSON string:
```json
{ "image_url": "https://example.com/xray.jpg" }
```

Response `data` field is hex-encoded JSON:
```json
{
  "segments": [
    { "ann_id": 0, "bbox": [x1, y1, x2, y2], "iou_score": 0.91, "mask_b64": "..." }
  ],
  "prob_fracture": 0.73,
  "predicted_fracture": true
}
```

**POST /action** — `VISION / HEALTH`

No payload needed. Returns hex-encoded JSON:
```json
{ "status": "ok", "device": "cuda", "threshold": 0.0853, "cached_embeddings": 1200 }
```

**GET /state**
```json
{ "stateVersion": "...", "state": { "version": "0.1.0", "vision_api_url": "http://localhost:8000" } }
```

### Directly via FastAPI (port 8000)

```
GET  /health
POST /analyze-url   body: { "image_url": "..." }
```
