# Project 1 — Infrastructure Comparison: Agent Deployments

## Overview

A side-by-side comparison of a **ReAct agent** running on 4 different infrastructure types, all using the **same model** (Qwen3 8B Q4_K_M) and the **same tool** (DuckDuckGo search + Markdownify). The goal is to demonstrate how infrastructure affects latency, cost, and throughput — not model quality.

---

## Stack

| Layer | Technology |
|---|---|
| Frontend | Nuxt 3 + Nitro (hosted on Vercel) |
| Agent framework | LangGraph (Python) |
| Model | Qwen3 8B Q4_K_M (all deployments) |
| Search tool | DuckDuckGo API + Markdownify |
| Client-side inference | Transformers.js v4 (WebGPU) |

---

## Architecture

```
Browser (Nuxt/Vercel)
    │
    ├──▶ /api/local        → Nitro proxy → LangGraph Server (desktop, Cloudflare Tunnel)
    ├──▶ /api/vastai       → Nitro proxy → LangGraph Server (Vast.ai GPU instance, vLLM)
    ├──▶ /api/openrouter   → Nitro proxy → LangGraph Server (Railway, OpenRouter API)
    └──▶ Transformers.js   → runs entirely in browser (WebGPU, no server)
```

All three server-based columns share **one LangGraph agent repo**, deployed three different ways. Environment variables swap the model endpoint per deployment.

---

## Repos

### 1. `portfolio-frontend` (existing)
Nuxt 3 app hosted on Vercel.

### 2. `agent-server` (new)
Single Python LangGraph server repo. Deployed 3 ways:
- Local (desktop)
- Vast.ai GPU instance
- Railway (OpenRouter)

---

## Frontend — `portfolio-frontend`

### UI Layout

```
┌─────────────────────────────────────┐
│         [Query input field]  [Send] │
└─────────────────────────────────────┘

┌──────────┬──────────┬──────────┬──────────┐
│  Local   │ Vast.ai  │  API     │  Client  │
│ Qwen3 8B │ Qwen3 8B │ Qwen3 8B │ Qwen3*   │
├──────────┼──────────┼──────────┼──────────┤
│ 🧠 Think │ 🧠 Think │ 🧠 Think │ 🧠 Think │
│ ⚡ Action│ ⚡ Action│ ⚡ Action│ ⚡ Action│
│ 👁 Obs   │ 👁 Obs   │ 👁 Obs   │ 👁 Obs   │
│ ✅ Answer│ ✅ Answer│ ✅ Answer│ ✅ Answer│
├──────────┼──────────┼──────────┼──────────┤
│ Metrics  │ Metrics  │ Metrics  │ Metrics  │
└──────────┴──────────┴──────────┴──────────┘

┌─────────────────────────────────────────────┐
│ Summary: Fastest: X | Cheapest: X | ...     │
└─────────────────────────────────────────────┘
```

*Client column uses a smaller Qwen3 variant due to browser constraints — label this clearly in the column header.

### Column Header Info
Each column header shows:
- Infrastructure label (Local / Vast.ai / API / Client)
- Model name and variant
- Current status (online / offline / loading)

### Per-Column Metrics (shown after completion)
- Time to first token (ms)
- Total time (ms)
- Tokens/sec
- Total tokens (input + output)
- Estimated cost per query (Local and Client show $0.00)

### Concurrent Sessions Display
Each server-based column (Local, Vast.ai, API) shows a live concurrent sessions count in the column header:
- Fetched via `GET /info` on the LangGraph server (`/runs/active` count)
- Updates every 10s while the column is online
- Display: `N active session(s)` — helps users understand why inference is slower
- Shown as a subtle badge below the column status indicator

### Summary Bar
Shown after all columns finish:
- Fastest: `[column name] (Xs)`
- Cheapest: `[column name] ($X.XX)`
- Most tokens/sec: `[column name]`

### Column States
- **Online**: streaming normally
- **Offline**: blurred with reason shown (e.g. "Local machine is off", "Vast.ai instance not running")
- **Loading** (Client only): progress bar showing model download with download speed

### Streaming
Each ReAct step streams in real time as it arrives. Steps are styled distinctly:
- `🧠 Thought` — subtle background
- `⚡ Action` — highlighted
- `👁 Observation` — muted/secondary
- `✅ Answer` — prominent, final

### Nitro Proxy Routes
All agent requests go through Nitro server routes to avoid CORS and hide upstream URLs:

```
server/api/agent/local.post.ts
server/api/agent/vastai.post.ts
server/api/agent/openrouter.post.ts
```

Each route streams the LangGraph SSE response back to the browser.

### Environment Variables (Vercel)
```env
NUXT_LOCAL_AGENT_URL=https://xxx.trycloudflare.com
NUXT_VASTAI_AGENT_URL=https://xxx.vast.ai:PORT
NUXT_OPENROUTER_AGENT_URL=https://your-app.railway.app
```

### Client Column — Transformers.js
- Runs entirely in the browser via WebGPU
- Model: Qwen3 1.7B or 4B Q4 (smaller variant — label clearly)
- Browser check: Chrome only (WebGPU inconsistent elsewhere)
- VRAM check: if insufficient, blur column with explanation
- First load: show model download progress bar with speed indicator
- Subsequent loads: model cached in browser

---

## Agent Server — `agent-server`

### Tech
- Python
- LangGraph (`langgraph` + `langgraph-cli`)
- `langchain-openai` (OpenAI-compatible client for all model endpoints)
- `duckduckgo-search` + `markdownify`

### ReAct Agent

Standard ReAct loop:
1. **Thought** — reason about the query
2. **Action** — call DuckDuckGo search tool
3. **Observation** — process result with Markdownify
4. Repeat until confident
5. **Answer** — return final response

### Tool: DuckDuckGo + Markdownify
```python
@tool
def web_search(query: str) -> str:
    """Search the web using DuckDuckGo and return clean markdown."""
    results = DDGS().text(query, max_results=5)
    raw = "\n\n".join([r["body"] for r in results])
    return markdownify(raw)
```

Include graceful fallback if DuckDuckGo rate limits.

### Model Configuration (env-driven)
```python
llm = ChatOpenAI(
    model=os.environ["MODEL_NAME"],          # e.g. "qwen3:8b"
    base_url=os.environ["MODEL_BASE_URL"],   # e.g. "http://localhost:11434/v1"
    api_key=os.environ["MODEL_API_KEY"],     # "ollama" for local, real key for OpenRouter
    streaming=True,
)
```

### LangGraph Config (`langgraph.json`)
```json
{
  "dependencies": ["."],
  "graphs": {
    "react_agent": "./src/agent/graph.py:graph"
  },
  "env": ".env"
}
```

### Streaming
Use LangGraph's native SSE streaming so each ReAct step emits as it completes. The Nitro proxy pipes this stream directly to the browser.

### Metrics emission
Emit a final SSE event at the end of the stream with:
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

## Deployments

### Deployment A — Local (Desktop)

**Model serving:** Ollama on RTX 4080 16GB
```bash
ollama pull qwen3:8b
OLLAMA_NUM_PARALLEL=3 ollama serve  # runs on localhost:11434
```

**Agent server:**
```bash
pip install -e .
langgraph dev --port 8123 --tunnel
# Cloudflare Tunnel auto-generates a public HTTPS URL
# e.g. https://abc123.trycloudflare.com
```

**Env vars:**
```env
MODEL_BASE_URL=http://localhost:11434/v1
MODEL_NAME=qwen3:8b
MODEL_API_KEY=ollama
```

**Update Vercel:** set `NUXT_LOCAL_AGENT_URL` to the Cloudflare Tunnel URL.
Note: URL changes on every `langgraph dev --tunnel` restart. Either use a persistent Cloudflare Tunnel (cloudflared daemon) for a stable URL, or update the env var each time.

**Recommended:** set up `cloudflared` as a system service pointing to port 8123 for a stable, persistent URL that survives restarts.

---

### Deployment B — Vast.ai GPU Instance

**Instance spec:**
- GPU: RTX 3090 (24GB VRAM) — fits Qwen3 8B Q4 comfortably
- Image: `ollama/ollama:latest`
- Disk: 40GB minimum
- Expose port: 11434 (Ollama), 8123 (LangGraph)

**Scheduled availability (Israeli business hours):**
Use GitHub Actions cron to start/stop the instance automatically.

```yaml
# .github/workflows/vast-start.yml
on:
  schedule:
    - cron: '30 4 * * 0-4'  # 6:30 AM GMT+2, Sun-Thu
jobs:
  start:
    runs-on: ubuntu-latest
    steps:
      - run: |
          pip install vastai
          vastai set api-key ${{ secrets.VAST_API_KEY }}
          vastai start instance ${{ secrets.VAST_INSTANCE_ID }}
```

```yaml
# .github/workflows/vast-stop.yml
on:
  schedule:
    - cron: '0 15 * * 0-4'  # 5:00 PM GMT+2, Sun-Thu
jobs:
  stop:
    runs-on: ubuntu-latest
    steps:
      - run: |
          pip install vastai
          vastai set api-key ${{ secrets.VAST_API_KEY }}
          vastai stop instance ${{ secrets.VAST_INSTANCE_ID }}
```

**On the instance (startup script — see `startup.sh`):**
```bash
# Pull and serve model with Ollama (3 parallel slots for concurrent users)
ollama pull qwen3:8b
OLLAMA_NUM_PARALLEL=3 ollama serve &

# Wait for Ollama to be ready
until curl -sf http://localhost:11434/api/tags > /dev/null; do sleep 2; done

# Run the agent server
pip install -e .
langgraph up --port 8123
```

**Env vars:**
```env
MODEL_BASE_URL=http://localhost:11434/v1
MODEL_NAME=qwen3:8b
MODEL_API_KEY=ollama
```

**Update Vercel:** set `NUXT_VASTAI_AGENT_URL` to `https://<vast-instance-ip>:<mapped-port>`.

---

### Deployment C — Railway (OpenRouter API)

No GPU needed — this deployment is a pure Python server that proxies requests to OpenRouter. Free/hobby Railway tier is sufficient.

**Railway setup:**
- Connect `agent-server` GitHub repo
- Set start command: `langgraph up --port 8123`
- Railway auto-assigns a public HTTPS URL

**Env vars (set in Railway dashboard):**
```env
MODEL_BASE_URL=https://openrouter.ai/api/v1
MODEL_NAME=qwen/qwen3-8b
MODEL_API_KEY=sk-or-your-openrouter-key
```

**Update Vercel:** set `NUXT_OPENROUTER_AGENT_URL` to the Railway app URL.

Cost: ~$0.05/M input tokens, $0.40/M output tokens via OpenRouter.

---

## Services Summary

| Component | Repo | Platform | Always On |
|---|---|---|---|
| Frontend | `portfolio-frontend` | Vercel | ✅ |
| Agent (OpenRouter) | `agent-server` | Railway | ✅ |
| Agent (Local) | `agent-server` | Desktop + Cloudflare Tunnel | When PC is on |
| Agent (Vast.ai) | `agent-server` | Vast.ai GPU instance | Sun–Thu 6:30–17:00 GMT+2 |
| Model (Local) | — | Ollama on RTX 4080 | When PC is on |
| Model (Vast.ai) | — | Ollama on instance | Sun–Thu 6:30–17:00 GMT+2 |
| Model (API) | — | OpenRouter | ✅ |
| Client model | — | Transformers.js in browser | On demand |
| Schedule automation | — | GitHub Actions | ✅ |

---

## Cost Estimate

| Deployment | Est. monthly cost |
|---|---|
| Vercel (frontend) | Free tier |
| Railway (OpenRouter server) | Free tier |
| OpenRouter (per query) | ~$0.0005/query |
| Vast.ai (Sun–Thu, ~10.5hr/day) | ~$35/month |
| Cloudflare Tunnel | Free |
| GitHub Actions | Free |
