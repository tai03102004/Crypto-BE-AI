FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy standalone Stage A application
COPY models/ ./models/
COPY feature_extractor.py .
COPY shadow_engine.py .
COPY live_shadow_runner.py .
COPY verify_artifacts.py .

# Create logs directory
RUN mkdir -p /app/logs

# Verify frozen artifacts before launch
RUN python verify_artifacts.py

# Run daemon
CMD ["python", "-u", "live_shadow_runner.py"]
