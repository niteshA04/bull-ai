"""Agent 3 — Financial Table (LLM, structured output).

Extracts every table-shaped section in report_schema.json (P&L, balance sheet, cashflow,
ratios, quarterly financials, annual estimates, and the small data tables on page 1).
Numbers only — no arithmetic here (that's the Metrics agent); return null for anything
not present in the source rather than estimating.
"""
from __future__ import annotations

import logging

from .. import config, llm

logger = logging.getLogger("app.agents.financial_table")

TABLE_SECTIONS = [
    s
    for page in config.REPORT_SCHEMA["pages"]
    for s in page["sections"]
    if s["type"] == "table" and not s.get("dynamic")
]

FIELD_SECTIONS = [
    s
    for page in config.REPORT_SCHEMA["pages"]
    for s in page["sections"]
    if s["type"] == "fields"
]

SYSTEM = f"""You are the Financial Table extraction agent in a financial report generation pipeline.
{config.SKILL_TEXT}

Extract every numeric table defined in the tool schema from the source document. Only use
figures actually present in the document (tables preferred over narrative text). Return
null for any cell you cannot find — never estimate or infer a number that isn't stated."""


def _table_schema(section: dict) -> dict:
    if section.get("orientation") == "key_value":
        props = {row: {"type": ["number", "string", "null"]} for row in section["rows"]}
        return {"type": "object", "properties": props}
    row_schema = {
        "type": "object",
        "properties": {col: {"type": ["number", "null"]} for col in section["columns"]},
    }
    return {
        "type": "object",
        "properties": {row: row_schema for row in section["rows"]},
    }


def _fields_schema(section: dict) -> dict:
    props = {name: {"type": ["number", "string", "null"]} for name in section["fields"]}
    return {"type": "object", "properties": props}


TOOL_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        **{s["id"]: _table_schema(s) for s in TABLE_SECTIONS},
        **{s["id"]: _fields_schema(s) for s in FIELD_SECTIONS},
    },
}


def extract_tables(ingested: dict) -> dict:
    if not config.LLM_AVAILABLE:
        return {}
    user_content = _build_user_content(ingested)
    try:
        return llm.run_tool(
            system=SYSTEM,
            user_content=user_content,
            tool_name="financial_tables",
            tool_description="Report all extracted financial table data.",
            input_schema=TOOL_INPUT_SCHEMA,
            max_tokens=8192,
        )
    except Exception:
        logger.exception("Financial Table agent failed; falling back to no table data")
        return {}


def _build_user_content(ingested: dict) -> list[dict]:
    instruction = "Extract all financial tables from this document per the schema."
    if ingested["mode"] == "native_document":
        return [
            {"type": "text", "text": instruction},
            llm.pdf_document_block(ingested["file_path"]),
        ]
    return [{"type": "text", "text": instruction + "\n\nDocument content:\n" + ingested["text"]}]
