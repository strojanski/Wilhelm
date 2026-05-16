# Gemma Multimodal Analyzer API

A FastAPI service that accepts **text + image + PDF + audio + extra metadata**, sends
everything to an **OpenAI-compatible LLM** (local vLLM serving Gemma, Google's
Gemini/Gemma OpenAI-compat endpoint, OpenAI, etc.), and returns a **structured
template response**. Also exposes a **speech-to-text** endpoint using the
OpenAI-compatible Whisper API.

Because everything goes through the OpenAI SDK, swapping between a local vLLM
deployment and a hosted API is just three env-var changes — **zero code
changes**.

---

## Project layout

```
gemma-api/
├── app/
│   ├── main.py              FastAPI app (/health, /analyze, /transcribe)
│   ├── config.py            pydantic-settings, loads .env
│   ├── schemas.py           Request/response Pydantic models
│   ├── services/
│   │   ├── llm_service.py   OpenAI SDK client → LLM
│   │   └── stt_service.py   OpenAI SDK client → Whisper
│   └── utils/
│       └── file_processing.py  PDF text extract + image → data-URL
├── tests/
│   └── test_api.py          End-to-end httpx test script
├── .env                     Real secrets (gitignored)
├── .env.example             Template
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

## 1. Configure `.env`

Edit the `.env` file in the project root. Two common configurations:

### A) Google AI Studio (Gemini/Gemma via OpenAI-compatible endpoint)

```env
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
LLM_API_KEY=your_google_ai_studio_api_key
LLM_MODEL=gemma-3-27b-it

STT_BASE_URL=https://api.openai.com/v1
STT_API_KEY=your_openai_key
STT_MODEL=whisper-1
```

### B) Local vLLM (same code, different URL)

```env
LLM_BASE_URL=http://host.docker.internal:8000/v1
LLM_API_KEY=EMPTY
LLM_MODEL=google/gemma-3-27b-it

STT_BASE_URL=http://host.docker.internal:8001/v1
STT_API_KEY=EMPTY
STT_MODEL=openai/whisper-large-v3
```

When using `host.docker.internal` on Linux, uncomment the `extra_hosts` block
in `docker-compose.yml`.

---

## 2. Run in Docker

```bash
# Build and start
docker compose up --build -d

# Tail logs
docker compose logs -f api

# Health check
curl http://localhost:8080/health

# Stop
docker compose down
```

Swagger UI is at **http://localhost:8080/docs**.

### Run without compose

```bash
docker build -t gemma-api .
docker run --rm -p 8080:8080 --env-file .env gemma-api
```

---

## 3. Run locally (no Docker)

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080
```

---

## 4. Test it

### With the included script

```bash
pip install httpx
python tests/test_api.py
python tests/test_api.py --image pic.png --pdf doc.pdf --audio clip.mp3
python tests/test_api.py --url http://localhost:8080 --skip-transcribe
```

### With curl

```bash
# Text only
curl -X POST http://localhost:8080/analyze \
  -F "text=Our Q3 revenue grew 18% YoY, driven by enterprise sales." \
  -F "category=finance" \
  -F 'metadata_json={"quarter":"Q3"}'

# Text + image + PDF + audio
curl -X POST http://localhost:8080/analyze \
  -F "text=Summarize the attached materials." \
  -F "image=@photo.jpg" \
  -F "pdf=@report.pdf" \
  -F "audio=@recording.mp3"

# Speech to text
curl -X POST http://localhost:8080/transcribe \
  -F "audio=@recording.mp3" \
  -F "language=en"
```

---

## Response template

`POST /analyze` always returns this shape (enforced by the system prompt):

```json
{
  "summary": "Brief 1-3 sentence summary.",
  "category": "finance",
  "tags": ["revenue", "enterprise", "Q3"],
  "entities": ["Acme Corp"],
  "key_points": [
    "Revenue up 18% YoY",
    "Strong enterprise performance",
    "Slight SMB churn increase"
  ],
  "sentiment": "positive",
  "confidence": 0.88,
  "raw_model_output": null
}
```

To change the template, edit `SYSTEM_PROMPT` and `AnalyzeResponse` in
`app/services/llm_service.py` and `app/schemas.py` respectively.

---

## Endpoints

| Method | Path          | Purpose                                              |
|--------|---------------|------------------------------------------------------|
| GET    | `/health`     | Returns status and configured model names            |
| POST   | `/analyze`    | Multipart: `text` + optional `image`/`pdf`/`audio`/extras |
| POST   | `/transcribe` | Multipart: `audio` + optional `language`             |
| GET    | `/docs`       | Swagger UI                                           |
| GET    | `/redoc`      | ReDoc UI                                             |

---

## Notes

- **Uploads are capped** at `MAX_UPLOAD_MB` (default 25 MB) per file.
- **PDFs** are text-extracted with `pypdf`; truncated at 30k chars.
  For scanned PDFs you'd need OCR (not included).
- **Images** are downscaled to 1536 px on the longest side before sending,
  to keep request payloads and latency reasonable.
- **JSON parsing is tolerant** — plain JSON, markdown-fenced JSON, and JSON
  embedded in prose all work, because real models sometimes ignore
  "JSON only" instructions.
- The **`openai` SDK** is used everywhere, so any OpenAI-compatible server
  works: vLLM, Ollama, LM Studio, llama.cpp, TGI, Deepgram, OpenAI itself.
