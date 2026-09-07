"""Agent 7 — Chart Data (LLM, native PDF input for chart/infographic pages)."""
from __future__ import annotations

import logging

from .. import config, llm

logger = logging.getLogger("app.agents.chart_data")

SYSTEM = f"""You are the Chart Data agent in a financial report generation pipeline.
{config.SKILL_TEXT}

Extract chart-ready series data for each chart defined in the tool schema. Charts are
often rendered as bar/line/donut graphics in the source document rather than tables —
read them visually. For each data point, also set `verified` to true only if the same
number also appears in the document's plain text layer given to you for cross-checking,
false otherwise. If a chart's underlying data isn't present in the document at all,
omit that chart from your output entirely (do not fabricate a placeholder series)."""

POINT_SCHEMA = {
    "type": "object",
    "properties": {
        "x": {"type": "string"},
        "y": {"type": "number"},
        "y2": {"type": ["number", "null"], "description": "secondary series value (e.g. line overlay on a bar chart)"},
        "verified": {"type": "boolean"},
    },
    "required": ["x", "y"],
}

CHART_SECTIONS = [
    s
    for page in config.REPORT_SCHEMA["pages"]
    for s in page["sections"]
    if s["type"] == "chart"
]

TOOL_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        s["id"]: {"type": "array", "items": POINT_SCHEMA} for s in CHART_SECTIONS
    },
}


def extract_charts(ingested: dict) -> dict:
    if not config.LLM_AVAILABLE:
        return {}
    user_content = _build_user_content(ingested)
    try:
        return llm.run_tool(
            system=SYSTEM,
            user_content=user_content,
            tool_name="chart_data_result",
            tool_description="Report extracted chart series data.",
            input_schema=TOOL_INPUT_SCHEMA,
            max_tokens=4096,
        )
    except Exception:
        logger.exception("Chart Data agent failed; falling back to no chart data")
        return {}


def _build_user_content(ingested: dict) -> list[dict]:
    text_layer = ingested.get("text_layer") or ingested.get("text") or ""
    instruction = (
        "Extract chart series data from this document. "
        "Here is the document's plain text layer for cross-checking values:\n\n"
        + text_layer[:6000]
    )
    if ingested["mode"] == "native_document":
        return [
            {"type": "text", "text": instruction},
            llm.pdf_document_block(ingested["file_path"]),
        ]
    return [{"type": "text", "text": instruction}]
