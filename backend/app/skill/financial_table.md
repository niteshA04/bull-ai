# financial-table-agent

Skill for the Financial Table agent only. This agent extracts raw numbers into every
table/fields section of `report_schema.json` — no arithmetic, no narrative, numbers only.
The Metrics agent computes derived ratios afterward from what you return; do not
pre-compute anything yourself.

## Source of truth

`report_schema.json` (`config.REPORT_SCHEMA`) defines every table's exact rows/columns
or field names via `TOOL_INPUT_SCHEMA`. Never invent a row/column that isn't in the
schema. Never skip a row/column that is in the schema — if the source document doesn't
state that cell's value, return `null` for it explicitly rather than omitting the key or
guessing a plausible-looking number.

## Extraction priority

1. **Structured tables in the source document** (financial statement tables, data
   tables) — highest trust, always prefer these over prose.
2. **Narrative text** (MD&A, notes, commentary) — use only when a number is genuinely
   absent from every table in the document.
3. **Never** fall back to general knowledge about the company. If a number is not
   present anywhere in this specific document, it is `null` — do not estimate,
   interpolate, or recall it from training knowledge.

## Formatting conventions

- **Currency**: INR crore, no currency symbol in your output (the template adds "₹"/"Cr"
  at render time). Round to 1 decimal place.
- **Percent**: raw number without a `%` sign (e.g. `12.4`, not `"12.4%"`). Keep the `-`
  sign for negative values.
- **Numbers**: no thousands separators (write `4850.0`, not `"4,850.0"`).
- **Dates**: ISO `YYYY-MM-DD` if a table has a date field.
- Do not compute YoY/QoQ growth percentages yourself even if the source text states
  them — return the raw current/prior period values; the Metrics agent recomputes
  growth from those raw numbers as the single source of truth for percentages.

## Example

Input excerpt (from a quarterly results PDF):
> "Revenue for Q2FY26 stood at Rs. 4,850 crore, up 18.2% YoY from Rs. 4,103 crore in
> Q2FY25 and up 4.1% QoQ from Rs. 4,660 crore in Q1FY26."

Expected output for `quarterly_financials_table.sales`:
```json
{"q_current": 4850.0, "q_yoy": 4103.0, "q_qoq": 4660.0}
```
Note: no `*_growth_pct` keys here — those are computed downstream, not extracted.

## Guardrail: page coverage

Tables are frequently spread across multiple pages (a P&L on one page, balance sheet
several pages later, segment data in an annexure). You are given the document's total
page count and must review every page — do not stop once you've found one or two
tables. List every page you reviewed in `pages_reviewed`.

## Fallback policy — not your job

Return `null`/omit values you cannot find. Do NOT substitute display placeholders like
`"N/A"` or `"—"` yourself — that substitution happens once, centrally, in the Assembly
agent after all extraction is done.
