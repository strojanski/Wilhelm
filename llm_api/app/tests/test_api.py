"""End-to-end smoke test against a running API container.

Usage:
    python tests/test_api.py                          # uses http://localhost:8080
    python tests/test_api.py --url http://host:8080   # custom host
    python tests/test_api.py --skip-transcribe        # skip STT test
    python tests/test_api.py --image path/to/img.png --pdf path/to/doc.pdf
    python tests/test_api.py --audio path/to/clip.wav

This does NOT mock anything - it actually hits the API, which in turn hits
your configured LLM backend (vLLM, Gemini, etc.). Make sure the API is
running and the .env points at a reachable model.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

import httpx


def _print_header(title: str) -> None:
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


def test_health(client: httpx.Client) -> None:
    _print_header("GET /health")
    r = client.get("/health")
    print(f"status={r.status_code}")
    print(json.dumps(r.json(), indent=2))
    r.raise_for_status()


def test_analyze_text_only(client: httpx.Client) -> None:
    _print_header("POST /analyze  (text only)")
    r = client.post(
        "/analyze",
        data={
            "text": (
                "Our Q3 revenue grew 18% year-over-year, driven by strong "
                "performance in the enterprise segment. Churn rose slightly "
                "in the SMB tier."
            ),
            "category": "finance",
            "user_id": "user-123",
            "metadata_json": json.dumps({"source": "earnings_call", "quarter": "Q3"}),
        },
        timeout=120,
    )
    print(f"status={r.status_code}")
    try:
        print(json.dumps(r.json(), indent=2))
    except Exception:
        print(r.text)
    r.raise_for_status()


def test_analyze_with_files(
    client: httpx.Client,
    image_path: Path | None,
    pdf_path: Path | None,
    audio_path: Path | None,
) -> None:
    if not image_path and not pdf_path and not audio_path:
        print(
            "\n(skipping file-upload test: pass --image, --pdf, and/or --audio to enable)"
        )
        return

    _print_header("POST /analyze  (with attachments)")
    files: list[tuple[str, tuple[str, bytes, str]]] = []
    if image_path:
        files.append(
            ("image", (image_path.name, image_path.read_bytes(), _guess_image_mime(image_path)))
        )
    if pdf_path:
        files.append(("pdf", (pdf_path.name, pdf_path.read_bytes(), "application/pdf")))
    if audio_path:
        files.append(
            (
                "audio",
                (
                    audio_path.name,
                    audio_path.read_bytes(),
                    _guess_audio_mime(audio_path),
                ),
            )
        )

    r = client.post(
        "/analyze",
        data={
            "text": "Please analyze the attached materials and summarize.",
            "category": "mixed",
        },
        files=files,
        timeout=180,
    )
    print(f"status={r.status_code}")
    try:
        print(json.dumps(r.json(), indent=2))
    except Exception:
        print(r.text)
    r.raise_for_status()


def test_transcribe(client: httpx.Client, audio_path: Path | None) -> None:
    if audio_path is None:
        # Generate a 1-second silent WAV so we at least hit the endpoint.
        audio_bytes = _silent_wav_1sec()
        filename = "silence.wav"
        print("\n(no --audio given; sending 1s of silence just to exercise the endpoint)")
    else:
        audio_bytes = audio_path.read_bytes()
        filename = audio_path.name

    _print_header("POST /transcribe")
    r = client.post(
        "/transcribe",
        files={"audio": (filename, audio_bytes, "audio/wav")},
        timeout=120,
    )
    print(f"status={r.status_code}")
    try:
        print(json.dumps(r.json(), indent=2))
    except Exception:
        print(r.text)
    # don't raise - STT creds may not be configured; just show result.


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _guess_image_mime(p: Path) -> str:
    ext = p.suffix.lower()
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(ext, "application/octet-stream")


def _guess_audio_mime(p: Path) -> str:
    ext = p.suffix.lower()
    return {
        ".wav": "audio/wav",
        ".mp3": "audio/mpeg",
        ".m4a": "audio/mp4",
        ".ogg": "audio/ogg",
        ".flac": "audio/flac",
        ".weba": "audio/webm",
    }.get(ext, "application/octet-stream")


def _silent_wav_1sec() -> bytes:
    """Minimal 1-second silent PCM WAV, 16kHz mono 16-bit."""
    import struct
    import wave

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(struct.pack("<" + "h" * 16000, *([0] * 16000)))
    return buf.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8080")
    parser.add_argument("--image", type=Path, default=None)
    parser.add_argument("--pdf", type=Path, default=None)
    parser.add_argument("--audio", type=Path, default=None)
    parser.add_argument("--skip-transcribe", action="store_true")
    parser.add_argument("--skip-analyze", action="store_true")
    args = parser.parse_args()

    with httpx.Client(base_url=args.url) as client:
        test_health(client)
        if not args.skip_analyze:
            test_analyze_text_only(client)
            test_analyze_with_files(client, args.image, args.pdf, args.audio)
        if not args.skip_transcribe:
            test_transcribe(client, args.audio)

    print("\n✅ All requested tests completed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
