# syntax=docker/dockerfile:1.6
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libxcb1 libxext6 libx11-6 libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# CPU-only torch avoids pulling ~1.5GB of CUDA wheels.
# Override with --build-arg TORCH_INDEX=https://download.pytorch.org/whl/cu121 for GPU.
ARG TORCH_INDEX=https://download.pytorch.org/whl/cpu

COPY vision/requirements.txt requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --extra-index-url ${TORCH_INDEX} -r requirements.txt

COPY vision/ ./vision/
COPY vision_classifier/ ./vision_classifier/
