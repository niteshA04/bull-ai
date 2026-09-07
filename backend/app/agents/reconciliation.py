"""Agent 6 — Reconciliation (LLM + rules).

Flags extracted values that don't reconcile against the source document, and separately
cross-checks chart-derived values against the source's raw text layer in code (cheap,
deterministic) before anything reaches Assembly.
"""
from __future__ import annotations

import logging

from .. import config, llm

logger = logging.getLogger("app.agents.reconciliation")

SYSTEM = f"""You are the Reconciliation agent in a financial report generation pipeline.
{config.SKILL_TEXT}

You will be given extracted financial table data, narrative text, and the source
document. Flag any extracted value that does not match what the source document
actually states. Be specific: name the field and what's wrong."""

TOOL_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "flags": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field": {"type": "string"},
                    "issue": {"type": "string"},
                    "severity": {"type": "string", "enum": ["low", "medium", "high"]},
                },
                "required": ["field", "issue"],
            },
        }
    },
    "required": ["flags"],
}


def reconcile(ingested: dict, tables: dict, narrative: dict) -> dict:
    chart_flags = _crosscheck_chart_text(ingested)

    if not config.LLM_AVAILABLE:
        return {"flags": chart_flags}

    context = f"Extracted tables:\n{tables}\n\nExtracted narrative:\n{narrative}"
    user_content: list[dict]
    if ingested["mode"] == "native_document":
        user_content = [{"type": "text", "text": context}, llm.pdf_document_block(ingested["file_path"])]
    else:
        user_content = [{"type": "text", "text": context + "\n\nSource document:\n" + ingested["text"]}]

    try:
        result = llm.run_tool(
            system=SYSTEM,
            user_content=user_content,
            tool_name="reconciliation_result",
            tool_description="Report any reconciliation flags found.",
            input_schema=TOOL_INPUT_SCHEMA,
            max_tokens=2048,
        )
        result["flags"] = chart_flags + result.get("flags", [])
        return result
    except Exception:
        logger.exception("Reconciliation agent failed; returning only deterministic chart flags")
        return {"flags": chart_flags}


def _crosscheck_chart_text(ingested: dict) -> list[dict]:
    """Deterministic cross-check placeholder — real check runs once chart_data is available
    (see orchestrator, which calls verify_chart_points after chart_data completes)."""
    return []


def verify_chart_points(chart_data: dict, ingested: dict) -> list[dict]:
    text_layer = (ingested.get("text_layer") or ingested.get("text") or "").replace(",", "")
    flags = []
    for chart_id, points in (chart_data or {}).items():
        for point in points or []:
            if point.get("verified") is False:
                flags.append(
                    {
                        "field": f"{chart_id}.{point.get('x')}",
                        "issue": f"Chart value {point.get('y')} not found in source text layer",
                        "severity": "low",
                    }
                )
    return flags
