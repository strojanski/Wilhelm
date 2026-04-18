# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

X-ray anomaly detection hackathon project. Segments X-ray images and highlights anomalies using **SAM-Med2D** — SAM with adapter layers pretrained on 4.6M medical image-mask pairs. Better zero-shot performance than MedSAM on 2D medical images; adapter architecture makes fine-tuning cheap (freeze ViT backbone, train adapters + decoder only).

## Environment Setup

```bash
# Activate virtual environment
.venv\Scripts\activate   # Windows
source .venv/bin/activate  # Unix

# Install SAM-Med2D (clone into project root)
git clone https://github.com/OpenGVLab/SAM-Med2D
cd SAM-Med2D && pip install -e . && cd ..

# Install project dependencies
pip install -r requirements.txt

# Download checkpoint: sam-med2d_b.pth from SAM-Med2D GitHub releases
# Place at: SAM-Med2D/sam-med2d_b.pth
```

## Running the Pipeline

```bash
python scripts/download_data.py   # Download FracAtlas → data/fracatlas/
python scripts/run_inference.py   # Run SAM-Med2D → data/fracatlas/*/predictions/
python scripts/evaluate.py        # IoU + Dice → stdout + data/fracatlas/results.csv
```

## Running Notebooks

```bash
jupyter notebook
```

## Architecture

**Model:** SAM-Med2D (`SAM-Med2D/` cloned repo + `sam-med2d_b.pth` checkpoint). Uses `SamPredictor` interface — bounding-box prompt → segmentation mask. Internally adds adapter layers to each ViT block; backbone stays frozen during fine-tuning.

**Datasets:**
- `FracAtlas` — HuggingFace (`yh0701/FracAtlas_dataset`), CC-BY 4.0, start here
- `VinDr-CXR` — PhysioNet, 18K chest X-rays with 22 anomaly bounding box labels
- `CheXmask` — 657K anatomical segmentation masks
- `MURA` — Stanford, 40K musculoskeletal images, normal/abnormal labels

**Scripts:**
```
scripts/download_data.py    # HuggingFace → data/fracatlas/{split}/{images,masks,annotations.json}
scripts/run_inference.py    # SAM-Med2D inference → data/fracatlas/{split}/predictions/
scripts/evaluate.py         # IoU + Dice → data/fracatlas/results.csv
```

## Key Patterns

SAM-Med2D uses the standard `SamPredictor` interface:

```python
from segment_anything import sam_model_registry, SamPredictor

model = sam_model_registry["vit_b"](checkpoint="SAM-Med2D/sam-med2d_b.pth")
model.eval()
predictor = SamPredictor(model)

predictor.set_image(image_np)  # H x W x 3, uint8
masks, _, _ = predictor.predict(box=np.array([[x_min, y_min, x_max, y_max]]), multimask_output=False)
mask = masks[0]  # H x W binary
```
