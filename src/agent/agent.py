"""ReactAgent: a LangGraph-based ReAct agent using Tavily web search."""

from __future__ import annotations

import time
from typing import Literal

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import SecretStr
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode

from .config import ModelConfig, load_config
from .metrics import build_metrics_payload
from .state import AgentState
from .tools import web_search

# System prompt for the ReAct agent — guides the LLM to follow a clean
# Thought → Action → Observation → Answer loop and avoid excessive iterations.
_SYSTEM_PROMPT = """\
You are a helpful assistant with access to a web_search tool.

Follow this pattern:
1. THINK about what information you need to answer the user's question.
2. Use web_search to find relevant information. Search once with a clear query.
3. Read the results and formulate your answer.
4. Provide a clear, concise answer based on what you found.

Rules:
- Search at most 2 times. If the first search doesn't help, try ONE different query.
- If search returns no results, answer based on your knowledge and note the limitation.
- Do NOT repeat the same search query.
- Keep your final answer concise and directly address the user's question.
"""


class ReactAgent:
    """ReAct agent: Thought → Action → Observation loop with metrics.

    Wraps a LangGraph ``StateGraph`` that executes the classic ReAct pattern:

    1. **agent** node  — calls the LLM (with Tavily search bound as a tool).
    2. **tools** node  — executes any requested tool calls.
    3. Loop until the LLM produces a final answer (no tool calls).
    4. **finalize** node — appends a ``metrics`` event to the message stream.

    The compiled graph is exposed via the ``graph`` property and registered
    in ``langgraph.json`` so LangGraph Server can serve and stream it.

    Memory:
        Pass a ``checkpointer`` to enable per-thread conversation memory.
        The LangGraph Server thread API (``/threads/{id}/runs/stream``)
        uses the checkpointer to persist messages across requests.

    Concurrency note:
        All timing and token data live in ``AgentState`` (per-request dict),
        not on ``self``.  Multiple concurrent requests are fully isolated.

    Example::

        from langgraph.checkpoint.memory import MemorySaver
        agent = ReactAgent(checkpointer=MemorySaver())
        config = {"configurable": {"thread_id": "session-1"}}
        result = agent.graph.invoke(
            {"messages": [("user", "What is LangGraph?")]}, config
        )
    """

    def __init__(
        self,
        config: ModelConfig | None = None,
    ) -> None:
        """Initialise the agent.

        Args:
            config: Pre-loaded ``ModelConfig``.  If ``None``, calls
                    ``load_config()`` to read from environment variables.
        """
        self._config: ModelConfig = config or load_config()

        # OpenRouter requires HTTP-Referer and X-Title headers to identify the
        # app in their dashboard and enforce per-app rate limits.  These headers
        # are no-ops for Ollama (self-hosted) deployments.
        extra_headers: dict[str, str] = {}
        if self._config.openrouter_referer:
            extra_headers["HTTP-Referer"] = self._config.openrouter_referer
        if self._config.openrouter_title:
            extra_headers["X-Title"] = self._config.openrouter_title

        self._llm = ChatOpenAI(
            model=self._config.model_name,
            base_url=self._config.base_url,
            api_key=SecretStr(self._config.api_key),
            streaming=True,
            default_headers=extra_headers or None,
        )

        self._tools = [web_search]
        self._llm_with_tools = self._llm.bind_tools(self._tools)
        self._tool_node = ToolNode(self._tools)

        self._graph: CompiledStateGraph = self._build_graph()

    # ------------------------------------------------------------------ #
    #  Graph nodes                                                         #
    # ------------------------------------------------------------------ #

    def _start_timing(self, state: AgentState) -> dict:
        """Capture graph entry timestamp and initialise token counters.

        This node runs once at the very start of each request.  Recording
        ``start_time_ns`` here (rather than in the ``agent`` node) ensures the
        timer includes the first LLM call's full latency.
        """
        return {
            "start_time_ns": time.monotonic_ns(),
            "first_token_ns": None,
            "input_tokens": 0,
            "output_tokens": 0,
        }

    def _call_model(self, state: AgentState) -> dict:
        """Invoke the LLM and accumulate token usage.

        On the *first* call, also records ``first_token_ns`` as a proxy for
        TTFT (time-to-first-token).  Subsequent calls leave it unchanged.

        Prepends the system prompt to guide the ReAct loop if no system
        message is already present in the conversation.

        Args:
            state: Current graph state.

        Returns:
            Dict with ``messages`` (new AI message) and updated token counts.
        """
        # Capture timestamp before LLM call as TTFT proxy (first call only)
        call_start_ns: int = time.monotonic_ns()

        # Prepend system prompt if not already present
        messages = state["messages"]
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=_SYSTEM_PROMPT)] + list(messages)

        response: AIMessage = self._llm_with_tools.invoke(messages)

        updates: dict = {"messages": [response]}

        # Record first-call time as TTFT approximation
        if state.get("first_token_ns") is None:
            updates["first_token_ns"] = call_start_ns

        # Accumulate token usage from LLM metadata when available
        meta = getattr(response, "usage_metadata", None)
        if meta:
            updates["input_tokens"] = (
                (state.get("input_tokens") or 0) + meta.get("input_tokens", 0)
            )
            updates["output_tokens"] = (
                (state.get("output_tokens") or 0) + meta.get("output_tokens", 0)
            )

        return updates

    def _finalize(self, state: AgentState) -> dict:
        """Compute and emit the final metrics event.

        Constructs the metrics payload and attaches it to an ``AIMessage``
        under ``additional_kwargs["metrics"]``.  The LangGraph Server streams
        this as the last SSE event; the Nitro proxy extracts and forwards it
        to the browser.

        Args:
            state: Final graph state after all ReAct iterations.

        Returns:
            Dict with a trailing ``AIMessage`` carrying the metrics payload.
        """
        payload: dict = build_metrics_payload(
            start_time_ns=state["start_time_ns"] or 0,
            first_token_ns=state["first_token_ns"] or state["start_time_ns"] or 0,
            end_time_ns=time.monotonic_ns(),
            input_tokens=state.get("input_tokens") or 0,
            output_tokens=state.get("output_tokens") or 0,
            cost_per_input_token=self._config.cost_per_input_token,
            cost_per_output_token=self._config.cost_per_output_token,
        )

        return {
            "messages": [
                AIMessage(content="", additional_kwargs={"metrics": payload})
            ]
        }

    # ------------------------------------------------------------------ #
    #  Routing                                                             #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _route(state: AgentState) -> Literal["tools", "finalize"]:
        """Route to ``tools`` if the LLM requested a tool call, else finalize.

        Args:
            state: Current graph state.

        Returns:
            ``"tools"`` or ``"finalize"``.
        """
        last: BaseMessage = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return "tools"
        return "finalize"

    # ------------------------------------------------------------------ #
    #  Graph construction                                                  #
    # ------------------------------------------------------------------ #

    def _build_graph(self) -> CompiledStateGraph:
        """Assemble and compile the ReAct StateGraph.

        Graph topology::

            START
              │
            start_timing
              │
            agent ──→ [has tool calls] ──→ tools ──→ agent (loop)
              │
              └──→ [no tool calls] ──→ finalize ──→ END

        Returns:
            Compiled LangGraph graph ready for ``invoke`` / ``stream``.
        """
        builder: StateGraph = StateGraph(AgentState)

        builder.add_node("start_timing", self._start_timing)
        builder.add_node("agent", self._call_model)
        builder.add_node("tools", self._tool_node)
        builder.add_node("finalize", self._finalize)

        builder.add_edge(START, "start_timing")
        builder.add_edge("start_timing", "agent")
        builder.add_conditional_edges("agent", self._route)
        builder.add_edge("tools", "agent")
        builder.add_edge("finalize", END)

        return builder.compile()

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    @property
    def graph(self) -> CompiledStateGraph:
        """Compiled graph consumed by LangGraph Server via ``langgraph.json``."""
        return self._graph
