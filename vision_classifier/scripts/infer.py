"""Call the classifier API and show the annotated overlay.

Requires the API to be running:
    uvicorn api:app --reload --port 8001

Run from vision_classifier/scripts/:
    python infer.py --image ..\data\FracAtlas\FracAtlas\images\Fractured\IMG0000019.jpg
"""

import argparse
import base64
import io
import json
import urllib.request
from pathlib import Path

API_URL = "http://localhost:8001/classify"


def true_label_from_path(image: Path) -> str | None:
    parts = {p.lower() for p in image.parts}
    if "non_fractured" in parts:
        return "not fractured"
    if "fractured" in parts:
        return "fractured"
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", type=Path, required=True)
    args = ap.parse_args()

    image_id  = args.image.name
    true_label = true_label_from_path(args.image)

    b64     = base64.b64encode(args.image.read_bytes()).decode()
    payload = {"image_b64": b64, "image_id": image_id}
    if true_label:
        payload["true_label"] = true_label

    req  = urllib.request.Request(API_URL, json.dumps(payload).encode(),
                                  {"Content-Type": "application/json"})
    resp = json.loads(urllib.request.urlopen(req).read())

    print(f"\nImage               : {args.image.name}")
    print(f"P(fracture)         : {resp['prob_fractured']:.4f}")
    print(f"Send to segmentation: {resp['send_to_segmentation']}")

    from PIL import Image
    import matplotlib.pyplot as plt
    overlay = Image.open(io.BytesIO(base64.b64decode(resp["overlay_b64"])))
    plt.figure(figsize=(6, 6))
    plt.imshow(overlay)
    plt.axis("off")
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
