import pickle
import torch
from pathlib import Path
from transformers import AutoModel, AutoProcessor

MODEL_DIR = Path(__file__).parent.parent / "medsiglip-448"
CLF_PATH  = Path(__file__).parent.parent / "fracture_classifier_v3_0.91auc.pkl"

_processor = None
_model     = None
_clf       = None
_device    = None
_dtype     = None


def load_model(model_dir: Path = MODEL_DIR, clf_path: Path = CLF_PATH):
    global _processor, _model, _clf, _device, _dtype

    _device = "cuda" if torch.cuda.is_available() else "cpu"
    _dtype  = torch.float16 if _device == "cuda" else torch.float32

    print(f"Loading MedSigLIP from {model_dir} on {_device} ...")
    _processor = AutoProcessor.from_pretrained(model_dir)
    _model     = AutoModel.from_pretrained(model_dir, dtype=_dtype).to(_device)
    _model.eval()

    print(f"Loading classifier from {clf_path} ...")
    try:
        import joblib
        _clf = joblib.load(clf_path)
    except Exception:
        with open(clf_path, "rb") as f:
            _clf = pickle.load(f)

    print("Ready.\n")


def predict(pil_image) -> float:
    """Return P(fracture) for a single PIL image. Call load_model() first."""
    if _model is None:
        raise RuntimeError("Call load_model() first.")
    return predict_batch([pil_image])[0]


def predict_batch(pil_images: list) -> list:
    """Return list of P(fracture) for a list of PIL images."""
    if _model is None:
        raise RuntimeError("Call load_model() first.")
    imgs   = [img.convert("RGB") for img in pil_images]
    inputs = _processor(images=imgs, return_tensors="pt").to(_device)
    inputs["pixel_values"] = inputs["pixel_values"].to(_dtype)
    with torch.no_grad():
        out = _model.get_image_features(**inputs)
        if hasattr(out, "pooler_output"):
            out = out.pooler_output
        elif not isinstance(out, torch.Tensor):
            out = out[0]
        emb = out.float().cpu().numpy()
    return _clf.predict_proba(emb)[:, 1].tolist()
