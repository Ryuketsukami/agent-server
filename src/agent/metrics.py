"""Metrics computation and SSE payload construction."""

from __future__ import annotations


def build_metrics_payload(
    *,
    start_time_ns: int,
    first_token_ns: int,
    end_time_ns: int,
    input_tokens: int,
    output_tokens: int,
    cost_per_input_token: float = 0.0,
    cost_per_output_token: float = 0.0,
) -> dict:
    """Compute the final metrics dict emitted as a trailing SSE event.

    All timestamps are monotonic nanoseconds (``time.monotonic_ns()``).

    Args:
        start_time_ns:          Timestamp at graph entry.
        first_token_ns:         Timestamp at first LLM call start (TTFT proxy).
        end_time_ns:            Timestamp at finalize node entry.
        input_tokens:           Total input tokens across all LLM calls.
        output_tokens:          Total output tokens across all LLM calls.
        cost_per_input_token:   USD per input token.  0.0 for self-hosted.
        cost_per_output_token:  USD per output token.  0.0 for self-hosted.

    Returns:
        Dict matching the metrics SSE schema::

            {
                "type": "metrics",
                "ttft_ms": float,
                "total_ms": float,
                "tokens_per_sec": float,
                "input_tokens": int,
                "output_tokens": int,
                "cost_usd": float,
            }
    """
    total_ms: float = (end_time_ns - start_time_ns) / 1_000_000
    ttft_ms: float = (first_token_ns - start_time_ns) / 1_000_000
    total_sec: float = total_ms / 1000.0
    tokens_per_sec: float = output_tokens / total_sec if total_sec > 0 else 0.0
    cost_usd: float = (
        input_tokens * cost_per_input_token
        + output_tokens * cost_per_output_token
    )

    return {
        "type": "metrics",
        "ttft_ms": round(ttft_ms, 1),
        "total_ms": round(total_ms, 1),
        "tokens_per_sec": round(tokens_per_sec, 1),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": round(cost_usd, 6),
    }
