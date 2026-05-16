# Wilhelm — ER X-ray to clinical report in seconds, powered by Gemma 4

> **The Gemma 4 Good Hackathon** · Health track · One command to run · 100% local, private inference

Think about the last time you went to the emergency room. The one thing every ER visit has in common is *the waiting*. Wilhelm cuts the time from X-ray to a draft clinical report from hours to **seconds** — running a four-stage medical-imaging pipeline with **Gemma 4** as the multimodal reasoning core, entirely on local hardware so no patient data ever leaves the building.

---

## Submission

| | |
|---|---|
| 🎥 **Demo video** | `<TODO: add video URL before submission>` |
| 🌐 **Live demo** | `<TODO: add live demo URL before submission>` |
| 📝 **Kaggle writeup** | `<TODO: add Kaggle writeup URL before submission>` |
| 📦 **Code repository** | this repo |
| 🗓️ **Final submission deadline** | May 18, 2026 (11:59 PM UTC) |

---

## The problem

Emergency departments are bottlenecked on triage and radiology turnaround. A patient with a suspected fracture waits while images are queued, read, and written up. Most of that time is not treatment — it is administrative latency. Wilhelm collapses that latency: upload the X-ray, and within seconds a clinician sees a localized fracture assessment and a structured, editable draft report ready for sign-off.

This build focuses on **bone fractures**, but the architecture generalizes to other imaging domains.

## What Wilhelm does

An X-ray moves through four stages:

```
  X-ray upload
        │
        ▼
  1. CLASSIFY   ── MedSigLIP-448 embeddings + Logistic Regression
        │           "Is there a fracture?"  (0.91 AUC, recall-tuned)
        ▼
  2. DETECT     ── YOLOv8 (fine-tuned on FracAtlas)
        │           "Where is it?"  → bounding boxes
        ▼
  3. SEGMENT    ── SAM-Med2D (medical Segment Anything, ViT-B)
        │           "Exactly which pixels?"  → masks + IoU
        ▼
  4. REASON     ── Gemma 4 (multimodal: image + voice + notes + PDF)
        │           → structured Emergency Department report
        ▼
  Clinician reviews, corrects, exports PDF
```

The clinician stays in the loop: AI detections are shown as overlays that can be corrected before a report is generated.

## Why Gemma 4

Gemma 4 is the reasoning engine that turns vision output and clinician input into a usable clinical document.

- **Truly multimodal.** A single `/analyze` call fuses the **X-ray image**, a **dictated voice note**, typed **doctor notes**, and a prior **triage PDF** into one Emergency Department report. The content is assembled in image → audio → text order, following Gemma multimodal best practice (`llm_api/app/services/llm_service.py`).
- **100% local and private.** Gemma 4 runs via **Ollama** behind an OpenAI-compatible Caddy proxy. No PHI is sent to a third-party API — a hard requirement for real healthcare deployment and the core of our "for good" story.
- **Scales to the hardware you have.** Pick the variant in `gemma/.env`:

  | Variant | Size | Notes |
  |---|---|---|
  | `gemma4:e2b` | ~2 GB | Fastest, lowest VRAM |
  | `gemma4:e4b` | ~4 GB | Edge-class quality — **default** |
  | `gemma4:26b` | ~16 GB | Mixture-of-Experts, great on a 24 GB GPU |
  | `gemma4:31b` | ~20 GB | Dense, maximum quality |

- **Provider-portable.** Because the interface is OpenAI-compatible, the exact same code runs against local Ollama or a hosted Gemma 4 endpoint with zero code changes — only environment variables differ.

A 931-line clinical system prompt (`llm_api/app/services/system_prompt.py`) constrains Gemma 4 to a fixed Emergency Department report template and forbids fabricating identifiers or measurements.

## Quick start

The entire stack — database, backend, vision pipeline, Gemma 4, and UI — comes up with **one command from the repo root**:

```bash
git clone <this-repo> && cd Wilhelm
docker compose up --build
```

Then open **http://localhost:5173**.

**First run** pulls the Gemma 4 model (`gemma4:e4b`, ~4 GB) and clones + downloads the SAM-Med2D checkpoint, so the initial build takes a while; subsequent starts are fast (models are cached in Docker volumes).

**GPU vs CPU.** The vision images install CPU-only PyTorch by default. For CUDA, rebuild with:

```bash
docker compose build --build-arg TORCH_INDEX=https://download.pytorch.org/whl/cu121
```

An NVIDIA GPU is recommended for Gemma 4 inference latency (the `ollama` service requests an NVIDIA device).

## Architecture

```text
Frontend (React + Vite, :5173)
   │  ├──────────────► Backend (Spring Boot + Kotlin, :8081) ──► PostgreSQL
   │  │                       │
   │  │                       └──► Vision API (:8000) ── classify → detect → segment
   │  │
   │  └──────────────► LLM API (FastAPI, :8082) ──► Ollama proxy (:8084) ──► Gemma 4
```

| Service | Image / build | Port | Role |
|---|---|---|---|
| `db` | `postgres:16` | internal | Patient & visit data |
| `app` | `backend/WilhelmBackend` | 8081 | REST API, file storage, analysis orchestration |
| `vision-api` | root `Dockerfile` | 8000 | Classify → detect → segment pipeline |
| `ollama` + `model-init` | `ollama/ollama` | internal | Local Gemma 4 serving + model pull |
| `ollama-proxy` | `caddy:2-alpine` | 8084 | OpenAI-compatible proxy to Ollama |
| `llm-api` | `llm_api/` | 8082 | Multimodal `/analyze` + `/transcribe` |
| `frontend` | `node:20-alpine` | 5173 | Clinician UI |

## The models

| Stage | Model | Asset | Provenance |
|---|---|---|---|
| Classify | MedSigLIP-448 embeddings + Logistic Regression, **0.91 AUC**, threshold `0.0853` (tuned for ≥90% recall) | `vision_classifier/fracture_classifier_v3_0.91auc.pkl`, `embedding_cache.pkl` | Trained on **FracAtlas** (4,083 X-rays, CC-BY 4.0) |
| Detect | YOLOv8, fine-tuned for fracture regions | `vision_segmentation/weights/best.pt` | Trained on FracAtlas (COCO annotations) |
| Segment | SAM-Med2D (ViT-B, medical Segment Anything, 256×256, adapter) | `vision_segmentation/SAM-Med2D/sam-med2d_b.pth` | Cloned from [OpenGVLab/SAM-Med2D](https://github.com/OpenGVLab/SAM-Med2D); checkpoint auto-pulled at build |
| Reason | Gemma 4 (multimodal) | served by Ollama | `gemma/.env` (`LLM_MODEL`) |

The classifier uses a precomputed embedding cache, so known X-rays are scored instantly without loading the vision encoder.

## Clinician workflow

1. **Create a patient** (name, EHR ID, age, gender).
2. **Create a visit** for that patient.
3. **Upload an X-ray** image to the visit.
4. **Analyze** — Wilhelm runs classify → detect → segment and overlays detected fractures (red masks, bounding boxes, IoU scores) on the image.
5. **Correct (optional)** — toggle draw mode to add, edit, or delete regions; corrections are flagged and persisted.
6. **Dictate findings** — record a voice note directly in the browser, type doctor notes, optionally attach a prior triage PDF.
7. **Generate report** — Gemma 4 fuses image + voice + notes + PDF into a structured Emergency Department report.
8. **Review & export** — preview the rendered Markdown, edit it inline, and export a PDF (with the annotated X-ray and a patient barcode).

The browser-based **voice dictation → automatic report** flow is the standout moment of the live demo.

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | React 19, TypeScript, Vite, Tailwind CSS, TanStack Query |
| Backend | Spring Boot 3, Kotlin, Spring Data JPA |
| Database | PostgreSQL 16 |
| LLM service | FastAPI, Python, AsyncOpenAI SDK |
| Vision | PyTorch, Ultralytics YOLOv8, SAM-Med2D, MedSigLIP |
| LLM runtime | Ollama + Gemma 4, Caddy OpenAI-compatible proxy |
| Orchestration | Docker Compose (single root file) |

## Configuration

Sensible defaults work out of the box. Key knobs:

- **Gemma 4 variant** — `gemma/.env` → `LLM_MODEL` (default `gemma4:e4b`); also `OLLAMA_CONTEXT_LENGTH`, `PROXY_PORT`.
- **Fracture sensitivity** — `FRACTURE_THRESHOLD` (default `0.0853`, recall-tuned).
- **Frontend endpoints** — `VITE_API_URL`, `VITE_LLM_URL` (set in `docker-compose.yml`).

**Local vs. cloud Gemma 4.** The shipped default is **Gemma 4 served locally via Ollama** — this is the canonical path and keeps all data on-prem. The same OpenAI-compatible code can instead target a hosted Gemma 4 endpoint by changing `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL`. *Note for maintainers: `llm_api/.env.example` still shows a Gemma 3 / cloud default — align it to the Gemma 4 local default before final submission to avoid confusing judges.*

## Repository map

- `frontend/` — React + TypeScript clinician UI (key view: `src/pages/XrayDetailPage.tsx`)
- `backend/WilhelmBackend/` — Spring Boot + Kotlin REST API and orchestration
- `llm_api/` — FastAPI multimodal Gemma 4 service (`/analyze`, `/transcribe`)
- `vision/` — Vision inference API
- `vision_classifier/` — fracture classifier + embedding cache
- `vision_segmentation/` — YOLO + SAM-Med2D assets and pipeline
- `gemma/` — Ollama + Caddy config and Gemma 4 variant selection
- `use_cases/` — sample patient scenarios
- `docker-compose.yml` — single-command orchestration for the whole stack

## Troubleshooting

- **First run is slow** — Gemma 4 (~4 GB) and the SAM-Med2D checkpoint download on first build; later starts use cached Docker volumes.
- **No NVIDIA GPU** — the `ollama` service requests an NVIDIA device; on CPU-only hosts, remove the `deploy.resources` block from the `ollama` service in `docker-compose.yml` (smaller variants like `gemma4:e2b`/`e4b` still run, just slower).
- **Linux + `host.docker.internal`** — add an `extra_hosts` mapping if a service needs to reach the host.
- **Ports already in use** — 5173 / 8081 / 8000 / 8082 / 8084 must be free; adjust the port mappings in `docker-compose.yml`.

## Responsible AI & limitations

Wilhelm is a **research prototype, not a certified medical device**. It is designed to *assist*, not replace, clinicians: every AI detection is reviewable and correctable before a report is produced, and Gemma 4 is constrained by a system prompt that forbids inventing measurements or patient identifiers. Running Gemma 4 locally means patient data never leaves the deployment — a deliberate privacy-first design for the Health track.

## Acknowledgments & sources

Wilhelm is built on open models and an openly licensed dataset.

**Models**

- **Gemma 4** — Google DeepMind. Served locally via [Ollama](https://ollama.com/) (`gemma4:*` tags).
- **MedSigLIP-448** — Google Health medical vision-language encoder, used for fracture-classification embeddings. Model: [`google/medsiglip-448`](https://huggingface.co/google/medsiglip-448) (loaded via 🤗 Transformers).
- **YOLOv8 (yolov8n)** — Ultralytics, fine-tuned on FracAtlas for fracture-region detection. [github.com/ultralytics/ultralytics](https://github.com/ultralytics/ultralytics).
- **SAM-Med2D (ViT-B)** — Cheng et al., *SAM-Med2D*, 2023, [arXiv:2308.16184](https://arxiv.org/abs/2308.16184). Official implementation: [OpenGVLab/SAM-Med2D](https://github.com/OpenGVLab/SAM-Med2D); checkpoint mirror: [`schengal1/SAM-Med2D_model`](https://huggingface.co/schengal1/SAM-Med2D_model). Built on the Segment Anything Model (Kirillov et al., Meta AI, [arXiv:2304.02643](https://arxiv.org/abs/2304.02643)).

**Dataset**

- **FracAtlas** — Abedeen, Rahman, et al., *FracAtlas: A Dataset for Fracture Classification, Localization and Segmentation of Musculoskeletal Radiographs*, *Scientific Data* 10, 521 (2023), [doi:10.1038/s41597-023-02432-4](https://doi.org/10.1038/s41597-023-02432-4). 4,083 manually annotated radiographs, CC-BY 4.0. Used via [`yh0701/FracAtlas_dataset`](https://huggingface.co/datasets/yh0701/FracAtlas_dataset) (Hugging Face) and the [`mahmudulhasantasin/fracatlas-original-dataset`](https://www.kaggle.com/datasets/mahmudulhasantasin/fracatlas-original-dataset) (Kaggle) mirror.

Deeper component docs: `backend/WilhelmBackend/README.md`, `llm_api/README.md`, `vision/README.md`.

## Fracture classifier modes

The vision service supports two interchangeable fracture-classifier backends, selected
with the `CLASSIFIER_MODE` environment variable.

### `embeddings` (default)

The default. Uses the precomputed embedding cache plus the sklearn classifier
(`vision_classifier/fracture_classifier_v3_0.91auc.pkl`). Runs CPU-only, needs no
Hugging Face token and no GPU. This is the setup used by `docker compose up` with no
extra configuration — nothing to do.

### `live` (optional, MedSigLIP)

Real-time classification with the `google/medsiglip-448` MedSigLIP encoder. This is
opt-in because it requires a Hugging Face access token (the MedSigLIP model is gated)
and is intended to run on an NVIDIA GPU.

Enable it by setting, in your environment / `.env`:

```
CLASSIFIER_MODE=live
DOWNLOAD_MEDSIGLIP=true
TORCH_INDEX=https://download.pytorch.org/whl/cu128
VISION_DEVICE=cuda
```

and providing the token at build time:

```
HF_TOKEN=hf_xxx docker compose build vision-api tee-extension
docker compose up
```

For a GPU machine you must also expose the GPU to the `vision-api` (and `tee-extension`) containers (e.g. a
`docker-compose.override.yml` adding `gpus: all`). Without `DOWNLOAD_MEDSIGLIP=true`
the MedSigLIP weights are not downloaded and the image stays CPU-sized; set
`ALLOW_REMOTE_MEDSIGLIP=true` to let the service pull the model at runtime instead of
at build time.
