"""Agent tools: DuckDuckGo web search with Markdownify post-processing."""

from __future__ import annotations

import time

from duckduckgo_search import DDGS
from duckduckgo_search.exceptions import DuckDuckGoSearchException
from langchain_core.tools import tool
from markdownify import markdownify

_MAX_RESULTS: int = 5
_MAX_ATTEMPTS: int = 3
_RETRY_DELAY_SEC: float = 1.0


@tool
def web_search(query: str) -> str:
    """Search the web using DuckDuckGo and return clean Markdown text.

    Retries up to three times with a 1-second back-off on rate limit errors.
    Returns a human-readable error string rather than raising so the agent
    can reason about the failure and try a different query.

    Args:
        query: Natural-language search query.

    Returns:
        Markdown-formatted concatenation of the top result bodies, or an
        error message string if all attempts fail.
    """
    for attempt in range(_MAX_ATTEMPTS):
        try:
            results: list[dict] = DDGS().text(query, max_results=_MAX_RESULTS)

            if not results:
                return "No results found for this query."

            bodies: list[str] = [r["body"] for r in results if r.get("body")]
            if not bodies:
                return "Results returned but contained no readable text."

            raw: str = "\n\n".join(bodies)
            return markdownify(raw)

        except DuckDuckGoSearchException as exc:
            if attempt < _MAX_ATTEMPTS - 1:
                time.sleep(_RETRY_DELAY_SEC)
            else:
                return (
                    f"Search temporarily unavailable after {_MAX_ATTEMPTS} attempts "
                    f"(rate limited): {exc}"
                )

        except Exception as exc:  # noqa: BLE001
            # Surface unexpected errors as text so the agent can acknowledge them
            return f"Unexpected search error: {exc}"

    # Unreachable — loop above always returns or exhausts retries
    return "Search failed after all retries."
