"""Handlers for vision inference operations."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from base.types import Framework
from base.encoding import bytes_to_hex, hex_to_bytes
from .config import (
    VERSION,
    OP_TYPE_VISION,
    OP_COMMAND_ANALYZE,
    OP_COMMAND_HEALTH,
    VISION_API_URL,
)


def register(framework: Framework) -> None:
    framework.handle(OP_TYPE_VISION, OP_COMMAND_ANALYZE, handle_analyze)
    framework.handle(OP_TYPE_VISION, OP_COMMAND_HEALTH,  handle_health)


def report_state() -> Any:
    return {"version": VERSION, "vision_api_url": VISION_API_URL}


def _post_json(url: str, payload: dict) -> bytes:
    data = json.dumps(payload).encode()
    req  = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def _get(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=10) as resp:
        return resp.read()


def handle_analyze(msg: str) -> tuple[str | None, int, str | None]:
    """Receive JSON with image_url, call vision API, return hex-encoded result."""
    try:
        payload = json.loads(hex_to_bytes(msg)) if msg else {}
    except (json.JSONDecodeError, ValueError) as e:
        return None, 0, f"invalid message: {e}"

    image_url = payload.get("image_url", "")
    if not image_url:
        return None, 0, "missing image_url in message"

    try:
        result = _post_json(f"{VISION_API_URL}/analyze-url", {"image_url": image_url})
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        return None, 0, f"vision API error {e.code}: {body}"
    except Exception as e:
        return None, 0, f"vision API unreachable: {e}"

    return bytes_to_hex(result), 1, None


def handle_health(msg: str) -> tuple[str | None, int, str | None]:
    """Proxy a health check to the vision API."""
    try:
        result = _get(f"{VISION_API_URL}/health")
    except Exception as e:
        return None, 0, f"vision API unreachable: {e}"
    return bytes_to_hex(result), 1, None
