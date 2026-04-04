# agent-server

LangGraph ReAct agent backend for the **Infrastructure Comparison** portfolio project.

The same codebase runs on three deployments — local desktop, Vast.ai GPU instance, and Railway (OpenRouter API) — to show how infrastructure choices affect latency, cost, and throughput. A fourth column in the frontend runs fully in-browser via Transformers.js (no backend needed).

---

## Why LangGraph Server?

The frontend needs to stream the agent's Thought → Action → Observation steps as they happen, plus receive a final metrics event with timing and cost. Building that from scratch requires custom SSE handling, session management, and a streaming HTTP server.

**LangGraph Server** (`langgraph dev`) gives all of that for free: it serves the graph as a standard SSE HTTP endpoint, manages concurrent request slots, and streams each node's output to the client as it completes. The Nuxt frontend's Nitro proxy just posts to `/runs/stream` and pipes the SSE stream to the browser.

---

## Architecture

```
Browser (Nuxt / Vercel)
    │
    ├──▶ /api/agent/local       → Nitro proxy → LangGraph Server (desktop, Cloudflare Tunnel)
    ├──▶ /api/agent/vastai      → Nitro proxy → LangGraph Server (Vast.ai, Ollama)
    └──▶ /api/agent/openrouter  → Nitro proxy → LangGraph Server (Railway, OpenRouter API)
```

All three backends run identical code. Only environment variables differ.

---

## ReAct Agent graph

```
START
  │
start_timing ──→ agent ──┬──▶ [tool call]    ──▶ tools ──▶ agent (loop)
                         └──▶ [final answer] ──▶ finalize ──▶ END
```

Each node streams to the browser. The `finalize` node emits a trailing `metrics` SSE event:

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
│       ├── metrics.py    # build_metrics_payload() — pure computation
│       ├── state.py      # AgentState TypedDict
│       └── tools.py      # web_search tool (DuckDuckGo + Markdownify)
├── tests/
│   ├── conftest.py       # adds src/ to sys.path
│   ├── test_agent.py
│   └── test_tools.py
├── .github/
│   └── workflows/
│       ├── vast-start.yml   # cron: start Vast.ai 06:30 IL, Sun–Thu
│       └── vast-stop.yml    # cron: stop Vast.ai 17:00 IL, Sun–Thu
├── Dockerfile            # used by Railway (container deployment)
├── langgraph.json        # tells LangGraph Server which graph to serve
├── pyproject.toml        # dependencies and package config
├── startup.sh            # Vast.ai onstart script (installs + runs everything)
└── .env.example          # all env vars documented per deployment
```

---

## Local setup (resolving Python imports)

Python imports don't resolve in your editor until the package is installed into a virtual environment.

```bash
# Create and activate venv
python -m venv .venv
.venv\Scripts\activate       # Windows
# source .venv/bin/activate  # macOS / Linux

# Install the package + dev dependencies
pip install -e ".[dev]"
```

Then in VS Code: **Ctrl+Shift+P → Python: Select Interpreter → .venv**.
All `src.agent.*` imports will resolve.

---

## Running each deployment

### Local (desktop)

```bash
# 1. Start Ollama with 3 parallel slots (run once; keep terminal open)
OLLAMA_NUM_PARALLEL=3 ollama serve

# 2. Pull the model (one-time, ~5 GB download)
ollama pull qwen3:8b

# 3. Copy and fill the env file
cp .env.example .env
# Edit .env — the defaults already match local Ollama, no changes needed

# 4. Start the agent server with a Cloudflare Tunnel
langgraph dev --port 8123 --tunnel --max-concurrent-runs 3
# The tunnel URL is printed — set it as NUXT_LOCAL_AGENT_URL in Vercel
```

For a stable tunnel URL that survives restarts, run `cloudflared` as a system service pointing to port 8123.

---

### Vast.ai GPU instance

#### One-time setup

1. Create a Vast.ai instance:
   - Docker image: `pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime`
   - GPU: RTX 3090 (24 GB VRAM)
   - Disk: 40 GB minimum
   - Port: expose `8123`

2. In the instance's **Environment** settings, set:
   ```
   MODEL_NAME=qwen3:8b
   ```

3. In the instance's **Onstart** field, paste:
   ```bash
   bash -c "$(curl -fsSL https://raw.githubusercontent.com/Ryuketsukami/agent-server/main/startup.sh)"
   ```

4. Add GitHub Actions secrets (repo **Settings → Secrets and variables → Actions**):
   - `VAST_API_KEY` — your Vast.ai API key (vastai.com → Account → API key)
   - `VAST_INSTANCE_ID` — numeric ID shown in `vastai show instances`

The instance now starts automatically at 06:30 and stops at 17:00 Israel time (Sun–Thu).

Set `NUXT_VASTAI_AGENT_URL` in Vercel to `https://<instance-ip>:<mapped-8123-port>`.

---

### Railway (OpenRouter API)

No GPU needed.

1. Connect this repo in the Railway dashboard (New Project → Deploy from GitHub)
2. Railway detects the `Dockerfile` and builds automatically
3. Set environment variables in the Railway dashboard:

```env
MODEL_BASE_URL=https://openrouter.ai/api/v1
MODEL_NAME=qwen/qwen3-8b
MODEL_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxxxxxx
COST_PER_INPUT_TOKEN=0.00000005
COST_PER_OUTPUT_TOKEN=0.0000004
OPENROUTER_REFERER=https://your-portfolio.vercel.app
OPENROUTER_TITLE=Portfolio Infrastructure Demo
MAX_CONCURRENT_RUNS=3
```

Set `NUXT_OPENROUTER_AGENT_URL` in Vercel to the Railway app URL.

#### OpenRouter API key

Get your key at [openrouter.ai](https://openrouter.ai) → Keys.
`sk-or-v1-...` goes in `MODEL_API_KEY`. The key is **never** committed — only set in Railway's environment variables dashboard.

#### Rate limits

OpenRouter applies rate limits per key (typically 60 req/min on free tier, higher on paid). The server is capped at 3 concurrent runs (`MAX_CONCURRENT_RUNS=3`), which is well within free-tier limits for a portfolio demo. If you hit limits, configure them in the OpenRouter dashboard and raise `MAX_CONCURRENT_RUNS` accordingly.

---

## Frontend: concurrent sessions display

Each column header shows how many sessions are currently active on that server, fetched every 10 seconds:

```
GET {AGENT_URL}/runs?status=running
```

This lets visitors see at a glance whether slower inference is due to shared load (Ollama is capped at `OLLAMA_NUM_PARALLEL=3`).

---

## GitHub Actions secrets reference

| Secret | Where to get it | Used by |
|---|---|---|
| `VAST_API_KEY` | vastai.com → Account → API key | `vast-start.yml`, `vast-stop.yml` |
| `VAST_INSTANCE_ID` | `vastai show instances` (numeric ID) | `vast-start.yml`, `vast-stop.yml` |

Set both at: **GitHub repo → Settings → Secrets and variables → Actions → New repository secret**

---

## Tests

```bash
pytest
```

All external calls (Ollama, DuckDuckGo) are mocked — no network required.

---

## Cost reference

| Deployment | Model cost |
|---|---|
| Local | $0.00 (self-hosted Ollama) |
| Vast.ai | $0.00 per query (~$0.24/hr instance cost) |
| OpenRouter | ~$0.0005/query at typical query length |
| Client (Transformers.js) | $0.00 (runs in browser) |
