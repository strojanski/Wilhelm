# syntax=docker/dockerfile:1.6
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates git libxcb1 libxext6 libx11-6 libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# CPU-only torch avoids pulling ~1.5GB of CUDA wheels.
# Override with --build-arg TORCH_INDEX=https://download.pytorch.org/whl/cu121 for GPU.
ARG TORCH_INDEX=https://download.pytorch.org/whl/cpu

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
