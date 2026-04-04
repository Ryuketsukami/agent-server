# agent-server

LangGraph ReAct agent backend for the **Infrastructure Comparison** portfolio project.

The same codebase is deployed three ways — local desktop, Vast.ai GPU instance, and Railway (OpenRouter API) — to demonstrate how infrastructure choices affect inference latency, cost, and throughput.  A fourth column in the frontend runs fully in the browser via Transformers.js.

---

## Architecture

```
Browser (Nuxt / Vercel)
    │
    ├──▶ /api/agent/local        → Nitro proxy → LangGraph Server (desktop, Cloudflare Tunnel)
    ├──▶ /api/agent/vastai       → Nitro proxy → LangGraph Server (Vast.ai, Ollama)
    └──▶ /api/agent/openrouter   → Nitro proxy → LangGraph Server (Railway, OpenRouter API)
```

Each LangGraph Server exposes the same `react_agent` graph.  The only difference between deployments is the `MODEL_BASE_URL`, `MODEL_NAME`, and `MODEL_API_KEY` environment variables.

---

## ReAct Agent

The agent runs a standard Thought → Action → Observation loop using a DuckDuckGo web search tool:

```
START
  │
start_timing ──→ agent ──┬──▶ [tool call] ──▶ tools ──▶ agent (loop)
                         └──▶ [final answer] ──▶ finalize ──▶ END
```

Each step streams to the browser via LangGraph Server's SSE endpoint.  A final `metrics` event is emitted at the end of every run:

```json
{
  "type": "metrics",
  "ttft_ms": 312,
  "total_ms": 4821,
  "tokens_per_sec": 47.3,
  "input_tokens": 284,
  "output_tokens": 531,
  "cost_usd": 0.00031
}
```

---

## Project structure

```
agent-server/
├── src/
│   └── agent/
│       ├── agent.py      # ReactAgent class — graph construction
│       ├── config.py     # ModelConfig dataclass, load_config()
│       ├── graph.py      # Module-level `graph` export for langgraph.json
│       ├── metrics.py    # build_metrics_payload() utility
│       ├── state.py      # AgentState TypedDict
│       └── tools.py      # web_search LangChain tool (DuckDuckGo + Markdownify)
├── tests/
│   ├── test_agent.py     # ReactAgent graph + metrics unit tests
│   └── test_tools.py     # web_search tool unit tests
├── .github/
│   └── workflows/
│       ├── vast-start.yml   # Cron: start Vast.ai instance 06:30 IL, Sun–Thu
│       └── vast-stop.yml    # Cron: stop Vast.ai instance 17:00 IL, Sun–Thu
├── langgraph.json        # LangGraph Server config
├── pyproject.toml        # Package metadata and dependencies
├── startup.sh            # Vast.ai instance startup script
└── .env.example          # Environment variable reference
```

---

## Setup

### Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com) (local / Vast.ai) **or** an OpenRouter API key (Railway)

### Install

```bash
pip install -e ".[dev]"
```

### Configure

```bash
cp .env.example .env
# Edit .env with your deployment's values
```

---

## Running each deployment

### Local (desktop)

```bash
# 1. Start Ollama with 3 parallel slots
OLLAMA_NUM_PARALLEL=3 ollama serve

# 2. Pull the model (one-time)
ollama pull qwen3:8b

# 3. Start the agent server with a Cloudflare Tunnel
langgraph dev --port 8123 --tunnel
# → The tunnel URL is printed — set it as NUXT_LOCAL_AGENT_URL in Vercel

# For a stable URL that survives restarts, run cloudflared as a system service:
# cloudflared tunnel --url http://localhost:8123
```

`.env` for local:
```env
MODEL_BASE_URL=http://localhost:11434/v1
MODEL_NAME=qwen3:8b
MODEL_API_KEY=ollama
COST_PER_INPUT_TOKEN=0.0
COST_PER_OUTPUT_TOKEN=0.0
```

---

### Vast.ai GPU instance

The instance starts and stops automatically via GitHub Actions (Sun–Thu, 06:30–17:00 Israel time).

**Secrets required** (set in GitHub repository settings):
- `VAST_API_KEY` — your Vast.ai API key
- `VAST_INSTANCE_ID` — the numeric instance ID from the Vast.ai dashboard

**Instance configuration** (set in Vast.ai dashboard):
- Image: `ollama/ollama:latest`
- GPU: RTX 3090 (24 GB VRAM)
- Disk: 40 GB minimum
- On-start command: `bash /workspace/startup.sh`
- Exposed ports: 11434, 8123

The `startup.sh` script handles everything:
1. Starts Ollama with `OLLAMA_NUM_PARALLEL=3`
2. Waits for Ollama to be ready
3. Pulls `qwen3:8b` (cached after first run)
4. Installs Python dependencies
5. Starts LangGraph Server

`.env` for Vast.ai:
```env
MODEL_BASE_URL=http://localhost:11434/v1
MODEL_NAME=qwen3:8b
MODEL_API_KEY=ollama
COST_PER_INPUT_TOKEN=0.0
COST_PER_OUTPUT_TOKEN=0.0
```

Set `NUXT_VASTAI_AGENT_URL` in Vercel to `https://<instance-ip>:<mapped-8123-port>`.

---

### Railway (OpenRouter API)

No GPU needed.  The agent server proxies all inference to OpenRouter.

**Railway setup:**
1. Connect this GitHub repo in the Railway dashboard
2. Set start command: `langgraph up --port 8123`
3. Add environment variables (see below)

`.env` for Railway:
```env
MODEL_BASE_URL=https://openrouter.ai/api/v1
MODEL_NAME=qwen/qwen3-8b
MODEL_API_KEY=sk-or-your-openrouter-key
COST_PER_INPUT_TOKEN=0.00000005    # $0.05 / M tokens
COST_PER_OUTPUT_TOKEN=0.0000004    # $0.40 / M tokens
```

Set `NUXT_OPENROUTER_AGENT_URL` in Vercel to the Railway app URL.

---

## Frontend integration

The Nuxt frontend sends requests to LangGraph Server via Nitro proxy routes:

```
POST /api/agent/local
POST /api/agent/vastai
POST /api/agent/openrouter

Body: { "query": "user question here" }
```

Each route streams LangGraph SSE events back to the browser.  The final event in every stream has `type: "metrics"` and carries the latency, throughput, and cost data displayed in the UI.

### Concurrent sessions

Each server-based column displays the current active session count (`GET /info` on the LangGraph server, polled every 10 s).  This lets users see at a glance whether slower inference is due to shared load — the Ollama deployments support up to 3 parallel sessions (`OLLAMA_NUM_PARALLEL=3`).

---

## Tests

```bash
pytest
```

Tests mock all external calls (Ollama, DuckDuckGo) — no network required.

---

## Cost reference

| Deployment | Model cost |
|---|---|
| Local | $0.00 (self-hosted) |
| Vast.ai | $0.00 per query (~$0.24/hr instance) |
| OpenRouter | ~$0.0005/query at typical query length |
| Client (Transformers.js) | $0.00 (runs in browser) |
