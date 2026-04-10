"""Tests for the ReactAgent graph structure and metrics computation."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from src.agent.config import ModelConfig
from src.agent.metrics import build_metrics_payload


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_config() -> ModelConfig:
    """Minimal ModelConfig that avoids real env-var reads."""
    return ModelConfig(
        base_url="http://localhost:11434/v1",
        model_name=os.environ.get("MODEL_NAME", "qwen3:8b"),
        api_key="ollama",
        cost_per_input_token=0.0,
        cost_per_output_token=0.0,
        openrouter_referer="",
        openrouter_title="",
    )


# ---------------------------------------------------------------------------
# build_metrics_payload tests
# ---------------------------------------------------------------------------

class TestBuildMetricsPayload:
    """Unit tests for the metrics computation utility."""

    def test_payload_schema(self) -> None:
        """Returned dict has exactly the required keys."""
        payload = build_metrics_payload(
            start_time_ns=0,
            first_token_ns=100_000_000,
            end_time_ns=1_000_000_000,
            input_tokens=100,
            output_tokens=50,
        )
        required_keys = {
            "type", "ttft_ms", "total_ms", "tokens_per_sec",
            "input_tokens", "output_tokens", "cost_usd",
        }
        assert set(payload.keys()) == required_keys
        assert payload["type"] == "metrics"

    def test_ttft_calculation(self) -> None:
        """TTFT is correctly computed from nanosecond timestamps."""
        payload = build_metrics_payload(
            start_time_ns=0,
            first_token_ns=250_000_000,   # 250 ms
            end_time_ns=1_000_000_000,
            input_tokens=0,
            output_tokens=0,
        )
        assert payload["ttft_ms"] == pytest.approx(250.0, abs=0.2)

    def test_total_ms_calculation(self) -> None:
        """Total time is correctly computed from start to finalize timestamps."""
        payload = build_metrics_payload(
            start_time_ns=0,
            first_token_ns=100_000_000,
            end_time_ns=2_000_000_000,    # 2 000 ms
            input_tokens=0,
            output_tokens=0,
        )
        assert payload["total_ms"] == pytest.approx(2000.0, abs=0.2)

    def test_tokens_per_sec(self) -> None:
        """Token throughput is computed as output_tokens / total_seconds."""
        payload = build_metrics_payload(
            start_time_ns=0,
            first_token_ns=100_000_000,
            end_time_ns=1_000_000_000,    # 1 second total
            input_tokens=100,
            output_tokens=50,             # 50 tokens / 1 sec = 50 t/s
        )
        assert payload["tokens_per_sec"] == pytest.approx(50.0, abs=0.5)

    def test_cost_calculation_openrouter(self) -> None:
        """Cost is computed correctly for a paid API deployment."""
        payload = build_metrics_payload(
            start_time_ns=0,
            first_token_ns=100_000_000,
            end_time_ns=1_000_000_000,
            input_tokens=1_000_000,
            output_tokens=1_000_000,
            cost_per_input_token=0.05 / 1_000_000,   # $0.05 / M
            cost_per_output_token=0.40 / 1_000_000,  # $0.40 / M
        )
        assert payload["cost_usd"] == pytest.approx(0.45, abs=0.001)

    def test_cost_zero_for_self_hosted(self) -> None:
        """Self-hosted Ollama deployments produce zero cost."""
        payload = build_metrics_payload(
            start_time_ns=0,
            first_token_ns=100_000_000,
            end_time_ns=1_000_000_000,
            input_tokens=500,
            output_tokens=300,
            cost_per_input_token=0.0,
            cost_per_output_token=0.0,
        )
        assert payload["cost_usd"] == 0.0

    def test_zero_division_guard_tokens_per_sec(self) -> None:
        """tokens_per_sec is 0.0 when start and end timestamp are identical."""
        payload = build_metrics_payload(
            start_time_ns=1000,
            first_token_ns=1000,
            end_time_ns=1000,             # total_ms == 0
            input_tokens=100,
            output_tokens=50,
        )
        assert payload["tokens_per_sec"] == 0.0

    def test_input_output_tokens_pass_through(self) -> None:
        """Token counts are preserved exactly in the returned payload."""
        payload = build_metrics_payload(
            start_time_ns=0,
            first_token_ns=100_000_000,
            end_time_ns=1_000_000_000,
            input_tokens=123,
            output_tokens=456,
        )
        assert payload["input_tokens"] == 123
        assert payload["output_tokens"] == 456

    def test_ttft_cannot_exceed_total_ms(self) -> None:
        """TTFT must be <= total_ms when first_token is between start and end."""
        payload = build_metrics_payload(
            start_time_ns=0,
            first_token_ns=300_000_000,   # 300 ms
            end_time_ns=1_000_000_000,    # 1 000 ms
            input_tokens=0,
            output_tokens=0,
        )
        assert payload["ttft_ms"] <= payload["total_ms"]


# ---------------------------------------------------------------------------
# ReactAgent graph structure tests
# ---------------------------------------------------------------------------

class TestReactAgentGraph:
    """Smoke tests for ReactAgent graph assembly — no real LLM calls."""

    def test_graph_has_expected_nodes(self, mock_config: ModelConfig) -> None:
        """Compiled graph contains all four required nodes."""
        with patch("src.agent.agent.ChatOpenAI"):
            from src.agent.agent import ReactAgent
            agent = ReactAgent(config=mock_config)

        node_names = set(agent.graph.nodes.keys())
        assert {"start_timing", "agent", "tools", "finalize"}.issubset(node_names)

    def test_graph_property_is_stable(self, mock_config: ModelConfig) -> None:
        """graph property returns the same compiled object on every access."""
        with patch("src.agent.agent.ChatOpenAI"):
            from src.agent.agent import ReactAgent
            agent = ReactAgent(config=mock_config)

        assert agent.graph is agent.graph

    def test_openrouter_headers_set_when_referer_provided(
        self, mock_config: ModelConfig
    ) -> None:
        """extra_headers dict is populated when openrouter_referer is non-empty."""
        config_with_headers = ModelConfig(
            base_url="https://openrouter.ai/api/v1",
            model_name="qwen/qwen3-8b",
            api_key="sk-or-test",
            cost_per_input_token=0.0,
            cost_per_output_token=0.0,
            openrouter_referer="https://my-portfolio.vercel.app",
            openrouter_title="Portfolio Demo",
        )

        with patch("src.agent.agent.ChatOpenAI") as MockLLM:
            from src.agent.agent import ReactAgent
            ReactAgent(config=config_with_headers)

        call_kwargs = MockLLM.call_args.kwargs
        headers = call_kwargs.get("default_headers", {})
        assert headers.get("HTTP-Referer") == "https://my-portfolio.vercel.app"
        assert headers.get("X-Title") == "Portfolio Demo"

    def test_no_extra_headers_for_ollama(self, mock_config: ModelConfig) -> None:
        """default_headers is None when openrouter_referer is blank (Ollama)."""
        with patch("src.agent.agent.ChatOpenAI") as MockLLM:
            from src.agent.agent import ReactAgent
            ReactAgent(config=mock_config)

        call_kwargs = MockLLM.call_args.kwargs
        assert call_kwargs.get("default_headers") is None
