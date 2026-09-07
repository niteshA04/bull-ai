# Financial Research Report Generator

Upload a company name + a financial document (PDF/CSV/TXT) and get back a formatted
equity-research PDF report — tables, narrative, and charts — modeled on the Geojit
sample report. See [PLAN.md](PLAN.md) for the full design and [WHY_THIS_APPROACH.md](WHY_THIS_APPROACH.md)
for the reasoning behind the architecture.

## Run it

```bash
cd backend
../.venv/Scripts/python -m pip install -r requirements.txt   # already done if you followed setup
../.venv/Scripts/python -m playwright install chromium       # one-time, downloads a headless browser for PDF rendering
cp .env.example .env                                         # then put your real key in .env
../.venv/Scripts/python -m uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000 — the FastAPI server also serves the frontend directly (no
separate frontend process needed). Enter a company name, upload a PDF/CSV/TXT, watch the
per-agent progress, and download the PDF when it finishes.

**Without an `ANTHROPIC_API_KEY`** the app still runs end-to-end — every LLM agent falls
back to `null`/omitted output, and the schema's fallback policy (`—`, `N/A`, omitted rows,
omitted charts) fills the report, so you can verify the pipeline and template before
wiring up a real key.

## Tech stack

- **Backend**: Python/FastAPI, `asyncio` job orchestration, Server-Sent Events for
  per-agent progress
- **LLM**: Anthropic Claude via the `anthropic` SDK — native PDF document input for
  PDF sources (chart/infographic pages are read visually, not text-extracted), plain
  code parsing for CSV/TXT
- **PDF render**: Playwright (headless Chromium) over a Jinja2-templated HTML/CSS page
  — chosen over WeasyPrint because WeasyPrint requires native GTK/Pango/Cairo libraries
  that aren't available out of the box on Windows; Playwright ships its own browser
  and needs nothing extra installed on the OS
- **Charts**: hand-rolled inline SVG (`backend/app/charts.py`) — kept dependency-free
  (no matplotlib/numpy) since this environment's Python (3.14) has no prebuilt wheels
  for those yet and no C toolchain to build them from source
- **Frontend**: static HTML/CSS/vanilla JS (served by FastAPI itself) — instant press
  feedback, spring-like step animations, translucent cards, `prefers-reduced-motion`
  support

## Where the template fields are defined

**`backend/report_schema.json`** is the single source of truth: section order, every
table's columns/rows, chart specs, and the fallback policy. Everything downstream reads
from it:

- `backend/app/skill/*.md` — one curated skill file per LLM agent (`classification.md`,
  `financial_table.md`, `narrative.md`, `chart_data.md`, `reconciliation.md`), each with
  that agent's own formatting conventions, extraction priority, and example
  input→output pairs — not a shared prompt, so one agent's behavior can be tuned
  without affecting the others
- `backend/app/agents/financial_table.py`, `narrative.py`, `chart_data.py` — build
  their tool (structured-output) schemas directly from `report_schema.json`, so a
  schema change propagates without touching agent code
- `backend/app/templates/report.html` + `report.css` — the 4-page HTML template,
  filled by `backend/app/agents/render.py`
- `backend/app/templates/static_page4.html` — the static Investment Rating Criteria /
  disclaimer partial (not agent-generated, per PLAN.md §4)

## Pipeline (fixed DAG, not LLM-routed)

```
Ingestion (code) → Classification (LLM)
                         │
      ┌──────────────────┼──────────────────┐
      ▼                  ▼                  ▼
Financial Table (LLM) Narrative (LLM)  Chart Data (LLM)
      │                  │                  │
      ▼                  │                  │
 Metrics (code)           │                  │
      └──────────────────┴──────────────────┘
                         ▼
              Reconciliation (LLM + rules)
                         ▼
                  Assembly (code)
                         ▼
                   Render (code)
                         ▼
                       PDF
```

Each transition emits an SSE event (`GET /api/jobs/{id}/events`) consumed by the frontend
as a step list.

### Page-coverage guardrail

Every PDF-consuming agent is told the document's true page count and required to report
every page it actually reviewed (`pages_reviewed` in its tool schema). If an agent's
reported pages don't cover the full document, that gap is logged and surfaced in the
step's progress detail (e.g. `WARNING: read 8/12 pages, missed [9, 10, 11, 12]`) instead
of failing silently.

### Malformed tool-output recovery

On some large documents, Claude occasionally corrupts a string-array tool field into a
malformed shape (a leaked `<parameter name="$0">` tag plus sibling `$1`/`$2`/... keys
instead of a proper JSON array). `backend/app/llm.py`'s `run_tool()` detects this and
reassembles the array before returning — the underlying content is intact, only the
shape was wrong. A `Recovered leaked array field ...` warning in the logs is this
working as intended, not a failure.

## API

- `POST /api/jobs` — multipart form (`company_name`, `file`) → `{job_id}`
- `GET /api/jobs/{id}` — current status snapshot
- `GET /api/jobs/{id}/events` — SSE stream of per-agent progress
- `GET /api/jobs/{id}/download` — the generated PDF

## Sample data

`test_data/` holds five real quarterly-result PDFs used for manual testing. The repo
root also has four generated sample reports (`ICICI_Research_Report.pdf`,
`JSW_Research_Report.pdf`, `LTTS_Research_Report.pdf`, `POCL_Research_Report.pdf`) —
example pipeline output kept for quick visual reference, not part of the app itself
(actual runs write to `backend/storage/uploads/` and `backend/storage/outputs/`, keyed
by job id).
