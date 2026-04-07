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

EXPOSE 8123

# Railway injects $PORT; default to 2024 (langgraph default).
# --host 0.0.0.0 makes the server reachable outside the container.
# --no-reload disables file watching (unnecessary in production container).
CMD sh -c "langgraph dev \
    --port ${PORT:-2024} \
    --host 0.0.0.0 \
    --no-reload"
