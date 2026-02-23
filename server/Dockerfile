# Build from repo root: docker build -t food-server -f server/Dockerfile .
FROM python:3.12-slim

WORKDIR /app

COPY server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server/ ./server/

# Run from /app so that "server" is the top-level package
CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]
