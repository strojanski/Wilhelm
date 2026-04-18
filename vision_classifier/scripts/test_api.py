"""Quick test for the classifier API.

Run from vision_classifier/scripts/:
    python test_api.py path\to\image.jpg
    python test_api.py path\to\image.jpg --show      # display overlay image
    python test_api.py path\to\image.jpg --true-label fractured
"""

import argparse
import base64
import io
import json
import urllib.request
from pathlib import Path

API_URL = "http://localhost:8001/classify"


def classify_image(image_path: Path, image_id: str = None, true_label: str = None) -> dict:
    b64 = base64.b64encode(image_path.read_bytes()).decode()
    payload = {"image_b64": b64}
    if image_id:
        payload["image_id"] = image_id
    if true_label:
        payload["true_label"] = true_label
    body = json.dumps(payload).encode()
    req = urllib.request.Request(API_URL, body, {"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read())


def show_overlay(overlay_b64: str):
    from PIL import Image
    import matplotlib.pyplot as plt
    img = Image.open(io.BytesIO(base64.b64decode(overlay_b64)))
    plt.figure(figsize=(6, 6))
    plt.imshow(img)
    plt.axis("off")
    plt.tight_layout()
    plt.show()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image", type=Path)
    ap.add_argument("--image-id",   default=None, help="filename key for cached embedding, e.g. IMG0000019.jpg")
    ap.add_argument("--show",       action="store_true", help="display overlay image")
    ap.add_argument("--true-label", choices=["fractured", "normal"], default=None)
    args = ap.parse_args()

    result = classify_image(args.image, image_id=args.image_id, true_label=args.true_label)

    print(f"\nImage               : {args.image.name}")
    print(f"P(fracture)         : {result['prob_fractured']:.4f}")
    print(f"Send to segmentation: {result['send_to_segmentation']}")

    if args.show:
        show_overlay(result["overlay_b64"])


if __name__ == "__main__":
    main()
