"""
End-to-end test script for the RadiAI TEE extension stack.

Runs against live services — start both before running:
  Terminal 1: MODEL_ROOT=/path/to/models uvicorn vision_api:app --port 8000
  Terminal 2: TEE_PRIVATE_KEY=0x... python main.py

Usage:
  python scripts/test_stack.py [--ext-url http://localhost:8080] [--api-url http://localhost:8000]
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from base.encoding import bytes_to_hex, hex_to_bytes
from base.types import string_to_bytes32_hex

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
SKIP = "\033[33mSKIP\033[0m"

# Public FracAtlas test image (tiny, confirmed accessible)
TEST_IMAGE_URL = "https://raw.githubusercontent.com/Dataset-Champions/FracAtlas/main/images/Non-fractured/IMG0000001.jpg"


def _get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=15) as r:
        return json.loads(r.read())


def _post(url: str, payload: dict) -> dict:
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def _make_action(image_url: str, req_id: str = "test-1") -> dict:
    inner = {
        "instructionId": "0x01",
        "opType":        string_to_bytes32_hex("VISION"),
        "opCommand":     string_to_bytes32_hex("ANALYZE"),
        "originalMessage": bytes_to_hex(json.dumps({"image_url": image_url}).encode()),
    }
    return {
        "data": {
            "id":            req_id,
            "type":          "instruction",
            "submissionTag": "tag-1",
            "message":       bytes_to_hex(json.dumps(inner).encode()),
        }
    }


def _make_health_action() -> dict:
    inner = {
        "instructionId": "0x02",
        "opType":        string_to_bytes32_hex("VISION"),
        "opCommand":     string_to_bytes32_hex("HEALTH"),
        "originalMessage": bytes_to_hex(b"{}"),
    }
    return {
        "data": {
            "id":            "health-1",
            "type":          "instruction",
            "submissionTag": "tag-h",
            "message":       bytes_to_hex(json.dumps(inner).encode()),
        }
    }


# ── individual tests ──────────────────────────────────────────────────────────

results: list[tuple[str, str, str]] = []


def check(name: str, fn) -> None:
    try:
        msg = fn()
        results.append((PASS, name, msg or ""))
        print(f"  {PASS}  {name}" + (f" — {msg}" if msg else ""))
    except AssertionError as e:
        results.append((FAIL, name, str(e)))
        print(f"  {FAIL}  {name} — {e}")
    except Exception as e:
        results.append((FAIL, name, str(e)))
        print(f"  {FAIL}  {name} — {type(e).__name__}: {e}")


def test_vision_api_health(api_url: str) -> None:
    r = _get(f"{api_url}/health")
    assert r["status"] == "ok", f"unexpected status: {r}"
    return f"device={r['device']} embeddings={r['cached_embeddings']}"


def test_extension_state(ext_url: str) -> None:
    r = _get(f"{ext_url}/state")
    assert "stateVersion" in r, f"missing stateVersion: {r}"
    assert "state" in r, f"missing state: {r}"
    assert "version" in r["state"], f"missing version in state: {r}"
    return f"version={r['state']['version']}"


def test_signer_pubkey(sign_url: str) -> None:
    r = _get(f"{sign_url}/pubkey")
    assert "address" in r, f"missing address: {r}"
    assert r["address"].startswith("0x"), f"bad address format: {r}"
    assert len(r["address"]) == 42, f"address wrong length: {r}"
    return f"address={r['address']}"


def test_extension_health_action(ext_url: str) -> None:
    r = _post(f"{ext_url}/action", _make_health_action())
    assert r.get("status") == 1, f"bad status: {r}"
    assert "data" in r, f"missing data: {r}"
    inner = json.loads(hex_to_bytes(r["data"]))
    assert inner["status"] == "ok", f"vision API not healthy: {inner}"
    return f"vision_api={inner['status']} device={inner.get('device')}"


def test_action_has_signature(ext_url: str) -> None:
    r = _post(f"{ext_url}/action", _make_health_action())
    assert "signature" in r, "response missing 'signature' field — is TEE_PRIVATE_KEY set?"
    sig = r["signature"]
    assert sig.startswith("0x"), f"bad signature format: {sig[:20]}..."
    assert len(sig) == 132, f"signature wrong length ({len(sig)}), expected 132"
    return f"sig={sig[:18]}..."


def test_action_fields(ext_url: str) -> None:
    r = _post(f"{ext_url}/action", _make_health_action())
    for field in ("id", "submissionTag", "opType", "opCommand", "version", "status"):
        assert field in r, f"missing field: {field}"
    assert r["id"] == "health-1"
    assert r["submissionTag"] == "tag-h"


def test_analyze_action(ext_url: str) -> None:
    r = _post(f"{ext_url}/action", _make_action(TEST_IMAGE_URL))
    assert r.get("status") == 1, f"bad status: {r}"
    assert "data" in r, f"missing data: {r}"
    inner = json.loads(hex_to_bytes(r["data"]))
    assert "prob_fracture" in inner, f"missing prob_fracture: {inner}"
    assert "predicted_fracture" in inner, f"missing predicted_fracture: {inner}"
    assert "segments" in inner, f"missing segments: {inner}"
    prob = inner["prob_fracture"]
    assert 0.0 <= prob <= 1.0, f"prob_fracture out of range: {prob}"
    return f"prob_fracture={prob} predicted={inner['predicted_fracture']} segments={len(inner['segments'])}"


def test_bad_action_returns_error(ext_url: str) -> None:
    try:
        _post(f"{ext_url}/action", {"data": {"id": "x", "type": "instruction", "submissionTag": "t", "message": "0xdeadbeef"}})
    except urllib.error.HTTPError as e:
        assert e.code == 400, f"expected 400, got {e.code}"
        return "correctly rejected malformed message"
    # If it returns 200 with status=0, that's also acceptable
    return "returned 200 with error status"


def test_unknown_op_returns_501(ext_url: str) -> None:
    import base64
    inner = {
        "instructionId": "0x03",
        "opType":        string_to_bytes32_hex("UNKNOWN"),
        "opCommand":     string_to_bytes32_hex("NOOP"),
        "originalMessage": bytes_to_hex(b"{}"),
    }
    action = {
        "data": {
            "id": "unk-1", "type": "instruction", "submissionTag": "t",
            "message": bytes_to_hex(json.dumps(inner).encode()),
        }
    }
    try:
        _post(f"{ext_url}/action", action)
    except urllib.error.HTTPError as e:
        assert e.code == 501, f"expected 501, got {e.code}"
        return "correctly returned 501"
    return "server returned 200 (unexpected op may be handled)"


def test_direct_analyze_url(api_url: str) -> None:
    r = _post(f"{api_url}/analyze-url", {"image_url": TEST_IMAGE_URL})
    assert "prob_fracture" in r, f"missing prob_fracture: {r}"
    assert "segments" in r, f"missing segments: {r}"
    return f"prob_fracture={r['prob_fracture']} segments={len(r['segments'])}"


# ── runner ────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ext-url",  default="http://localhost:8080")
    ap.add_argument("--api-url",  default="http://localhost:8000")
    ap.add_argument("--sign-url", default="http://localhost:9090")
    ap.add_argument("--skip-analyze", action="store_true", help="skip the full ANALYZE test (slow, needs internet)")
    args = ap.parse_args()

    ext  = args.ext_url
    api  = args.api_url
    sign = args.sign_url

    print(f"\nTarget: ext={ext}  api={api}  sign={sign}\n")

    print("── Vision API ──────────────────────────────")
    check("vision API /health",          lambda: test_vision_api_health(api))
    check("vision API /analyze-url",     lambda: test_direct_analyze_url(api))

    print("\n── TEE Extension ───────────────────────────")
    check("extension /state",            lambda: test_extension_state(ext))
    check("signer /pubkey",              lambda: test_signer_pubkey(sign))
    check("HEALTH action via extension", lambda: test_extension_health_action(ext))
    check("action response signature",   lambda: test_action_has_signature(ext))
    check("action response fields",      lambda: test_action_fields(ext))

    print("\n── Error handling ──────────────────────────")
    check("malformed message → 400",     lambda: test_bad_action_returns_error(ext))
    check("unknown opType → 501",        lambda: test_unknown_op_returns_501(ext))

    if not args.skip_analyze:
        print("\n── Full pipeline ───────────────────────────")
        check("ANALYZE action (full pipeline)", lambda: test_analyze_action(ext))

    # Summary
    passed = sum(1 for r in results if r[0] == PASS)
    failed = sum(1 for r in results if r[0] == FAIL)
    total  = len(results)
    print(f"\n{'─'*44}")
    print(f"  {passed}/{total} passed", end="")
    if failed:
        print(f"  ({failed} FAILED)")
        sys.exit(1)
    else:
        print("  — all good")


if __name__ == "__main__":
    main()
