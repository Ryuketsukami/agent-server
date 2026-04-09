"""Tests for the web_search tool implementation (Tavily)."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest
import httpx

import src.agent.tools as tools_module
from src.agent.tools import _web_search


@pytest.fixture(autouse=True)
def _reset_client_and_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset the module-level httpx client and set a dummy API key."""
    tools_module._client = None
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test-key")


def _mock_response(
    json_data: dict | None = None,
    status_code: int = 200,
) -> MagicMock:
    """Create a mock httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=resp
        )
    return resp


class TestWebSearch:
    """Unit tests for the Tavily _web_search implementation."""

    def test_returns_text_on_success(self) -> None:
        """Successful search returns concatenated result content."""
        mock_resp = _mock_response({
            "results": [
                {"content": "LangGraph is a library for building stateful agents."},
                {"content": "It supports cycles and streaming."},
            ]
        })
        with patch.object(tools_module, "_get_client") as mock_client:
            mock_client.return_value.post.return_value = mock_resp
            result = _web_search("what is langgraph")

        assert "LangGraph" in result
        assert "cycles" in result

    def test_returns_no_results_message_when_empty(self) -> None:
        """Empty result list returns the no-results sentinel after retries."""
        mock_resp = _mock_response({"results": []})
        with patch.object(tools_module, "_get_client") as mock_client:
            with patch("src.agent.tools.time") as mock_time:
                mock_time.sleep = lambda _: None
                mock_client.return_value.post.return_value = mock_resp
                result = _web_search("xyzzy nonsense query 12345")

        assert "No results found" in result

    def test_retries_empty_results_then_succeeds(self) -> None:
        """Empty results trigger a retry; second attempt may succeed."""
        empty_resp = _mock_response({"results": []})
        success_resp = _mock_response({
            "results": [{"content": "Found on retry."}]
        })
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return empty_resp if call_count == 1 else success_resp

        with patch.object(tools_module, "_get_client") as mock_client:
            with patch("src.agent.tools.time") as mock_time:
                mock_time.sleep = lambda _: None
                mock_client.return_value.post.side_effect = side_effect
                result = _web_search("test query")

        assert "Found on retry" in result
        assert call_count == 2

    def test_returns_no_body_message_when_content_empty(self) -> None:
        """Results with no 'content' fields return the no-readable-text sentinel."""
        mock_resp = _mock_response({
            "results": [{"title": "Page", "url": "https://example.com"}]
        })
        with patch.object(tools_module, "_get_client") as mock_client:
            mock_client.return_value.post.return_value = mock_resp
            result = _web_search("test")

        assert "no readable text" in result.lower()

    def test_retries_on_rate_limit(self) -> None:
        """429 status triggers retry."""
        rate_limit_resp = _mock_response(status_code=429)
        rate_limit_resp.raise_for_status = MagicMock()  # 429 handled before raise
        success_resp = _mock_response({
            "results": [{"content": "Retry succeeded."}]
        })
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return rate_limit_resp if call_count == 1 else success_resp

        with patch.object(tools_module, "_get_client") as mock_client:
            with patch("src.agent.tools.time") as mock_time:
                mock_time.sleep = lambda _: None
                mock_client.return_value.post.side_effect = side_effect
                result = _web_search("test query")

        assert "Retry succeeded" in result
        assert call_count == 2

    def test_returns_error_after_all_retries_fail(self) -> None:
        """After max retries all fail with HTTP errors, returns error string."""
        error_resp = _mock_response(status_code=500)
        with patch.object(tools_module, "_get_client") as mock_client:
            with patch("src.agent.tools.time") as mock_time:
                mock_time.sleep = lambda _: None
                mock_client.return_value.post.return_value = error_resp
                result = _web_search("test")

        assert "temporarily unavailable" in result.lower()

    def test_handles_unexpected_exception_gracefully(self) -> None:
        """Unexpected exceptions are caught and returned as error strings."""
        with patch.object(tools_module, "_get_client") as mock_client:
            mock_client.return_value.post.side_effect = RuntimeError("network error")
            result = _web_search("test")

        assert "Unexpected search error" in result

    def test_missing_api_key_returns_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Missing TAVILY_API_KEY returns a clear error message."""
        monkeypatch.delenv("TAVILY_API_KEY", raising=False)
        result = _web_search("test")
        assert "TAVILY_API_KEY" in result

    def test_concatenates_multiple_results(self) -> None:
        """Multiple result bodies are joined and all content appears in output."""
        mock_resp = _mock_response({
            "results": [
                {"content": "First result content."},
                {"content": "Second result content."},
            ]
        })
        with patch.object(tools_module, "_get_client") as mock_client:
            mock_client.return_value.post.return_value = mock_resp
            result = _web_search("test")

        assert "First result content" in result
        assert "Second result content" in result
