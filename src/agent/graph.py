"""Module-level graph export consumed by LangGraph Server.

``langgraph.json`` points to this file::

    {
      "graphs": {
        "react_agent": "./src/agent/graph.py:graph"
      }
    }

The ``graph`` variable is a compiled ``StateGraph`` instance.  It is
instantiated once at import time; LangGraph Server reuses it across requests.
"""

from .agent import ReactAgent

# Instantiated once; all per-request state lives in AgentState (safe for
# concurrent use — see ReactAgent docstring).
graph = ReactAgent().graph
