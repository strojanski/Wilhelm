# X-Ray Anomaly Detection — Hackathon Setup

## Goal
Segment X-ray images and highlight anomalies across multiple body regions.
Main demo: chest. Supporting examples: hands, arms, legs.

---

## Model

**SAM-Med2D** — SAM with adapter layers trained on 4.6M medical image-mask pairs across 31 datasets. Better zero-shot performance than MedSAM on 2D medical images; adapter architecture makes fine-tuning cheap (freeze ViT backbone, train adapters + decoder only).

```bash
git clone https://github.com/OpenGVLab/SAM-Med2D
cd SAM-Med2D && pip install -e . && cd ..
```

- Checkpoint: download `sam-med2d_b.pth` from the repo releases
- Use zero-shot first. Fine-tune on HPC if zero-shot results are weak.

---

## Datasets

### Chest (main demo)

| Dataset | Size | Labels | Access |
|---|---|---|---|
| VinDr-CXR | ~18K images | 22 anomaly types, radiologist bounding boxes | [PhysioNet](https://physionet.org/content/vindr-cxr/1.0.0/) |
| CheXmask | 657K masks | Anatomical segmentation masks | [HuggingFace](https://huggingface.co/spaces/ngaggion/Chest-x-ray-HybridGNet-Segmentation) |

### Musculoskeletal (supporting examples)

| Dataset | Size | Labels | Access |
|---|---|---|---|
| FracAtlas | 4,083 images | Fracture masks + bboxes, hand/leg/hip/shoulder | [HuggingFace](https://huggingface.co/datasets/yh0701/FracAtlas_dataset) |
| MURA (Stanford) | ~40K images | Normal / abnormal, 7 body parts | [Stanford](https://stanfordmlgroup.github.io/competitions/mura/) |

> **FracAtlas** is CC-BY 4.0 and directly loadable via HuggingFace datasets — start here for non-chest examples.

---

## Suggested Project Structure

```
xray-hackathon/
├── data/
│   ├── vindrcxr/
│   ├── chexmask/
│   ├── fracatlas/
│   └── mura/
├── notebooks/
│   ├── 01_explore_vindrcxr.ipynb
│   ├── 02_explore_fracatlas.ipynb
│   └── 03_inference.ipynb
├── scripts/
│   ├── download_data.py        # via HuggingFace datasets
│   ├── run_inference.py        # zero-shot inference
│   ├── evaluate.py             # IoU + Dice metrics
│   └── visualize_masks.py      # overlay masks on images
├── SAM-Med2D/                  # cloned repo
└── README.md
```

---

## Quick Start: Load FracAtlas

```python
from datasets import load_dataset

ds = load_dataset("yh0701/FracAtlas_dataset")
print(ds)
```

## Quick Start: SAM-Med2D Inference

```python
import numpy as np
from segment_anything import sam_model_registry, SamPredictor

model = sam_model_registry["vit_b"](checkpoint="SAM-Med2D/sam-med2d_b.pth")
model.eval()
predictor = SamPredictor(model)

# Set image (H x W x 3, uint8)
predictor.set_image(image_np)

# Run inference with bounding box prompt [x_min, y_min, x_max, y_max]
bbox = np.array([[50, 50, 200, 200]])
masks, _, _ = predictor.predict(box=bbox, multimask_output=False)
mask = masks[0]  # H x W binary mask
```

---

## Next Steps (in order)

1. Load FracAtlas via HuggingFace, visualize a few images + masks
2. Run SAM-Med2D zero-shot on a bone X-ray (FracAtlas)
3. Run SAM-Med2D zero-shot on a chest X-ray (VinDr-CXR)
4. Compare zero-shot mask quality visually — fine-tune on HPC if needed