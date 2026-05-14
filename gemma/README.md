# Local Gemma 4 — Docker + OpenAI-Compatible API

Run any Gemma 4 variant on your machine, behind an authenticated
OpenAI-compatible endpoint. Switch models by editing a single line in `.env`.

## Files

```
gemma-local/
├── docker-compose.yml   # Ollama + Caddy auth proxy + one-shot model puller
├── Caddyfile            # Bearer-token check, forwards to Ollama
├── .env.example         # Copy to .env and edit
└── README.md
```

## Prerequisites

1. **Docker** + **Docker Compose v2** installed.
2. **GPU passthrough**:
   - **Linux**: install `nvidia-container-toolkit`
     ```bash
     sudo apt install -y nvidia-container-toolkit
     sudo systemctl restart docker
     ```
   - **Windows**: Docker Desktop on WSL2 — make sure "Use the WSL 2 based engine"
     is on and you have a recent NVIDIA driver. GPU works automatically.
3. **Ollama 0.20+** image (the `latest` tag is fine — Gemma 4 vision needs ≥0.20).

Confirm GPU is visible to Docker:
```bash
docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi
```

## Setup

```bash
cp .env.example .env
# Edit .env — at minimum set LLM_API_KEY to a long random string.
# Optionally change LLM_MODEL to pick a different size.
docker compose up -d
```

The first run pulls the model (several GB) — watch progress with:
```bash
docker compose logs -f model-init
```

When that container exits with "Model ready." you're done.

## Test it

```bash
# List models exposed via the OpenAI surface
curl -s http://localhost:8084/v1/models \
  -H "Authorization: Bearer $(grep LLM_API_KEY .env | cut -d= -f2)"

# Chat completion
curl -s http://localhost:8084/v1/chat/completions \
  -H "Authorization: Bearer $(grep LLM_API_KEY .env | cut -d= -f2)" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemma4:26b",
    "messages": [{"role":"user","content":"Say hi in one short sentence."}]
  }'
```

Without the header you get `401 unauthorized` — proves the auth works.

## Using it from another app

The three variables in your `.env` are exactly the ones your other app
already expects:

```dotenv
LLM_BASE_URL=http://localhost:8084/v1
LLM_API_KEY=<the long random string you chose>
LLM_MODEL=gemma4:26b
```

Drop those into the consuming app's `.env` and it will hit your local Gemma
the same way it hits Gemini. If the consuming app runs in another container
on the same Docker network, use `http://proxy:8080/v1` (container port)
instead of `localhost`.

## Switching models

```bash
# 1. Edit LLM_MODEL in .env, e.g. gemma4:31b
# 2. Recreate the services — this re-runs the puller for the new model.
docker compose up -d --force-recreate
```

You can keep multiple models on disk; only one is loaded at a time. To
preload several, run `docker exec ollama ollama pull gemma4:e4b` etc.

## Vision input

Multimodal works through the same endpoint. With the OpenAI SDK:

```python
import base64, os
from openai import OpenAI

client = OpenAI(base_url=os.environ["LLM_BASE_URL"],
                api_key=os.environ["LLM_API_KEY"])

b64 = base64.b64encode(open("photo.jpg","rb").read()).decode()

resp = client.chat.completions.create(
    model=os.environ["LLM_MODEL"],
    messages=[{
        "role": "user",
        "content": [
            {"type": "image_url",
             "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            {"type": "text", "text": "What's in this image?"},
        ],
    }],
)
print(resp.choices[0].message.content)
```

## Operations

```bash
docker compose ps              # status
docker compose logs -f ollama  # server logs
docker exec ollama ollama ps   # currently-loaded model & VRAM usage
docker compose down            # stop everything (data persists in volumes)
docker compose down -v         # stop and delete model weights too
```

## Notes

- The Caddy proxy enforces the API key. **Do not** publish port 11434 directly
  — Ollama has no built-in auth.
- For LAN access: in `.env` set `LLM_BASE_URL=http://<host-ip>:8083/v1`. The
  Caddy auth still protects it. For internet exposure, put a TLS-terminating
  proxy in front (Caddy can do this with one extra line if you have a domain).
- `OLLAMA_FLASH_ATTENTION=1` is enabled by default — turn it off in the compose
  file if you hit issues on older drivers.
