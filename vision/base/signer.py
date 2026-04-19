"""TEE signing service — secp256k1 key management and response signing."""

from __future__ import annotations

import json
import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import coincurve

from .crypto import keccak256
from .encoding import bytes_to_hex, hex_to_bytes

logger = logging.getLogger(__name__)

_KEY_FILE = Path(os.environ.get("TEE_KEY_FILE", "tee_key.hex"))


def _load_or_generate() -> coincurve.PrivateKey:
    key_hex = os.environ.get("TEE_PRIVATE_KEY", "")
    if key_hex:
        return coincurve.PrivateKey(hex_to_bytes(key_hex.removeprefix("0x")))
    if _KEY_FILE.exists():
        return coincurve.PrivateKey(bytes.fromhex(_KEY_FILE.read_text().strip().removeprefix("0x")))
    key = coincurve.PrivateKey()
    _KEY_FILE.write_text(bytes_to_hex(key.secret))
    logger.info("Generated new TEE key — saved to %s", _KEY_FILE)
    return key


def _eth_address(key: coincurve.PrivateKey) -> str:
    pub_uncompressed = key.public_key.format(compressed=False)[1:]  # strip 0x04 prefix
    return "0x" + keccak256(pub_uncompressed)[-20:].hex()


class Signer:
    """Holds the TEE private key and signs byte payloads."""

    def __init__(self) -> None:
        self._key = _load_or_generate()
        self.address = _eth_address(self._key)
        logger.info("TEE address: %s", self.address)

    def sign(self, data: bytes) -> str:
        """Sign keccak256(data); return 0x-prefixed 65-byte recoverable signature."""
        digest = keccak256(data)
        sig = self._key.sign_recoverable(digest, hasher=None)
        return bytes_to_hex(sig)

    def sign_result(self, result_dict: dict) -> str:
        """Sign the canonical JSON encoding of a result dict."""
        payload = json.dumps(result_dict, sort_keys=True, separators=(",", ":")).encode()
        return self.sign(payload)

    def public_key_hex(self) -> str:
        return bytes_to_hex(self._key.public_key.format(compressed=False))

    def start_http(self, sign_port: str) -> None:
        """Start the signing HTTP service in a daemon thread."""
        signer_ref = self

        class _Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                if self.path == "/sign":
                    length = int(self.headers.get("Content-Length", 0))
                    body = json.loads(self.rfile.read(length))
                    sig = signer_ref.sign(hex_to_bytes(body["data"]))
                    self._json(200, {"signature": sig})
                else:
                    self.send_error(404)

            def do_GET(self) -> None:
                if self.path == "/pubkey":
                    self._json(200, {
                        "address": signer_ref.address,
                        "pubkey": signer_ref.public_key_hex(),
                    })
                else:
                    self.send_error(404)

            def _json(self, status: int, data: dict) -> None:
                body = json.dumps(data).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args: object) -> None:
                pass

        def _serve() -> None:
            srv = ThreadingHTTPServer(("", int(sign_port)), _Handler)
            logger.info("signer listening on port %s", sign_port)
            srv.serve_forever()

        threading.Thread(target=_serve, daemon=True, name="signer").start()
