"""Production entrypoint — runs the LangGraph API server via uvicorn.

Replicates what `langgraph dev` does internally (set env vars, load config,
run uvicorn) but without dev-mode extras (browser opening, file watching,
tunnel setup) that can cause issues in containers.
"""

import json
import os
import sys


def main():
    import uvicorn

    port = int(os.environ.get("PORT", "2024"))
    host = os.environ.get("HOST", "0.0.0.0")

    # Load langgraph.json
    config_path = os.environ.get("LANGGRAPH_CONFIG", "langgraph.json")
    with open(config_path, encoding="utf-8") as f:
        config = json.load(f)

    graphs = config.get("graphs", {})

    # Set env vars that langgraph_api.server expects (same as langgraph dev)
    env_patch = {
        "LANGSERVE_GRAPHS": json.dumps(graphs),
        "LANGSMITH_LANGGRAPH_API_VARIANT": "local_dev",
        "LANGGRAPH_RUNTIME_EDITION": "inmem",
        "N_JOBS_PER_WORKER": os.environ.get("N_JOBS_PER_WORKER", "1"),
        "LANGGRAPH_UI_BUNDLER": "true",
        "LANGGRAPH_API_URL": f"http://{host}:{port}",
        "LANGGRAPH_DISABLE_FILE_PERSISTENCE": "false",
        "LANGGRAPH_ALLOW_BLOCKING": "false",
        "ALLOW_PRIVATE_NETWORK": "true",
        # langgraph_api.config reads these at import time even in inmem mode.
        # They're unused by the inmem runtime — just need to exist.
        "DATABASE_URI": "placeholder://inmem",
        "REDIS_URI": "placeholder://inmem",
    }

    for key, value in env_patch.items():
        if value is not None and key not in os.environ:
            os.environ[key] = value

    # Load .env file if it exists (for local dev)
    env_file = config.get("env")
    if env_file and os.path.exists(env_file):
        try:
            from dotenv.main import dotenv_values
            for k, v in dotenv_values(env_file).items():
                if v is not None and k not in os.environ:
                    os.environ[k] = v
        except ImportError:
            pass

    print(f"Starting LangGraph API on {host}:{port}", flush=True)

    uvicorn.run(
        "langgraph_api.server:app",
        host=host,
        port=port,
        access_log=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
