# Flare Network — RadiAI TEE Extension Deployment

## Architecture

```
Frontend
  │
  ▼
TEE Extension  (port 8080)  ←── Flare relay sends signed action requests
  │   Signer  (port 9090)   ←── HTTP signing service (secp256k1)
  │
  ▼
Vision API     (port 8000)  ←── FastAPI: YOLO + SAM-Med2D + LR classifier
```

Action flow: Flare relay → `POST /action` → TEE extension decodes opType/opCommand → calls Vision API → signs result → returns to relay.

---

## Prerequisites

- Docker + Docker Compose
- A secp256k1 private key for the TEE identity (generate one or reuse an existing EVM key)
- The TEE extension registered on the Flare network (one-time; see §4)

---

## 1. Environment

Create `.env` in the repo root (never commit this):

```env
# Required
TEE_PRIVATE_KEY=0x<64-hex-chars>

# Optional overrides
FLARE_RPC_URL=https://flare-api.flare.network/ext/C/rpc
REGISTRY_CONTRACT=0x<registry_contract_address>
EXTENSION_PORT=8080
SIGN_PORT=9090
FRACTURE_THRESHOLD=0.0853
```

To generate a fresh key:

```bash
python -c "import coincurve, secrets; k=coincurve.PrivateKey(secrets.token_bytes(32)); print('0x'+k.secret.hex())"
```

---

## 2. Build and Run

```bash
docker compose up --build -d
```

Services start in order: `vision-api` first (60 s model load), then `tee-extension` once the health check passes.

Check logs:

```bash
docker compose logs -f
```

Expected startup output:

```
vision-api      | Loading embedding cache …
vision-api      | Loading LR classifier …
vision-api      | Loading YOLO …
vision-api      | Loading SAM-Med2D on cpu …
vision-api      | All models loaded.
tee-extension   | TEE address: 0x<your_address>
tee-extension   | signer listening on port 9090
tee-extension   | extension listening on port 8080
```

---

## 3. Verify Services

```bash
# Vision API health
curl http://localhost:8000/health

# TEE extension state (includes TEE version)
curl http://localhost:8080/state

# Signer public key
curl http://localhost:9090/pubkey
```

Expected `/state` response:

```json
{
  "stateVersion": "0x...",
  "state": { "version": "0.1.0", "vision_api_url": "http://vision-api:8000" }
}
```

---

## 4. Register on Flare (one-time)

Install registration dependencies if running outside Docker:

```bash
pip install coincurve pycryptodome eth-abi
```

Run the registration script:

```bash
cd vision
FLARE_RPC_URL=https://flare-api.flare.network/ext/C/rpc \
REGISTRY_CONTRACT=0x<registry_contract_address> \
CALLER_PRIVATE_KEY=0x<key_paying_gas> \
TEE_PRIVATE_KEY=0x<tee_key> \
python scripts/register_flare.py
```

The script prints the TEE address and call data, does an `eth_call` dry-run, then prompts before broadcasting. If `eth-account` is not installed, it prints the equivalent `cast` command instead:

```bash
cast send <REGISTRY_CONTRACT> \
  'registerExtension(address,bytes)' \
  <tee_address> <tee_pubkey_hex> \
  --rpc-url https://flare-api.flare.network/ext/C/rpc \
  --private-key $CALLER_PRIVATE_KEY
```

---

## 5. Sending an Analyze Action

The Flare relay sends actions automatically once registered. To send one manually for testing:

```python
import json, urllib.request
import sys; sys.path.insert(0, 'vision')
from base.encoding import bytes_to_hex
from base.types import string_to_bytes32_hex

inner = {
    "instructionId": "0x01",
    "opType":        string_to_bytes32_hex("VISION"),
    "opCommand":     string_to_bytes32_hex("ANALYZE"),
    "originalMessage": bytes_to_hex(json.dumps({"image_url": "https://example.com/xray.jpg"}).encode()),
}
body = json.dumps({
    "data": {
        "id":            "req-1",
        "type":          "instruction",
        "submissionTag": "tag-1",
        "message":       bytes_to_hex(json.dumps(inner).encode()),
    }
}).encode()

req = urllib.request.Request("http://localhost:8080/action", data=body, headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req) as r:
    result = json.loads(r.read())

print(result)
# result["data"] is hex-encoded JSON: {"segments": [...], "prob_fracture": 0.73, ...}
# result["signature"] is the TEE's secp256k1 signature over the result
```

---

## 6. Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `TEE_PRIVATE_KEY` | — | TEE secp256k1 key (required for signed responses) |
| `TEE_KEY_FILE` | `tee_key.hex` | File to persist auto-generated key |
| `VISION_API_URL` | `http://localhost:8000` | Where FastAPI runs (set to `http://vision-api:8000` in Docker) |
| `MODEL_ROOT` | parent of `vision/` | Root for model file resolution |
| `FRACTURE_THRESHOLD` | `0.0853` | Classification decision threshold |
| `EXTENSION_PORT` | `8080` | TEE extension HTTP port |
| `SIGN_PORT` | `9090` | Signing service port |
| `FLARE_RPC_URL` | — | Flare JSON-RPC endpoint (registration only) |
| `REGISTRY_CONTRACT` | — | TEE registry contract address (registration only) |
| `CALLER_PRIVATE_KEY` | `TEE_PRIVATE_KEY` | Key paying gas for registration tx |
| `FLARE_CHAIN_ID` | `14` | Chain ID (14 = Flare mainnet, 114 = Coston2 testnet) |

---

## 7. Updating

```bash
docker compose down
docker compose up --build -d
```

No re-registration needed unless the TEE key changes.
