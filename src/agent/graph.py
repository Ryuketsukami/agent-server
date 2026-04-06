"""Module-level graph export consumed by LangGraph Server.

``langgraph.json`` points to this file::

    {
      "graphs": {
        "react_agent": "src.agent.graph:graph"
      }
    }

The ``graph`` variable is a compiled ``StateGraph`` instance.  It is
instantiated once at import time; LangGraph Server reuses it across requests.

LangGraph Server handles persistence automatically — no custom checkpointer
is needed.  The thread-based API (``/threads/{id}/runs/stream``) persists
conversation history out of the box.
"""

from .agent import ReactAgent

graph = ReactAgent().graph
