# Wilhelm: from ER X-ray to a signed-off clinical report in seconds

### A four-stage, fully on-prem medical-imaging pipeline with Gemma 4 as the multimodal reasoning core

**Track:** Health / Medical

---

## The waiting room is the bottleneck

Think back to the last time you sat in an emergency room. The injury took a moment. The *waiting* took hours. Most of that time wasn't treatment — it was administrative latency: an X-ray sitting in a queue, waiting to be read, written up, and signed. For a suspected fracture, the medicine is fast. The paperwork is slow.

Wilhelm collapses that gap. A clinician uploads an X-ray and, within seconds, sees a localized fracture assessment drawn onto the image and a structured, editable Emergency Department report ready for sign-off. Nothing about the patient ever leaves the building.

That last sentence is the entire design philosophy. Hospitals cannot ship protected health information to a third-party API, and most cannot afford a GPU cluster either. So Wilhelm is built to be **private, on-prem, and cheap** — and that constraint, not a feature list, drove every decision below.

## The pipeline: ask the cheap questions first

An X-ray flows through four stages, deliberately ordered from cheapest to most expensive to run:

```
X-ray → 1. CLASSIFY → 2. DETECT → 3. SEGMENT → 4. REASON → editable report
        is there a    where is     which        Gemma 4: fuse image +
        fracture?     it?          pixels?      voice + notes + PDF
```

**1. Classify.** MedSigLIP-448 — Google Health's medical vision-language encoder — turns the X-ray into a 1,152-dimensional embedding, which an MLP classifier head scores. Measured on FracAtlas (4,083 radiographs, CC-BY 4.0), the classifier reaches a **ROC-AUC of 0.91**. (ROC-AUC is the probability the model ranks a random fractured X-ray above a random clean one; 0.91 means it gets that ordering right roughly nine times in ten.) We then push the decision threshold far below the usual 0.5 — down to **0.0853** — which lifts **recall to ≥90%**: it catches at least nine of every ten true fractures, accepting more false positives in return. That trade is intentional. In triage, a false positive costs a clinician one extra glance; a false negative can send a real fracture home undiagnosed.

**2. Detect.** YOLOv8, fine-tuned on FracAtlas, draws bounding boxes — but only if the classifier clears the threshold.

**3. Segment.** SAM-Med2D (medical Segment Anything, ViT-B) produces pixel masks and IoU scores for the flagged regions.

**4. Reason.** Gemma 4 fuses everything into a clinical document.

The funnel is the whole point. The expensive vision models and the LLM run *only* when the cheap classifier says they should, so a clean X-ray costs almost nothing. A precomputed embedding cache lets known images skip the vision encoder entirely — instant re-scoring after a clinician edits a region.

And the clinician always has the last word. Detections appear as correctable overlays: toggle draw mode to add, move, or delete a region, and the correction is flagged and persisted before any report is generated. The AI proposes; the doctor disposes.

## Why Gemma 4 is the right reasoning core

Stages 1–3 answer *where* and *what*. They don't write medicine. Turning a mask and a bounding box into a document a doctor will actually sign requires a model that can read an X-ray, listen to a dictated note, parse a prior referral PDF, and reconcile all of it into one coherent report. That is exactly the job we gave Gemma 4.

**One call, four modalities.** A single `/analyze` request fuses the X-ray, a browser-recorded voice note, typed doctor notes, and a prior triage PDF. The content blocks are assembled in **image → audio → text** order, following Gemma's multimodal guidance — an ordering that measurably improved how reliably the model grounded its report in the image instead of drifting toward the text. The voice note is explicitly elevated as the primary signal in the system prompt, because in a real ED the doctor's spoken examination findings outrank everything else in the room.

**A 931-line system prompt as a clinical guardrail.** Gemma 4 is constrained by a long, fixed Emergency Department report template. It must populate every section and is explicitly forbidden from inventing patient identifiers, measurements, or classifications it was not given. This is the line between a chatbot and a documentation tool: the output shape is deterministic, the clinical content is grounded, and a hallucinated bone measurement is engineered out rather than hoped against. We deliberately avoid `response_format=json_object` — not every OpenAI-compatible server honors it with Gemma — and instead enforce structure through the prompt, with tolerant Markdown parsing on our side.

**100% local, behind an OpenAI-compatible seam.** Gemma 4 runs through Ollama behind a Caddy auth proxy that exposes an OpenAI-compatible endpoint. Our code speaks only the OpenAI SDK, which buys two things at once: PHI never leaves the deployment, and the *exact same code* runs against local Ollama or a hosted endpoint by changing three environment variables. No vendor lock-in, and no separate code path for the privacy-critical deployment.

**It scales to the hardware a hospital actually owns.** Gemma 4 ships in variants from ~2 GB to a 20 GB dense model, selectable with one line in `.env`. A rural clinic on a single consumer GPU and a regional hospital with a 24 GB card run the same Wilhelm — only the model tag changes. For a "for good" project, *runs on the hardware you can afford* is not a footnote. It is the thesis.

## Challenges we actually hit

- **Recall versus precision in triage.** The default 0.5 threshold scored well on paper and missed fractures we cared about. We re-tuned the threshold down to 0.0853 to reach ≥90% recall, accepting more false positives — dismissed in a glance — over false negatives that leave undiagnosed.
- **Grounding the report in the image.** Early reports read fluently but leaned on the text and under-used the X-ray. Reordering multimodal content to image-first, and explicitly elevating the voice note in the system prompt, fixed the grounding.
- **Structured output with no JSON mode.** Gemma plus some OpenAI-compatible servers don't reliably honor `response_format`. Enforcing the template in the prompt and parsing tolerantly proved far more portable than fighting server-side schema support.
- **One command for the whole stack.** PostgreSQL, a Spring Boot/Kotlin backend, the vision pipeline, Ollama + Gemma 4, and a React UI all come up with a single `docker compose up`; weights cache in volumes after the first pull. A judge — or a hospital IT team — runs one command.

## Why this matters, and where it goes

Wilhelm is a research prototype, not a certified device, and it is built to *assist*, never replace. Every detection is reviewable, every report is editable, and the model is constrained against fabrication. But the architecture is the real contribution: a privacy-first, hardware-flexible, clinician-in-the-loop imaging pipeline with a multimodal LLM doing the documentation work doctors dread.

Nothing in stages 2–4 is fracture-specific. Swap the FracAtlas-trained detector for a chest, dental, or mammography model and the same funnel, the same Gemma 4 core, and the same on-prem guarantees carry straight over. The bottleneck we attacked — imaging-to-report latency under a hard privacy constraint — exists in every imaging department on earth. We built it for fractures because we could prove it end to end. It generalizes because the design never assumed otherwise.

