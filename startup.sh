#!/usr/bin/env bash
# startup.sh — Vast.ai GPU instance onstart script
#
# Paste this as the "onstart" command in your Vast.ai instance config:
#   bash -c "$(curl -fsSL https://raw.githubusercontent.com/Ryuketsukami/agent-server/main/startup.sh)"
#
# Or SSH in and run: bash startup.sh
#
# ── What this script does ─────────────────────────────────────────────────────
#   1. Installs Ollama (if not already present)
#   2. Starts Ollama with 3 parallel slots (for concurrent frontend sessions)
#   3. Pulls qwen3:8b (skipped if model is already cached on the volume)
#   4. Clones/updates this repo
#   5. Creates .env from instance environment variables
#   6. Installs Python dependencies
#   7. Starts the LangGraph agent server on port 8123
#
# ── Prerequisites ─────────────────────────────────────────────────────────────
# Vast.ai instance config:
#   Docker image : pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime
#                  (has Python 3.11 + CUDA; we install Ollama on top)
#   GPU          : RTX 3090 (24 GB VRAM) or better
#   Disk         : 40 GB minimum
#   Ports exposed: 8123
#
# Vast.ai environment variables (set in instance dashboard → Environment):
#   MODEL_NAME              qwen3:8b
#   OPENROUTER_REFERER      (leave blank for Vast.ai deployment)
#   OPENROUTER_TITLE        (leave blank for Vast.ai deployment)
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

REPO_URL="https://github.com/Ryuketsukami/agent-server.git"
WORK_DIR="/workspace/agent-server"

# ── 1. Install Ollama ─────────────────────────────────────────────────────────
if ! command -v ollama &> /dev/null; then
    echo "[startup] Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
else
    echo "[startup] Ollama already installed, skipping."
fi

# ── 2. Start Ollama with 3 parallel slots ─────────────────────────────────────
echo "[startup] Starting Ollama (OLLAMA_NUM_PARALLEL=3)..."
OLLAMA_NUM_PARALLEL=3 ollama serve &
OLLAMA_PID=$!

echo "[startup] Waiting for Ollama to be ready..."
until curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; do
    sleep 2
done
echo "[startup] Ollama is up."

# ── 3. Pull model (skipped if already cached on the persistent volume) ─────────
MODEL_NAME="${MODEL_NAME:-qwen3:8b}"
echo "[startup] Pulling ${MODEL_NAME}..."
ollama pull "${MODEL_NAME}"
echo "[startup] Model ready."

# ── 4. Clone or update the agent repo ────────────────────────────────────────
if [ -d "$WORK_DIR/.git" ]; then
    echo "[startup] Repo exists — pulling latest..."
    git -C "$WORK_DIR" pull --ff-only
else
    echo "[startup] Cloning agent-server..."
    git clone "$REPO_URL" "$WORK_DIR"
fi
cd "$WORK_DIR"

# ── 5. Write .env from instance environment variables ─────────────────────────
echo "[startup] Writing .env..."
cat > .env << EOF
MODEL_BASE_URL=http://localhost:11434/v1
MODEL_NAME=${MODEL_NAME}
MODEL_API_KEY=ollama
COST_PER_INPUT_TOKEN=0.0
COST_PER_OUTPUT_TOKEN=0.0
OPENROUTER_REFERER=
OPENROUTER_TITLE=
MAX_CONCURRENT_RUNS=3
EOF

# ── 6. Install Python dependencies ────────────────────────────────────────────
echo "[startup] Installing dependencies..."
pip install -e . --quiet

# ── 7. Start LangGraph agent server ──────────────────────────────────────────
echo "[startup] Starting LangGraph Server on 0.0.0.0:8123..."
# langgraph dev runs the graph directly in the current Python env (no Docker
# needed), which is correct for Vast.ai where we're already inside a container.
langgraph dev \
    --port 8123 \
    --host 0.0.0.0 \
    --no-reload

# Cleanup on exit
kill "$OLLAMA_PID" 2>/dev/null || true
