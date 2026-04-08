"""Agent tools: DuckDuckGo web search with Markdownify post-processing."""

from __future__ import annotations

import time

from duckduckgo_search import DDGS
from duckduckgo_search.exceptions import DuckDuckGoSearchException
from langchain_core.tools import tool
from markdownify import markdownify

_MAX_RESULTS: int = 5
_MAX_ATTEMPTS: int = 3
_RETRY_DELAY_SEC: float = 1.5

# Module-level DDGS session — reused across calls to avoid rate limiting.
# DuckDuckGo rate-limits new sessions aggressively; reusing the session
# keeps the same cookies/tokens and avoids triggering empty results.
_ddgs: DDGS | None = None


def _get_ddgs() -> DDGS:
    """Return a cached DDGS session, creating one on first use."""
    global _ddgs  # noqa: PLW0603
    if _ddgs is None:
        _ddgs = DDGS()
    return _ddgs


def _web_search(query: str) -> str:
    """Search the web using DuckDuckGo and return clean Markdown text.

    Retries up to three times with exponential back-off on rate limit errors
    AND on empty results (DuckDuckGo sometimes returns empty sets under load).
    Returns a human-readable error string rather than raising so the agent
    can reason about the failure and try a different query.

    Args:
        query: Natural-language search query.

    Returns:
        Markdown-formatted concatenation of the top result bodies, or an
        error message string if all attempts fail.
    """
    global _ddgs  # noqa: PLW0603

    for attempt in range(_MAX_ATTEMPTS):
        try:
            results: list[dict] = _get_ddgs().text(query, max_results=_MAX_RESULTS)

            if not results:
                # Empty results may be transient (rate limiting) — retry
                if attempt < _MAX_ATTEMPTS - 1:
                    time.sleep(_RETRY_DELAY_SEC * (attempt + 1))
                    continue
                return "No results found for this query."

            bodies: list[str] = [r["body"] for r in results if r.get("body")]
            if not bodies:
                return "Results returned but contained no readable text."

            raw: str = "\n\n".join(bodies)
            return markdownify(raw)

        except DuckDuckGoSearchException as exc:
            # Reset the session on errors — the old session may be poisoned
            _ddgs = None
            if attempt < _MAX_ATTEMPTS - 1:
                time.sleep(_RETRY_DELAY_SEC * (attempt + 1))
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


# LangChain tool wrapper consumed by the ReactAgent.
# Tests call _web_search() directly to avoid the tool wrapper's type ambiguity.
web_search = tool(_web_search)
