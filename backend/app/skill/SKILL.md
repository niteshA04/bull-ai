# financial-report-extraction

Skill used by the Classification, Financial Table, Narrative, Reconciliation, and Chart Data agents when
generating a Geojit-style equity research report from an uploaded financial document.

## Source of truth

`report_schema.json` (loaded alongside this file) defines every field the report needs: section order,
table columns/rows, chart specs, and the fallback policy for missing data. Never invent a field that is
not in the schema. Never omit a field that is in the schema — if the source document does not contain a
value, say so explicitly (return `null`) rather than guessing.

## Formatting conventions

- **Currency**: INR crore, no currency symbol in raw output (the template adds "₹"/"Cr"). Round to 1 decimal.
- **Percent**: raw number without the `%` sign (e.g. `12.4`, not `"12.4%"`). Negative values keep the `-` sign.
- **Dates**: ISO `YYYY-MM-DD` in structured output; the template formats for display.
- **Growth/YoY/QoQ**: always `(current - prior) / abs(prior) * 100`, never eyeballed from the text.
- **Ratings**: one of `BUY, ACCUMULATE, HOLD, REDUCE, SELL, NOT RATED` exactly as written.
- **Numbers**: never include thousands separators in structured output; the template formats display.
- Never fabricate a number. If a figure is not present in the source document (table or narrative text),
  return `null` for that field rather than estimating or interpolating.

## Extraction priority

1. Structured tables in the source document (financial statement tables, data tables) — highest trust.
2. Narrative text in the source document (MD&A, notes, commentary) — used only when a number is absent
   from tables.
3. Never fall back to general knowledge about the company. If it isn't in the document, it's `null`.

## Example input -> output pair

Input excerpt (from a quarterly results PDF):
> "Revenue for Q2FY26 stood at Rs. 4,850 crore, up 18.2% YoY from Rs. 4,103 crore in Q2FY25 and up 4.1%
> QoQ from Rs. 4,660 crore in Q1FY26. EBITDA margin expanded to 22.3% from 21.1% YoY."

Expected structured output for `quarterly_financials_table.sales`:
```json
{
  "q_current": 4850.0,
  "q_yoy": 4103.0,
  "yoy_growth_pct": 18.23,
  "q_qoq": 4660.0,
  "qoq_growth_pct": 4.08
}
```
Note `yoy_growth_pct`/`qoq_growth_pct` are recomputed from the raw values in code (Metrics agent), not
copied verbatim from the source text, even when the source states a percentage — the source percentage is
used only as a reconciliation cross-check.

## Chart/infographic pages (native PDF input)

When a source page is a bar chart, donut chart, or icon-labeled infographic (common in quarterly result
decks), read it visually — do not rely on any co-located text layer alone, since chart labels and values
are often spatially separated from their numbers. Cross-check every value you read off a chart against the
document's raw text layer before reporting it; if the value cannot be found in the text layer, still report
it as extracted but mark `verified: false` in the Chart Data agent's per-point output.

## Fallback policy (applied by the Assembly agent, not per-agent)

- Missing string field -> `"—"`
- Missing numeric field -> `"N/A"`
- Missing table row -> omit the row entirely (do not render a blank row)
- Missing chart -> omit the chart region, render a placeholder note instead

Agents should return `null`/omit fields they cannot find — they must NOT apply the fallback glyphs
themselves. Fallback substitution happens once, centrally, in Assembly.
