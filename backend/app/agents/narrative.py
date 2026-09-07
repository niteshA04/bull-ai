"""Agent 4 — Narrative (LLM, structured output)."""
from __future__ import annotations

import logging

from .. import config, llm

logger = logging.getLogger("app.agents.narrative")

SYSTEM = f"""You are the Narrative agent in a financial report generation pipeline.
{config.SKILL_TEXT}

Write the narrative sections of the report in the analyst voice of an equity research
note: concise, factual, numbers-backed. Respect the max_words limits exactly. Every
claim must be traceable to the source document — do not editorialize beyond what the
document supports."""

TOOL_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string", "description": "<=15 words, e.g. 'Blinkit propels growth; valuation limits upside'"},
        "company_description": {"type": "string", "description": "<=60 words"},
        "key_highlights": {
            "type": "array",
            "items": {"type": "string"},
            "description": "3-8 bullet points, <=40 words each",
        },
        "outlook_valuation": {
            "type": "string",
            "description": "<=150 words; final sentence must state the rating and target price",
        },
        "key_highlights_page2": {
            "type": "array",
            "items": {"type": "string"},
            "description": "3-6 bullet points, <=60 words each, deeper detail than page 1 highlights",
        },
        "rating": {
            "type": "string",
            "enum": ["BUY", "ACCUMULATE", "HOLD", "REDUCE", "SELL", "NOT RATED"],
        },
        "target_price": {"type": ["number", "null"]},
    },
    "required": ["headline", "company_description", "key_highlights", "outlook_valuation", "rating"],
}


def write_narrative(ingested: dict, classification: dict, tables: dict) -> dict:
    if not config.LLM_AVAILABLE:
        return {}
    user_content = _build_user_content(ingested, classification, tables)
    try:
        return llm.run_tool(
            system=SYSTEM,
            user_content=user_content,
            tool_name="narrative_result",
            tool_description="Report the written narrative sections of the report.",
            input_schema=TOOL_INPUT_SCHEMA,
            max_tokens=2048,
        )
    except Exception:
        logger.exception("Narrative agent failed; falling back to no narrative")
        return {}


def _build_user_content(ingested: dict, classification: dict, tables: dict) -> list[dict]:
    context = (
        f"Company: {classification.get('company_name')}\n"
        f"Doc type: {classification.get('doc_type')}\n"
        f"Already-extracted financial tables (for numeric grounding):\n{tables}\n\n"
        "Write the narrative sections based on the source document below."
    )
    if ingested["mode"] == "native_document":
        return [
            {"type": "text", "text": context},
            llm.pdf_document_block(ingested["file_path"]),
        ]
    return [{"type": "text", "text": context + "\n\nDocument content:\n" + ingested["text"]}]
