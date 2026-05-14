# syntax=docker/dockerfile:1.6
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates git libxcb1 libxext6 libx11-6 libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# CUDA torch is the default because the vision service is expected to run on
# NVIDIA GPUs. Override with --build-arg TORCH_INDEX=https://download.pytorch.org/whl/cpu
# for a smaller CPU-only image.
ARG TORCH_INDEX=https://download.pytorch.org/whl/cu128

# Install huggingface_hub early so model downloads can be cached independently of other requirements
RUN pip install huggingface_hub

ARG MEDSIGLIP_MODEL_ID=google/medsiglip-448
ENV MEDSIGLIP_MODEL_ID=${MEDSIGLIP_MODEL_ID}
RUN --mount=type=cache,target=/root/.cache/huggingface \
    --mount=type=secret,id=hf_token,required=true <<'PY'
python - <<'INNER'
import os
from pathlib import Path
from huggingface_hub import snapshot_download

token_path = Path("/run/secrets/hf_token")
token = token_path.read_text().strip()
if not token:
    raise SystemExit("HF_TOKEN build secret is empty.")

snapshot_download(
    repo_id=os.environ["MEDSIGLIP_MODEL_ID"],
    local_dir="/app/vision_classifier/medsiglip-448",
    local_dir_use_symlinks=False,
    token=token,
)
INNER
PY

COPY vision/requirements.txt requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --extra-index-url ${TORCH_INDEX} -r requirements.txt

ARG SAM_MED2D_REPO=https://github.com/OpenGVLab/SAM-Med2D.git
ARG SAM_MED2D_REF=main
ARG SAM_MED2D_CHECKPOINT_URL=https://huggingface.co/schengal1/SAM-Med2D_model/resolve/main/sam-med2d_b.pth?download=true

RUN git clone --depth 1 --branch ${SAM_MED2D_REF} ${SAM_MED2D_REPO} /app/vision_segmentation/SAM-Med2D \
    && python -c "from pathlib import Path; p=Path('/app/vision_segmentation/SAM-Med2D/segment_anything/build_sam.py'); s=p.read_text(); p.write_text(s.replace('torch.load(f, map_location=\"cpu\")', 'torch.load(f, map_location=\"cpu\", weights_only=False)'))" \
    && python -c "from urllib.request import urlretrieve; urlretrieve('${SAM_MED2D_CHECKPOINT_URL}', '/app/vision_segmentation/SAM-Med2D/sam-med2d_b.pth')"

COPY vision/ ./vision/
COPY vision_classifier/ ./vision_classifier/
COPY vision_segmentation/weights/ ./vision_segmentation/weights/
