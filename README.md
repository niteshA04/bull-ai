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
- **Frontend**: static HTML/CSS/vanilla JS (served by FastAPI itself), styled per
  `SKILL.md`'s Apple-design principles — instant press feedback, spring-like step
  animations, translucent cards, `prefers-reduced-motion` support

## Where the template fields are defined

**`backend/report_schema.json`** is the single source of truth: section order, every
table's columns/rows, chart specs, and the fallback policy. Everything downstream reads
from it:

- `backend/app/skill/SKILL.md` — the packaged "Claude Agent Skill" (formatting
  conventions, extraction priority, example input→output pairs) loaded into every
  LLM agent's system prompt alongside the schema
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

## API

- `POST /api/jobs` — multipart form (`company_name`, `file`) → `{job_id}`
- `GET /api/jobs/{id}` — current status snapshot
- `GET /api/jobs/{id}/events` — SSE stream of per-agent progress
- `GET /api/jobs/{id}/download` — the generated PDF

## Example outputs

Two generated reports from the provided test set are in [`examples/`](examples/):
`ICICI_Q2FY26_Report.pdf`, `JSW_Energy_Q2FY26_Report.pdf` — generated without an API key
configured, so they exercise the fallback-policy path end-to-end. With a real
`ANTHROPIC_API_KEY` set, the same documents populate every table/narrative/chart field.

## Known gaps vs. the full PLAN.md

- No persistent job store (Postgres/Redis) — jobs live in-memory for the process
  lifetime; fine for local use, would need adding for multi-worker deployment.
- `recommendation_summary_table` (page 4 rating history) is always empty — a single
  source document has no prior-rating history to extract; a real deployment would pull
  this from a database of past calls, not the uploaded document.
