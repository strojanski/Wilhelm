import pickle
import torch
from pathlib import Path

MODEL_DIR   = Path(__file__).parent.parent / "medsiglip-448"
CLF_PATH    = Path(__file__).parent.parent / "fracture_classifier_v3_0.91auc.pkl"
CACHE_PATH  = Path(__file__).parent.parent / "embedding_cache.pkl"

_processor      = None
_model          = None
_clf            = None
_device         = None
_dtype          = None
_embedding_cache = {}   # {image_id: np.ndarray(1152,)}


def load_model(model_dir: Path = MODEL_DIR, clf_path: Path = CLF_PATH,
               cache_path: Path = CACHE_PATH):
    global _processor, _model, _clf, _device, _dtype, _embedding_cache

    _device = "cuda" if torch.cuda.is_available() else "cpu"
    _dtype  = torch.float16 if _device == "cuda" else torch.float32

    # Fast path: load pre-computed embedding cache
    if cache_path.exists():
        with open(cache_path, "rb") as f:
            _embedding_cache = pickle.load(f)
        print(f"Embedding cache: {len(_embedding_cache)} images (MedSigLIP not needed)")
    else:
        # Slow path: load full MedSigLIP encoder
        from transformers import AutoModel, AutoProcessor
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


def predict(pil_image, image_id: str = None) -> float:
    """Return P(fracture). Uses cached embedding if image_id is known, else runs MedSigLIP."""
    if image_id and image_id in _embedding_cache:
        emb = _embedding_cache[image_id].reshape(1, -1)
        return float(_clf.predict_proba(emb)[0, 1])
    return predict_batch([pil_image])[0]


def predict_batch(pil_images: list) -> list:
    """Run MedSigLIP + classifier on a list of PIL images (no cache)."""
    if _model is None:
        raise RuntimeError("MedSigLIP not loaded and no cache hit. Build the cache first: python build_cache.py")
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
