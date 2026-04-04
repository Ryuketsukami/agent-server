"""Environment-driven model configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ModelConfig:
    """Immutable snapshot of model settings loaded from env vars.

    All three server deployments (local, Vast.ai, Railway) share the same code
    and differ only in the environment variables they set.

    Attributes:
        base_url:               OpenAI-compatible API base URL.
        model_name:             Model identifier (e.g. ``"qwen3:8b"``).
        api_key:                API key.  Use ``"ollama"`` for self-hosted.
        cost_per_input_token:   USD cost per input token.  0.0 for self-hosted.
        cost_per_output_token:  USD cost per output token.  0.0 for self-hosted.
    """

    base_url: str
    model_name: str
    api_key: str
    cost_per_input_token: float
    cost_per_output_token: float


def load_config() -> ModelConfig:
    """Read model configuration from environment variables.

    Required:
        MODEL_BASE_URL   — OpenAI-compatible API base URL.
        MODEL_NAME       — Model identifier passed to the API.
        MODEL_API_KEY    — API key (``"ollama"`` for local/Vast.ai).

    Optional:
        COST_PER_INPUT_TOKEN   — Float USD per input token.  Default ``0.0``.
        COST_PER_OUTPUT_TOKEN  — Float USD per output token.  Default ``0.0``.

    Raises:
        KeyError: If any required environment variable is absent.
    """
    return ModelConfig(
        base_url=os.environ["MODEL_BASE_URL"],
        model_name=os.environ["MODEL_NAME"],
        api_key=os.environ["MODEL_API_KEY"],
        cost_per_input_token=float(os.environ.get("COST_PER_INPUT_TOKEN", "0.0")),
        cost_per_output_token=float(os.environ.get("COST_PER_OUTPUT_TOKEN", "0.0")),
    )
