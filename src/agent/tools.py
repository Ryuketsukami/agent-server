"""Agent tools: Tavily web search for the ReAct agent."""

from __future__ import annotations

import os
import time

import httpx
from langchain_core.tools import tool

_MAX_RESULTS: int = 5
_MAX_ATTEMPTS: int = 3
_RETRY_DELAY_SEC: float = 1.0
_TAVILY_URL = "https://api.tavily.com/search"

# Reusable httpx client — avoids connection setup overhead per search.
_client: httpx.Client | None = None


def _get_client() -> httpx.Client:
    """Return a cached httpx client, creating one on first use."""
    global _client  # noqa: PLW0603
    if _client is None:
        _client = httpx.Client(timeout=15.0)
    return _client


def _web_search(query: str) -> str:
    """Search the web using Tavily and return clean text results.

    Retries up to three times with back-off on transient errors.
    Returns a human-readable error string rather than raising so the agent
    can reason about the failure and try a different query.

    Args:
        query: Natural-language search query.

    Returns:
        Concatenated result text, or an error message string if all
        attempts fail.
    """
    api_key = os.environ.get("TAVILY_API_KEY", "")
    if not api_key:
        return "Web search unavailable: TAVILY_API_KEY not configured."

    for attempt in range(_MAX_ATTEMPTS):
        try:
            resp = _get_client().post(
                _TAVILY_URL,
                json={
                    "api_key": api_key,
                    "query": query,
                    "max_results": _MAX_RESULTS,
                    "include_answer": False,
                },
            )

            if resp.status_code == 429:
                # Rate limited — retry after delay
                if attempt < _MAX_ATTEMPTS - 1:
                    time.sleep(_RETRY_DELAY_SEC * (attempt + 1))
                    continue
                return "Search temporarily unavailable (rate limited)."

            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])

            if not results:
                if attempt < _MAX_ATTEMPTS - 1:
                    time.sleep(_RETRY_DELAY_SEC * (attempt + 1))
                    continue
                return "No results found for this query."

            bodies: list[str] = [r["content"] for r in results if r.get("content")]
            if not bodies:
                return "Results returned but contained no readable text."

            return "\n\n".join(bodies)

        except httpx.HTTPStatusError as exc:
            if attempt < _MAX_ATTEMPTS - 1:
                time.sleep(_RETRY_DELAY_SEC * (attempt + 1))
            else:
                return (
                    f"Search temporarily unavailable after {_MAX_ATTEMPTS} attempts: "
                    f"{exc.response.status_code}"
                )

        except Exception as exc:  # noqa: BLE001
            return f"Unexpected search error: {exc}"

    return "Search failed after all retries."


# LangChain tool wrapper consumed by the ReactAgent.
# Tests call _web_search() directly to avoid the tool wrapper's type ambiguity.
web_search = tool(_web_search)
