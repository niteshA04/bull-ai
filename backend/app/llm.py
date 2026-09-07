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
import re
from pathlib import Path
from typing import Any

from . import config

logger = logging.getLogger("app.llm")

_client = None

_LEAKED_ARRAY_RE = re.compile(r'^\s*<parameter name="\$0">(.*)$', re.DOTALL)


def _recover_leaked_arrays(result: dict) -> dict:
    """Rare but reproducible malformation seen on very large documents with a long
    array-of-strings tool field: instead of a proper JSON array, the model emits the
    first item as a string value with a leaked '<parameter name="$0">' tag, and the
    remaining items as sibling top-level keys '$1', '$2', ... The content itself is
    fine — only the shape is wrong — so reassemble it into the array the schema wants."""
    for field, value in list(result.items()):
        if not isinstance(value, str):
            continue
        m = _LEAKED_ARRAY_RE.match(value)
        if not m:
            continue
        items = [m.group(1)]
        i = 1
        while f"${i}" in result:
            items.append(result.pop(f"${i}"))
            i += 1
        result[field] = items
        logger.warning("Recovered leaked array field %r (%d items) from malformed tool output", field, len(items))
    return result


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


PAGES_REVIEWED_FIELD = {
    "type": "array",
    "items": {"type": "integer"},
    "description": (
        "Every page number (1-indexed) of the source document you actually reviewed before "
        "answering, in order. You must review and list every page of the document, including "
        "the last page — do not stop early or sample a subset."
    ),
}


def coverage_instruction(page_count: int) -> str:
    """Prompt text forcing the model to read (and self-report) every page."""
    if not page_count:
        return ""
    return (
        f"\n\nThis document has {page_count} pages. You must review every single page before "
        f"responding, including page {page_count} (the last page) — do not stop after the first "
        "few pages. List every page number you reviewed in the `pages_reviewed` field."
    )


def check_coverage(result: dict, page_count: int, agent_name: str) -> dict:
    """Pop `pages_reviewed` out of a tool result and report any gap vs. the true page count."""
    reviewed = sorted(set(result.pop("pages_reviewed", []) or []))
    if not page_count:
        return {"total": 0, "reviewed": reviewed, "missing": []}
    missing = sorted(set(range(1, page_count + 1)) - set(reviewed))
    if missing:
        logger.warning(
            "%s: reported reading %d/%d pages; missing %s", agent_name, len(reviewed), page_count, missing
        )
    return {"total": page_count, "reviewed": reviewed, "missing": missing}


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
            return _recover_leaked_arrays(block.input)
    raise RuntimeError(f"Model did not call tool {tool_name}")
