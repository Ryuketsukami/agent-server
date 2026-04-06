# Dockerfile — used by Railway (and any container-based deployment)
# Build: docker build -t agent-server .
# Run:   docker run -p 8123:8123 --env-file .env agent-server

FROM python:3.11-slim

WORKDIR /app

# Install dependencies before copying source so this layer is cached
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

# Copy source
COPY src/ ./src/
COPY langgraph.json .

EXPOSE 8123

# Railway injects $PORT; default to 8123 for local docker run.
# --no-browser skips opening a browser tab (not meaningful in a container).
# --host 0.0.0.0 makes the server reachable outside the container.
# --max-concurrent-runs matches OLLAMA_NUM_PARALLEL on the model server.
CMD sh -c "langgraph dev \
    --port ${PORT:-8123} \
    --host 0.0.0.0 \
    --no-browser \
    --max-concurrent-runs ${MAX_CONCURRENT_RUNS:-3}"
