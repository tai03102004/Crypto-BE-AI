FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all deployment files
COPY models/ ./models/
COPY feature_extractor.py .
COPY shadow_engine.py .
COPY binance_executor.py .
COPY paper_portfolio.py .
COPY manual_order.py .
COPY live_shadow_runner.py .
COPY dashboard_server.py .
COPY verify_artifacts.py .
COPY start_services.sh .

# Create logs directory
RUN mkdir -p /app/logs

# Expose Web Dashboard Port
EXPOSE 8501

# Run entrypoint services
CMD ["./start_services.sh"]
