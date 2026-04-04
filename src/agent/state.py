"""Agent state schema for the ReAct graph."""

from __future__ import annotations

from typing import Annotated, Optional

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict):
    """State passed between all nodes in the ReAct agent graph.

    Fields:
        messages:       Full conversation history.  LangGraph's ``add_messages``
                        reducer appends new messages rather than overwriting.
        start_time_ns:  Monotonic nanosecond timestamp captured at graph entry.
                        Used to compute ``total_ms`` in the final metrics event.
        first_token_ns: Monotonic nanosecond timestamp captured at the start of
                        the *first* LLM call.  Used as a proxy for TTFT because
                        LangChain callbacks cannot write back to LangGraph state
                        in streaming mode without extra plumbing.
        input_tokens:   Cumulative input token count across all LLM calls in
                        this run.  Accumulated by the ``agent`` node.
        output_tokens:  Cumulative output token count across all LLM calls in
                        this run.  Accumulated by the ``agent`` node.
    """

    messages: Annotated[list, add_messages]
    start_time_ns: Optional[int]
    first_token_ns: Optional[int]
    input_tokens: int
    output_tokens: int
