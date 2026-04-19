# syntax=docker/dockerfile:1.6
FROM python:3.11-slim

WORKDIR /app

# CPU-only torch avoids pulling ~1.5GB of CUDA wheels.
# Override with --build-arg TORCH_INDEX=https://download.pytorch.org/whl/cu121 for GPU.
ARG TORCH_INDEX=https://download.pytorch.org/whl/cpu

COPY vision/requirements.txt requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --extra-index-url ${TORCH_INDEX} -r requirements.txt

COPY vision/ ./vision/
COPY vision_classifier/ ./vision_classifier/
