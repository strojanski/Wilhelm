# RadiAI — Privacy-Preserving AI Radiology Triage

AI-powered bone fracture detection, segmentation, and clinical report generation.
All inference runs on **Flare confidential compute** — patient data is cryptographically protected.

**Pipeline:** Triage classifier → SAM-Med2D zero-shot segmentation → Gemma clinical report

---

## Replication — Step by Step

### 1. Clone the repo

```bash
git clone <repo-url>
cd vision_segmentation
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Unix / macOS
source .venv/bin/activate
```

### 3. Install PyTorch with CUDA

Check your CUDA driver version: `nvidia-smi` — look at the top-right number.

```bash
# CUDA 12.6 (adjust cu* to match your driver)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu126

# CPU-only fallback
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
```

### 4. Clone and register SAM-Med2D

SAM-Med2D has no `setup.py` — register it via a `.pth` file so Python can import it.

```bash
git clone https://github.com/OpenGVLab/SAM-Med2D
```

Find your venv site-packages path:
```bash
python -c "import site; print(site.getsitepackages()[0])"
```

Create a file called `sam_med2d.pth` in that directory containing the **absolute path** to the cloned repo:
```
C:\Users\you\...\vision_segmentation\SAM-Med2D
```

Then install the extra dependency:
```bash
pip install albumentations
```

### 5. Download the SAM-Med2D checkpoint

Download `sam-med2d_b.pth` from the [SAM-Med2D releases page](https://github.com/OpenGVLab/SAM-Med2D/releases) and place it at:
```
SAM-Med2D/sam-med2d_b.pth
```

### 6. Patch PyTorch 2.6+ compatibility

PyTorch 2.6 changed `torch.load` to default `weights_only=True`, which breaks the SAM-Med2D checkpoint loader. Open `SAM-Med2D/segment_anything/build_sam.py` and change:

```python
# Before
state_dict = torch.load(f, map_location="cpu")

# After
state_dict = torch.load(f, map_location="cpu", weights_only=False)
```

### 7. Install project dependencies

```bash
pip install -r requirements.txt
```

`requirements.txt` contents:
```
datasets>=2.0
torch>=2.0
torchvision
numpy
Pillow
matplotlib
tqdm
opencv-python-headless
albumentations
fastapi
uvicorn
pandas
python-multipart
```

### 8. Download FracAtlas

FracAtlas must be downloaded manually from [Kaggle](https://www.kaggle.com/datasets/bmadushanirodrigo/fracatlas) (CC-BY 4.0).

Expected directory structure after extraction:
```
data/FracAtlas/
  images/
    Fractured/         ← 717 X-rays with fractures
    Non_fractured/     ← 3,366 normal X-rays
  Annotations/
    COCO JSON/
      COCO_fracture_masks.json
  Utilities/
    Fracture Split/
      train.csv
      valid.csv
      test.csv
  dataset.csv
```

---

## Running the Pipeline

### Batch inference (offline evaluation)

```bash
cd scripts

# Run SAM-Med2D on all fractured images → data/FracAtlas/predictions/
python run_inference.py

# Evaluate IoU + Dice → stdout + data/FracAtlas/results.csv
python evaluate.py

# Visualize side-by-side overlays → data/FracAtlas/visualizations/
python visualize.py --n 20          # first 20
python visualize.py --all           # all images
python visualize.py --all --no-gt   # predictions only
```

### Interactive demo (web app)

```bash
cd scripts
uvicorn api:app --reload --port 8000
```

Open `frontend/index.html` directly in a browser (no build step needed).

The app will:
1. Run the triage classifier on load
2. Auto-detect fractures with SAM-Med2D (zero-shot, no GT prompts)
3. Allow GT vs AI comparison with live IoU
4. Let you draw a bounding box to probe any region
5. Generate a structured clinical report (Gemma stub — wire in your endpoint)

---

## Project Structure

```
vision_segmentation/
  scripts/
    api.py              ← FastAPI backend (SAM-Med2D + endpoints)
    run_inference.py    ← Batch inference on FracAtlas
    evaluate.py         ← IoU + Dice metrics
    visualize.py        ← Overlay visualizations
    download_data.py    ← HuggingFace dataset download helper
  frontend/
    index.html          ← Single-file web app, no build step
  SAM-Med2D/            ← Cloned (not committed)
  data/FracAtlas/       ← Downloaded manually (not committed)
  requirements.txt
  CLAUDE.md
```

---

## Wiring in Real Models

**Triage classifier** — replace the body of `classify()` in `scripts/api.py`:
```python
@app.post("/classify")
def classify(req: ClassifyRequest):
    # Replace stub with:
    img = load_image(req.image_id)
    result = your_classifier_model(img)
    return {"normal": ..., "urgency": ..., "confidence": ...}
```

**Gemma report** — replace `build_stub_report()` return value in `scripts/api.py`:
```python
# In generate_report():
prompt = build_report_prompt(req.image_id, req.patient, req.detections, req.triage)
# Replace stub with:
narrative = call_gemma_api(prompt, crop_b64=req.detections[0].get("crop_b64"))
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Server status, device, model loaded |
| GET | `/images` | List all available image IDs |
| GET | `/image/{id}` | X-ray image + metadata |
| POST | `/classify` | Triage: normal/abnormal, urgency |
| GET | `/presegment/{id}` | Zero-shot SAM-Med2D detection |
| GET | `/gt_overlay/{id}` | Radiologist GT mask overlay |
| POST | `/segment` | Probe a drawn bounding box |
| POST | `/report` | Generate clinical report (Gemma stub) |

---

## Key Technical Notes

- SAM-Med2D uses `image_size=256` and `encoder_adapter=True` — different from original SAM
- Use `SammedPredictor` (not `SamPredictor`) from `segment_anything.predictor_sammed`
- Model registry takes an `argparse.Namespace` object, not keyword args
- COCO bbox format is `[x, y, w, h]` — convert to `[x1, y1, x2, y2]` before passing to predictor
- `presegment` uses an 8×8 point grid + greedy NMS — no GT data used
