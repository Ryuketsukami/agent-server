"""Module-level graph export consumed by LangGraph Server.

``langgraph.json`` points to this file::

    {
      "graphs": {
        "react_agent": "./src/agent/graph.py:graph"
      }
    }

The ``graph`` variable is a compiled ``StateGraph`` instance.  It is
instantiated once at import time; LangGraph Server reuses it across requests.

Memory is enabled via ``MemorySaver`` so the thread-based API
(``/threads/{id}/runs/stream``) persists conversation history.
For production deployments, swap to ``PostgresSaver``.
"""

from langgraph.checkpoint.memory import MemorySaver

from .agent import ReactAgent

# MemorySaver stores thread state in-process.  Sufficient for single-server
# deployments and the portfolio demo.  Swap to PostgresSaver for multi-server.
graph = ReactAgent(checkpointer=MemorySaver()).graph
