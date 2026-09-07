"""Agent 2 — Classification (LLM, structured output)."""
from __future__ import annotations

import logging

from .. import config, llm

logger = logging.getLogger("app.agents.classification")

SYSTEM = f"""You are the Classification agent in a financial report generation pipeline.
{config.SKILLS['classification']}

Given the ingested content of a company's financial document, identify the company,
the type of document, and which report sections (by id, from report_schema.json) the
source document actually contains enough information to fill."""

SCHEMA_SECTION_IDS = [
    s["id"]
    for page in config.REPORT_SCHEMA["pages"]
    for s in page["sections"]
]

TOOL_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "company_name": {"type": "string"},
        "sector": {"type": ["string", "null"]},
        "doc_type": {
            "type": "string",
            "description": "e.g. quarterly_results, annual_report, investor_presentation, financial_statement_csv",
        },
        "report_period": {"type": ["string", "null"], "description": "e.g. Q2FY26"},
        "sections_present": {
            "type": "array",
            "items": {"type": "string", "enum": SCHEMA_SECTION_IDS},
        },
        "sections_absent": {
            "type": "array",
            "items": {"type": "string", "enum": SCHEMA_SECTION_IDS},
        },
        "pages_reviewed": llm.PAGES_REVIEWED_FIELD,
    },
    "required": ["company_name", "doc_type", "sections_present", "sections_absent", "pages_reviewed"],
}


def classify(ingested: dict, fallback_company_name: str) -> dict:
    if not config.LLM_AVAILABLE:
        return {
            "company_name": fallback_company_name,
            "sector": None,
            "doc_type": "unknown",
            "report_period": None,
            "sections_present": [],
            "sections_absent": SCHEMA_SECTION_IDS,
        }

    user_content = _build_user_content(ingested, fallback_company_name)
    try:
        result = llm.run_tool(
            system=SYSTEM,
            user_content=user_content,
            tool_name="classification_result",
            tool_description="Report the classification of this financial document.",
            input_schema=TOOL_INPUT_SCHEMA,
        )
        ingested.setdefault("_coverage", {})["classification"] = llm.check_coverage(
            result, ingested.get("page_count", 0), "classification"
        )
        return result
    except Exception:
        logger.exception("Classification agent failed; falling back to unclassified")
        return {
            "company_name": fallback_company_name,
            "sector": None,
            "doc_type": "unknown",
            "report_period": None,
            "sections_present": [],
            "sections_absent": SCHEMA_SECTION_IDS,
        }


def _build_user_content(ingested: dict, fallback_company_name: str) -> list[dict]:
    prefix = (
        f"The user says the company name is '{fallback_company_name}'. "
        "Confirm or correct it from the document itself."
    )
    if ingested["mode"] == "native_document":
        prefix += llm.coverage_instruction(ingested.get("page_count", 0))
        return [
            {"type": "text", "text": prefix},
            llm.pdf_document_block(ingested["file_path"]),
        ]
    return [{"type": "text", "text": prefix + "\n\nDocument content:\n" + ingested["text"]}]
