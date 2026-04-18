"""
Test the full YOLO → SAM-Med2D pipeline on a single image.
Saves a side-by-side visualization to pipeline_test_output.jpg.

Run from scripts/:
    python test_pipeline.py
    python test_pipeline.py --image IMG0000019
"""

import argparse
import argparse as ap
import sys
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image
from ultralytics import YOLO

DATA_DIR   = Path("../data/FracAtlas")
IMG_DIRS   = [DATA_DIR / "images/Fractured", DATA_DIR / "images/Non_fractured"]
CHECKPOINT = Path("../SAM-Med2D/sam-med2d_b.pth")
WEIGHTS    = Path("../weights/best.pt")
DEVICE     = "cuda" if torch.cuda.is_available() else "cpu"


def find_image(stem: str):
    for d in IMG_DIRS:
        for ext in [".jpg", ".jpeg", ".png"]:
            p = d / f"{stem}{ext}"
            if p.exists():
                return p
    return None


def load_sam():
    from segment_anything import sam_model_registry
    from segment_anything.predictor_sammed import SammedPredictor
    args = ap.Namespace(image_size=256, sam_checkpoint=str(CHECKPOINT), encoder_adapter=True)
    model = sam_model_registry["vit_b"](args)
    model.eval()
    model.to(DEVICE)
    return SammedPredictor(model)


def run(image_stem: str):
    img_path = find_image(image_stem)
    if not img_path:
        sys.exit(f"Image '{image_stem}' not found in {IMG_DIRS}")

    img = np.array(Image.open(img_path).convert("RGB"))
    H, W = img.shape[:2]
    print(f"Image: {img_path}  ({W}×{H})")

    # ── YOLO detection ──────────────────────────────────────────────────────────
    print(f"Loading YOLO from {WEIGHTS} …")
    yolo = YOLO(str(WEIGHTS))
    yolo_res = yolo.predict(img, conf=0.25, verbose=False)[0]
    boxes = yolo_res.boxes.xyxy.cpu().numpy() if len(yolo_res.boxes) else []
    confs = yolo_res.boxes.conf.cpu().numpy() if len(yolo_res.boxes) else []
    print(f"YOLO: {len(boxes)} detection(s)")

    # ── SAM segmentation ────────────────────────────────────────────────────────
    print(f"Loading SAM-Med2D on {DEVICE} …")
    predictor = load_sam()

    COLORS = [
        [255, 60,  60],
        [60,  160, 255],
        [255, 180, 0],
        [60,  220, 100],
    ]

    composite = img.copy()
    masks_out = []

    with torch.no_grad():
        predictor.set_image(img)

        if len(boxes) == 0:
            print("No YOLO detections — falling back to full-image bbox")
            boxes = [[0, 0, W, H]]
            confs = [0.0]

        for i, (box, conf) in enumerate(zip(boxes, confs)):
            x1, y1, x2, y2 = map(float, box[:4])
            masks, scores, _ = predictor.predict(
                box=np.array([x1, y1, x2, y2]),
                multimask_output=True,
            )
            best  = int(np.argmax(scores))
            mask  = masks[best].astype(np.uint8)
            score = float(scores[best])
            color = COLORS[i % len(COLORS)]

            region = mask.astype(bool)
            composite[region] = (0.4 * np.array(color) + 0.6 * img[region]).astype(np.uint8)
            cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(composite, cnts, -1, tuple(color), max(2, H // 400))

            # draw YOLO bbox
            cv2.rectangle(composite, (int(x1), int(y1)), (int(x2), int(y2)), tuple(color), 2)
            label = f"det {i+1}  yolo:{conf:.2f}  sam:{score:.2f}"
            cv2.putText(composite, label, (int(x1), max(int(y1)-6, 12)),
                        cv2.FONT_HERSHEY_SIMPLEX, max(0.4, H/3000), tuple(color), 1, cv2.LINE_AA)

            masks_out.append(mask)
            print(f"  Region {i+1}: YOLO conf={conf:.3f}  SAM score={score:.3f}  "
                  f"area={mask.sum()/(H*W)*100:.1f}%")

    # ── Save output ─────────────────────────────────────────────────────────────
    side_by_side = np.concatenate([img, composite], axis=1)
    out_path = Path("pipeline_test_output.jpg")
    Image.fromarray(side_by_side).save(out_path, quality=90)
    print(f"\nSaved: {out_path.resolve()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", default="IMG0000019", help="Image stem to test")
    args = parser.parse_args()
    run(args.image)
