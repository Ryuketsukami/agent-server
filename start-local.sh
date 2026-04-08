#!/usr/bin/env bash
# Start the local LangGraph agent server with Cloudflare tunnel.
# Usage: bash portfolio/backend/start-local.sh
#
# Prerequisites:
#   - Ollama installed and running (ollama pull qwen3:8b)
#   - Cloudflare tunnel "local-agent" created (cloudflared tunnel create local-agent)
#   - Python venv at portfolio/backend/.venv with langgraph-cli installed

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CLOUDFLARED="/c/Program Files (x86)/cloudflared/cloudflared.exe"
VENV="$SCRIPT_DIR/.venv/Scripts/activate"
PORT=8123

# --- Preflight checks ---
if ! command -v ollama &>/dev/null; then
  echo "[ERROR] Ollama not found in PATH." >&2; exit 1
fi

if ! ollama list 2>/dev/null | grep -q "qwen3:8b"; then
  echo "[WARN] qwen3:8b not found — pulling now..."
  ollama pull qwen3:8b
fi

if [ ! -f "$VENV" ]; then
  echo "[ERROR] Python venv not found at $VENV" >&2; exit 1
fi

if [ ! -f "$CLOUDFLARED" ]; then
  echo "[ERROR] cloudflared not found at $CLOUDFLARED" >&2; exit 1
fi

# --- Start ---
source "$VENV"

echo "[1/2] Starting Cloudflare tunnel (local-agent -> localhost:$PORT)..."
"$CLOUDFLARED" tunnel run --url "http://localhost:$PORT" local-agent &
TUNNEL_PID=$!

echo "[2/2] Starting LangGraph server on port $PORT..."
cd "$SCRIPT_DIR"

# Load .env into the shell so langgraph dev picks up MODEL_BASE_URL etc.
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

langgraph dev --port $PORT --host 0.0.0.0 &
LANGGRAPH_PID=$!

echo ""
echo "=== Local agent server running ==="
echo "  LangGraph:  http://localhost:$PORT"
echo "  Tunnel:     (see cloudflared output above for public URL)"
echo "  Press Ctrl+C to stop both."
echo ""

# Trap Ctrl+C to kill both processes
trap 'echo "Shutting down..."; kill $TUNNEL_PID $LANGGRAPH_PID 2>/dev/null; wait; exit 0' INT TERM

wait
