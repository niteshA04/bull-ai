# chart-data-agent

Skill for the Chart Data agent only. This agent extracts chart-ready series data for
every chart section in `report_schema.json`, reading source pages that are often
rendered as bar/line/donut graphics or icon-labeled infographics rather than tables —
common in quarterly result decks and investor presentations.

## Reading charts visually

- Read chart images visually using the native PDF input — do not rely solely on any
  co-located text layer, since chart labels and their values are frequently spatially
  separated from each other (a legend on one side, values as tiny axis labels, etc.).
- For each data point, extract the category/x-label and its value as precisely as the
  chart renders it (read exact bar heights/labels, not eyeballed approximations).

## Cross-checking (`verified` field)

You are also given the document's plain-text layer (extracted separately, for
cross-checking only — never treat it as more authoritative than the chart itself for
values that only appear in the chart). For every point you extract:
- Set `verified: true` only if the same number also appears in that plain text layer.
- Set `verified: false` if it doesn't appear in the text layer, but still report the
  point as read from the chart — do not drop it just because it's unverified.

## What to omit

If a chart's underlying data is not present in the document at all (neither as an image
nor text), omit that chart's key from your output entirely. Never fabricate a
placeholder series to fill a chart section that has no source data.

## Guardrail: page coverage

Charts can appear anywhere in the document, including pages with no other financial
data (a single infographic slide near the end, for instance). You are given the
document's total page count and must review every page — list every page you reviewed
in `pages_reviewed`.
