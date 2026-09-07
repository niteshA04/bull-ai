"""Agent 1 — Ingestion (deterministic, no LLM).

Routes the uploaded file by format:
- PDF: kept as raw bytes, handed downstream as a native `document` content block so
  LLM agents can reason over layout/charts visually (see PLAN.md "Ingestion note").
  A best-effort text layer is also extracted (pypdf) purely for the Reconciliation
  agent's cheap text cross-check — never used as the primary extraction source for PDFs.
- CSV/TXT: parsed to plain text in code; this text *is* the primary content for those
  formats, sent to LLM agents as text rather than a document block.
"""
from __future__ import annotations

from pathlib import Path


def ingest(file_path: str) -> dict:
    ext = Path(file_path).suffix.lower()
    if ext == ".pdf":
        text_layer, page_count = _extract_pdf_text(file_path)
        return {
            "format": "pdf",
            "mode": "native_document",
            "file_path": file_path,
            "text_layer": text_layer,
            "page_count": page_count,
        }
    if ext in (".csv", ".txt"):
        text = Path(file_path).read_text(encoding="utf-8", errors="ignore")
        return {
            "format": "csv" if ext == ".csv" else "txt",
            "mode": "text",
            "file_path": file_path,
            "text": text,
        }
    raise ValueError(f"Unsupported file format: {ext}")


def _extract_pdf_text(file_path: str) -> tuple[str, int]:
    try:
        from pypdf import PdfReader

        reader = PdfReader(file_path)
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
        return text, len(reader.pages)
    except Exception:
        return "", 0
