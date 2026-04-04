#!/usr/bin/env bash
# startup.sh — Vast.ai instance startup script
#
# Runs on a fresh Vast.ai RTX 3090 instance after provisioning.
# Called automatically by the instance's on-start command, or manually via SSH.
#
# Prerequisites:
#   - Docker image: ollama/ollama:latest
#   - Disk: 40 GB minimum
#   - Ports exposed: 11434 (Ollama), 8123 (LangGraph Server)
#
# Environment variables (set in Vast.ai instance config):
#   MODEL_BASE_URL        http://localhost:11434/v1
#   MODEL_NAME            qwen3:8b
#   MODEL_API_KEY         ollama
#   COST_PER_INPUT_TOKEN  0.0
#   COST_PER_OUTPUT_TOKEN 0.0

set -euo pipefail

echo "[startup] Starting Ollama..."

# Serve Ollama with 3 parallel slots to handle concurrent frontend sessions.
# Qwen3 8B Q4 is ~5 GB; 3 slots fit within 24 GB VRAM with headroom.
OLLAMA_NUM_PARALLEL=3 ollama serve &
OLLAMA_PID=$!

echo "[startup] Waiting for Ollama to be ready..."
until curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; do
    sleep 2
done
echo "[startup] Ollama is up."

echo "[startup] Pulling model qwen3:8b (skips if already cached)..."
ollama pull qwen3:8b
echo "[startup] Model ready."

echo "[startup] Installing agent dependencies..."
pip install -e . --quiet

echo "[startup] Starting LangGraph Server on port 8123..."
langgraph up --port 8123

# If langgraph up exits unexpectedly, kill Ollama cleanly
kill "$OLLAMA_PID" 2>/dev/null || true
