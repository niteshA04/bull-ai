"""Agent 8 — Assembly (deterministic, no LLM).

Merges every upstream agent's output into one context object keyed by report_schema.json
field IDs, applying the fallback policy uniformly (never ad hoc per template section).
"""
from __future__ import annotations

import datetime as dt

from .. import config

FALLBACK = config.FALLBACK_POLICY


def _fallback_string(v):
    return v if v not in (None, "") else FALLBACK["missing_string"]


def _fallback_number(v):
    return v if isinstance(v, (int, float)) else FALLBACK["missing_number"]


def _clean_table(section: dict, values: dict) -> dict:
    """Drop rows with no values at all (missing_table_row -> omit_row); fallback per-cell."""
    if section.get("orientation") == "key_value":
        cleaned = {}
        for row in section["rows"]:
            v = (values or {}).get(row)
            if v is None:
                continue
            cleaned[row] = v if isinstance(v, str) else _fallback_number(v)
        return cleaned

    cleaned = {}
    for row in section["rows"]:
        row_vals = (values or {}).get(row) or {}
        if not any(row_vals.get(c) is not None for c in section["columns"]):
            continue
        cleaned[row] = {c: _fallback_number(row_vals.get(c)) for c in section["columns"]}
    return cleaned


def assemble(*, company_name: str, classification: dict, tables: dict, narrative: dict, chart_data: dict, flags: list[dict]) -> dict:
    ctx: dict = {"generated_at": dt.datetime.now().strftime("%d-%B-%Y, %H:%M") + "hrs"}

    ctx["company_name"] = classification.get("company_name") or company_name
    ctx["sector"] = _fallback_string(classification.get("sector"))
    ctx["report_tag"] = _fallback_string(classification.get("report_period") and f"{classification['report_period']} Result Update")
    ctx["report_date"] = dt.datetime.now().strftime("%d %B, %Y")
    ctx["data_as_of"] = ctx["generated_at"]

    header_fields = tables.get("header") or {}
    ctx["header"] = {k: _fallback_string(header_fields.get(k)) for k in
                      config.REPORT_SCHEMA["pages"][0]["sections"][0]["fields"]}
    ctx["header"]["company_name"] = ctx["company_name"]
    ctx["header"]["sector"] = ctx["sector"]

    rating_fields = tables.get("rating_box") or {}
    rating = narrative.get("rating") or rating_fields.get("rating")
    target = narrative.get("target_price") or rating_fields.get("target_price")
    ctx["rating_box"] = {
        **{k: _fallback_string(rating_fields.get(k)) for k in
           config.REPORT_SCHEMA["pages"][0]["sections"][1]["fields"] if k not in ("rating", "target_price", "sensex", "cmp", "return_pct")},
        "rating": rating or "NOT RATED",
        "target_price": _fallback_number(target),
        "cmp": _fallback_number(rating_fields.get("cmp")),
        "sensex": _fallback_number(rating_fields.get("sensex")),
        "return_pct": _fallback_number(rating_fields.get("return_pct")),
    }

    ctx["headline"] = _fallback_string(narrative.get("headline"))
    ctx["company_description"] = _fallback_string(narrative.get("company_description"))
    ctx["key_highlights"] = narrative.get("key_highlights") or []
    ctx["key_highlights_page2"] = narrative.get("key_highlights_page2") or []
    ctx["outlook_valuation"] = _fallback_string(narrative.get("outlook_valuation"))

    table_section_lookup = {
        s["id"]: s
        for page in config.REPORT_SCHEMA["pages"]
        for s in page["sections"]
        if s["type"] == "table" and not s.get("dynamic")
    }
    ctx["tables"] = {
        sid: _clean_table(section, tables.get(sid))
        for sid, section in table_section_lookup.items()
    }

    ctx["charts"] = {k: v for k, v in (chart_data or {}).items() if v}

    ctx["reconciliation_flags"] = flags or []

    ctx["recommendation_summary_table"] = []  # dynamic, history not derivable from a single doc
    ctx["analyst_name"] = FALLBACK["missing_string"]
    ctx["analyst_signature_date"] = ctx["report_date"]

    return ctx
