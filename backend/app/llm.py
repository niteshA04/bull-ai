"""Thin wrapper around the Anthropic SDK for structured (tool-call) extraction.

All extraction agents call `run_tool` with a single tool definition and get back the
parsed JSON arguments the model produced, never free-text. If no API key is configured
the call raises LLMUnavailable and callers fall back to null/omitted fields, which the
Assembly agent then renders via the schema's fallback policy.
"""
from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from typing import Any

from . import config

logger = logging.getLogger("app.llm")

_client = None


class LLMUnavailable(Exception):
    pass


def _get_client():
    global _client
    if not config.LLM_AVAILABLE:
        raise LLMUnavailable("ANTHROPIC_API_KEY is not configured")
    if _client is None:
        import anthropic

        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


def pdf_document_block(file_path: str) -> dict:
    data = base64.standard_b64encode(Path(file_path).read_bytes()).decode("utf-8")
    return {
        "type": "document",
        "source": {"type": "base64", "media_type": "application/pdf", "data": data},
    }


def run_tool(
    *,
    system: str,
    user_content: list[dict] | str,
    tool_name: str,
    tool_description: str,
    input_schema: dict[str, Any],
    max_tokens: int = 4096,
) -> dict:
    """Force the model to call exactly one tool and return its parsed arguments."""
    client = _get_client()
    if isinstance(user_content, str):
        user_content = [{"type": "text", "text": user_content}]

    tool = {
        "name": tool_name,
        "description": tool_description,
        "input_schema": input_schema,
    }

    resp = client.messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=max_tokens,
        system=system,
        tools=[tool],
        tool_choice={"type": "tool", "name": tool_name},
        messages=[{"role": "user", "content": user_content}],
    )

    for block in resp.content:
        if block.type == "tool_use" and block.name == tool_name:
            return block.input
    raise RuntimeError(f"Model did not call tool {tool_name}")
