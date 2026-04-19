FROM python:3.11-slim

WORKDIR /app

COPY vision/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY vision/ ./vision/

# Copy model artifacts — keeps images self-contained
COPY vision_classifier/ ./vision_classifier/
COPY vision_segmentation/weights/   ./vision_segmentation/weights/
COPY vision_segmentation/SAM-Med2D/ ./vision_segmentation/SAM-Med2D/
