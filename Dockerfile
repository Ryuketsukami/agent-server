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
RUN touch .env

# Production entrypoint — reads $PORT from Railway (default 2024).
# serve.py sets up the same env vars as `langgraph dev` but without
# dev-mode extras (browser, file watcher, tunnel) that break in containers.
COPY serve.py .
CMD ["python", "serve.py"]
