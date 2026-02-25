# Build from repo root: docker build -t food-server -f server/Dockerfile .
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server/ ./server/

# Include kg_pipeline so the pipeline scheduler can run inside the container
COPY kg_pipeline/ ./kg_pipeline/

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run from /app so that "server" is the top-level package
CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]
