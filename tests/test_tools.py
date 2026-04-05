"""Tests for the web_search tool implementation."""

from __future__ import annotations

from unittest.mock import patch

import pytest

# Test the raw implementation function, not the LangChain tool wrapper.
# This avoids type-checker ambiguity around @tool's return type and keeps
# tests focused on the search logic rather than the LangChain plumbing.
from src.agent.tools import _web_search


class TestWebSearch:
    """Unit tests for the DuckDuckGo _web_search implementation."""

    def test_returns_markdown_on_success(self) -> None:
        """Successful search returns a non-empty markdown string."""
        mock_results = [
            {"body": "LangGraph is a library for building stateful agents."},
            {"body": "It supports cycles and streaming."},
        ]
        with patch("src.agent.tools.DDGS") as MockDDGS:
            MockDDGS.return_value.text.return_value = mock_results
            result = _web_search("what is langgraph")

        assert isinstance(result, str)
        assert len(result) > 0

    def test_returns_no_results_message_when_empty(self) -> None:
        """Empty result list returns the no-results sentinel string."""
        with patch("src.agent.tools.DDGS") as MockDDGS:
            MockDDGS.return_value.text.return_value = []
            result = _web_search("xyzzy nonsense query 12345")

        assert "No results found" in result

    def test_returns_no_body_message_when_bodies_empty(self) -> None:
        """Results with no 'body' fields return the no-readable-text sentinel."""
        with patch("src.agent.tools.DDGS") as MockDDGS:
            MockDDGS.return_value.text.return_value = [{"title": "Page"}]
            result = _web_search("test")

        assert "no readable text" in result.lower()

    def test_retries_on_rate_limit_then_succeeds(self) -> None:
        """Tool retries on DuckDuckGoSearchException and returns result on retry."""
        from duckduckgo_search.exceptions import DuckDuckGoSearchException

        mock_results = [{"body": "Retry succeeded."}]
        call_count = 0

        def side_effect(query: str, max_results: int) -> list:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise DuckDuckGoSearchException("rate limited")
            return mock_results

        with patch("src.agent.tools.DDGS") as MockDDGS:
            with patch("src.agent.tools.time") as mock_time:
                mock_time.sleep = lambda _: None  # skip actual delay
                MockDDGS.return_value.text.side_effect = side_effect
                result = _web_search("test query")

        assert "Retry succeeded" in result
        assert call_count == 2

    def test_returns_error_string_after_all_retries_fail(self) -> None:
        """After max retries all fail, returns a human-readable error string."""
        from duckduckgo_search.exceptions import DuckDuckGoSearchException

        with patch("src.agent.tools.DDGS") as MockDDGS:
            with patch("src.agent.tools.time") as mock_time:
                mock_time.sleep = lambda _: None
                MockDDGS.return_value.text.side_effect = DuckDuckGoSearchException(
                    "persistent rate limit"
                )
                result = _web_search("test")

        assert "temporarily unavailable" in result.lower()

    def test_handles_unexpected_exception_gracefully(self) -> None:
        """Unexpected exceptions are caught and returned as error strings."""
        with patch("src.agent.tools.DDGS") as MockDDGS:
            MockDDGS.return_value.text.side_effect = RuntimeError("network error")
            result = _web_search("test")

        assert "Unexpected search error" in result

    def test_skips_results_with_no_body(self) -> None:
        """Results missing the 'body' key are excluded; valid bodies are kept."""
        mock_results = [
            {"title": "Page 1"},       # no body — should be excluded
            {"body": "Valid content here."},
        ]
        with patch("src.agent.tools.DDGS") as MockDDGS:
            MockDDGS.return_value.text.return_value = mock_results
            result = _web_search("test")

        assert "Valid content here" in result

    def test_concatenates_multiple_bodies(self) -> None:
        """Multiple result bodies are joined and all content appears in output."""
        mock_results = [
            {"body": "First result content."},
            {"body": "Second result content."},
        ]
        with patch("src.agent.tools.DDGS") as MockDDGS:
            MockDDGS.return_value.text.return_value = mock_results
            result = _web_search("test")

        assert "First result content" in result
        assert "Second result content" in result
