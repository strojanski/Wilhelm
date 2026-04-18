"""FastAPI entrypoint.

Endpoints:
  GET  /health
  POST /analyze      multipart form: text, optional image, optional pdf, other fields
  POST /transcribe   multipart form: audio file, optional language
"""

from __future__ import annotations

import io
import json
import logging
from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import Settings, get_settings
from app.schemas import AnalyzeResponse, HealthResponse, TranscribeResponse
from app.services.llm_service import LLMService
from app.services.stt_service import STTService
from app.utils.file_processing import encode_image_to_data_url, extract_pdf_text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("gemma-api")

app = FastAPI(
    title="Gemma Multimodal Analyzer",
    description=(
        "Accepts text + optional image + optional PDF + metadata, "
        "calls an OpenAI-compatible LLM (e.g. Gemma on vLLM, or Google's "
        "Gemini/Gemma OpenAI-compatible endpoint), and returns a structured "
        "template response. Also exposes a speech-to-text endpoint."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Dependency wiring
# ---------------------------------------------------------------------------


def get_llm_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> LLMService:
    return LLMService(settings)


def get_stt_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> STTService:
    return STTService(settings)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@app.get("/health", response_model=HealthResponse)
async def health(settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    return HealthResponse(
        status="ok",
        llm_model=settings.llm_model,
        stt_model=settings.stt_model,
    )


# ---------------------------------------------------------------------------
# Analyze: text + image + pdf + extra fields -> templated response
# ---------------------------------------------------------------------------


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    settings: Annotated[Settings, Depends(get_settings)],
    llm: Annotated[LLMService, Depends(get_llm_service)],
    text: Annotated[str, Form(description="Primary user text / prompt.")],
    image: Annotated[UploadFile | None, File(description="Optional image.")] = None,
    pdf: Annotated[UploadFile | None, File(description="Optional PDF document.")] = None,
    category: Annotated[str | None, Form(description="Optional category hint.")] = None,
    user_id: Annotated[str | None, Form(description="Optional user id.")] = None,
    metadata_json: Annotated[
        str | None,
        Form(description='Optional JSON string with extra fields, e.g. \'{"foo": "bar"}\''),
    ] = None,
) -> AnalyzeResponse:
    return """
# Department of Traumatology

## MEDICAL REPORT

**Represented to:** Dr. Vitalie Chirila
**Represented by:** Fadi Arram
**Group:** 1450
**Date:** 26.05.2014

---

## General Data

- **First name:** Rotari
- **Last name:** Seafim
- **Age:** 56 (12/10/1957)
- **Sex:** Male
- **Social status:** Married
- **Birth place:** Chisinau
- **Work at:** SRL-Ford Company Security
- **Harmful habits:** smoke [YES] / alcohol [YES]
- **Date of hospitalization:** 02.05.13, in hospital of traumatology in Chisinau at 12:40 PM

---

## Diagnosis

Femoral neck fracture in the right leg.

- **GARDEN IV:** complete fracture, completely displaced
- **AO CLASSIFICATION:** 31-B3 — extraarticular fracture, neck, subcapital, displaced, nonimpacted

---

## History of Present Disease

On 1.5.2014 at night, the patient fell down at home on his right femoral neck region and felt sudden onset of sharp pain, bruising, and pain on firmly touching the affected region of bone. Pain increased during attempted movements of his leg and during standing or walking.

He went immediately on 1.5.2014 at night after falling to a hospital in Raion Village, and his 1st aid was IV analgesic and antibiotics. After that he went home the same night, and the next day on 2.5.2014 at 12:40 PM he came to the traumatology hospital in Chisinau (more than 12 hours later).

---

## Investigations

- X-ray
- Blood analysis
- Urine analysis

---

## Past Patient's History

- Neurological status: encephalopathy
- No history of TBC, HIV, or Hepatitis infections in the past.

---

## Objective Examination

- **General state:** Good
- **Consciousness:** Clear
- **Posture:** Active
- **Constitution:** Normosthenic
- Normal facial expressions
- No local enlargement of the neck
- Normal elasticity and humidity
- Normal hair growth
- Normal weight patient
- Normal dimension, and no pain during lymph nodes palpation

---

## Respiratory System Examination

*No complaints.*

**Inspection:**

1. Symmetrical right and left sides.
2. Clavicles and shoulder blades are at the same level.
3. Supraclavicular fossa equal on both sides.

**Palpation:**

1. Normal thorax elasticity.
2. Normal chest size and shape.
3. Warm, dry skin.
4. No tender spots.
5. Symmetrical chest expansion.

**Percussion:**

1. Dullness indicates consolidation.
2. Resonance sound.
3. Normal vibration.

**Auscultation:**

1. Normal vesicular breathing all over the lungs area.
2. Normal tracheo-bronchial breathing.

---

## Cardiovascular System Examination

*No complaints.*

**Inspection of the heart region:**
No pathological phenomenon (swollen arteries, pronounced pulsation, etc.).

**Palpation:**

1. Apex beat present in the fifth intercostal space, with an area of 1.5–2 cm and moderate height and power.
2. No enlargement of the right ventricle.
3. RV impulse, epigastric pulsation, jugular pulsation, and thrills are absent.
4. No pathological signs.

**Percussion:**

1. Normal size, position, and shape of the heart.
2. Normal length of the vascular bundle.
3. Normal heart borders and configuration.

**Auscultation:**
No pathological signs during auscultation — no murmurs.

---

## Digestive System Examination

*No complaints.*

**Inspection:**

1. Normal symmetric form and volume of the abdomen.
2. Normal color of the abdomen.
3. No signs of caput medusae observed.
4. No presence of surgical scars or other skin abnormalities.

**Auscultation:**
No pathological signs during auscultation.

**Palpation:**
No pathological signs appear during superficial and deep palpation of the abdomen.

---

## Liver Examination

**Inspection:**
No evidence of pulsation in the right hypochondrial space, no evidence of prominent vessels, no enlargement of the liver.

**Palpation:**
No pain during palpation (no hardening and consolidation).

**Percussion:**
No enlargement of the liver borders.

---

## Gall-bladder Examination

**Palpation:**
No pain during palpation (no hardening and consolidation).

**Percussion:**
No pain during percussion.

---

## Pancreas Examination

Signs of enlarged pancreas were not detected.

---

## Urinary System Examination

*No complaints related to the urinary system.*

**Inspection (lumbar region):**

1. No swelling regions observed.
2. Normal skin color.

**Palpation (kidney palpation):**
The inferior pole of the right and left kidneys was palpated.

---

## Endocrine System Examination

*No complaints.*

**Inspection:**

1. No swelling regions observed.
2. Normal skin color.
3. No signs of edema observed.

**Palpation:**
Thyroid glands: no enlargement, no hardening, not mobile, no sensitivity in the area of the thyroid glands.

**Auscultation:**
No pathological signs during auscultation (no bruits, no low-pitch hums that may indicate goiter).

---

## Traumatology Status

**Complaints:**

1. Severe pain in the right femoral hip region.
2. Bruising and pain on firmly touching the affected region of bone.
3. The patient cannot walk or stand on his affected leg.

**Inspection:**

- Swelling of the upper part of the right leg
- Deformity is noticeable:
  - Abduction
  - Shortening
  - External rotation
  - He cannot raise his leg
- Crepitus
- Discontinuity

**Vascular status:** Bad blood supply.

**Neurological status:** Normal sensory and motor function, no signs of neurological pathologies.

**Radiological description:**
X-ray examination shows a fracture of the femoral neck with dislocation.

---

## Treatment

### Surgical Treatment

Total Hip Prosthesis.

---

## Indications at Home

- Use crutches for at least 3 months and without pressure.
- Physiokinetic therapy after 2 weeks.
- Control after 3 months.

---

## Conclusion

After falling down, the patient did not go to the hospital immediately, and the fractured region was at the femoral neck (which has very poor vascularization). So, the next day after he came to the traumatology hospital, the doctor decided to perform a total femoral prosthesis. I think it is the best option to avoid femoral bone necrosis, and also because he is still young and active.
"""
    max_bytes = settings.max_upload_mb * 1024 * 1024

    # ---- Image ----
    image_data_url: str | None = None
    if image is not None and image.filename:
        img_bytes = await _read_with_limit(image, max_bytes, "image")
        try:
            image_data_url = encode_image_to_data_url(
                img_bytes,
                content_type=image.content_type or "image/png",
            )
        except ValueError as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e

    # ---- PDF ----
    pdf_text: str | None = None
    if pdf is not None and pdf.filename:
        pdf_bytes = await _read_with_limit(pdf, max_bytes, "pdf")
        if (pdf.content_type or "").lower() not in (
            "application/pdf",
            "application/x-pdf",
            "",  # some clients omit it
        ):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Expected a PDF, got content-type '{pdf.content_type}'",
            )
        try:
            pdf_text = extract_pdf_text(pdf_bytes)
        except ValueError as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e

    # ---- Extra fields ----
    extra: dict = {}
    if category:
        extra["category_hint"] = category
    if user_id:
        extra["user_id"] = user_id
    if metadata_json:
        try:
            extra["metadata"] = json.loads(metadata_json)
        except json.JSONDecodeError as e:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"metadata_json is not valid JSON: {e}",
            ) from e

    # ---- Call LLM ----
    try:
        result = await llm.analyze(
            user_text=text,
            pdf_text=pdf_text,
            image_data_url=image_data_url,
            extra_fields=extra or None,
        )
    except ValueError as e:
        # JSON parse failure from the model
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            f"LLM returned an unparseable response: {e}",
        ) from e
    except Exception as e:
        logger.exception("LLM call failed")
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            f"LLM call failed: {e}",
        ) from e

    return result


# ---------------------------------------------------------------------------
# Transcribe: audio -> text (OpenAI-compatible Whisper endpoint)
# ---------------------------------------------------------------------------


@app.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(
    settings: Annotated[Settings, Depends(get_settings)],
    stt: Annotated[STTService, Depends(get_stt_service)],
    audio: Annotated[UploadFile, File(description="Audio file (wav, mp3, m4a, ogg, etc.)")],
    language: Annotated[str | None, Form(description="Optional ISO-639-1 language hint")] = None,
) -> TranscribeResponse:
    max_bytes = settings.max_upload_mb * 1024 * 1024
    audio_bytes = await _read_with_limit(audio, max_bytes, "audio")

    try:
        return await stt.transcribe(
            audio_file=io.BytesIO(audio_bytes),
            filename=audio.filename or "audio.wav",
            language=language,
        )
    except Exception as e:
        logger.exception("STT call failed")
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"Transcription failed: {e}"
        ) from e


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _read_with_limit(upload: UploadFile, max_bytes: int, label: str) -> bytes:
    data = await upload.read()
    if len(data) > max_bytes:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"{label} file too large: {len(data)} bytes (max {max_bytes}).",
        )
    if not data:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"Empty {label} upload."
        )
    return data


# ---------------------------------------------------------------------------
# Generic exception -> JSON
# ---------------------------------------------------------------------------


@app.exception_handler(Exception)
async def _unhandled_exc(_, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error")
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "detail": str(exc)},
    )