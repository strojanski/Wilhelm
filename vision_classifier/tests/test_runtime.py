import json
import pickle
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from vision_classifier.runtime import FractureClassifier


class FakeInputs(dict):
    def to(self, device):
        self["device"] = device
        return self


class FakeProcessor:
    def __init__(self):
        self.calls = 0

    def __call__(self, images, return_tensors):
        self.calls += 1
        return FakeInputs({"pixel_values": FakeTensor([[0.0] for _ in images])})


class FakeTensor:
    def __init__(self, value):
        self.value = value

    def to(self, dtype):
        return self

    def float(self):
        return self

    def cpu(self):
        return self

    def numpy(self):
        return self.value


class FakeModel:
    def __init__(self):
        self.calls = 0

    def get_image_features(self, **inputs):
        self.calls += 1
        return FakeTensor([[0.25, 0.75]])


class FakeClassifier:
    def __init__(self):
        self.seen = []

    def predict_proba(self, embeddings):
        self.seen.append(embeddings)
        return [[0.2, 0.8]]


class FakeImage:
    def __init__(self):
        self.convert_calls = []

    def convert(self, mode):
        self.convert_calls.append(mode)
        return self


class RuntimeTests(unittest.TestCase):
    def test_unknown_filename_uses_encoder_for_real_time_prediction(self):
        processor = FakeProcessor()
        model = FakeModel()
        classifier = FakeClassifier()
        runtime = FractureClassifier(
            processor=processor,
            model=model,
            classifier=classifier,
            threshold=0.5,
            device="cpu",
            dtype=None,
        )

        image = FakeImage()
        result = runtime.predict(image, image_id="not-in-cache.jpg")

        self.assertEqual(result.prob_fracture, 0.8)
        self.assertTrue(result.predicted_fracture)
        self.assertEqual(processor.calls, 1)
        self.assertEqual(model.calls, 1)
        self.assertEqual(classifier.seen[0], [[0.25, 0.75]])
        self.assertEqual(image.convert_calls, ["RGB"])

    def test_cache_is_loaded_only_when_explicitly_enabled(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            cache_path = tmp_path / "embedding_cache.pkl"
            metadata_path = tmp_path / "classifier.json"

            with cache_path.open("wb") as f:
                pickle.dump({"cached.jpg": [1.0, 2.0]}, f)
            metadata_path.write_text(json.dumps({"threshold": 0.42}), encoding="utf-8")

            no_cache = FractureClassifier.from_components(
                processor=FakeProcessor(),
                model=FakeModel(),
                classifier=FakeClassifier(),
                metadata_path=metadata_path,
                cache_path=cache_path,
                use_cache=False,
            )
            with_cache = FractureClassifier.from_components(
                processor=FakeProcessor(),
                model=FakeModel(),
                classifier=FakeClassifier(),
                metadata_path=metadata_path,
                cache_path=cache_path,
                use_cache=True,
            )

        self.assertEqual(no_cache.threshold, 0.42)
        self.assertEqual(no_cache.cache_size, 0)
        self.assertEqual(with_cache.cache_size, 1)


if __name__ == "__main__":
    unittest.main()
