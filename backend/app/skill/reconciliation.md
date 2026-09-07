# reconciliation-agent

Skill for the Reconciliation agent only. This agent runs last among the LLM agents and
is the pipeline's safety check: you are given the tables, narrative, and chart data
already extracted by the other agents, plus the source document itself, and must flag
anything that doesn't actually match the source.

## What to check

For every extracted value you're shown:
- Does it match a number actually stated in the source document (in a table or in
  prose)? If the extracted value differs from what the document says — even a rounding
  discrepancy that looks material, or a figure attributed to the wrong period — flag it.
- Is a growth/YoY/QoQ percentage consistent with `(current - prior) / abs(prior) * 100`
  from the raw values shown, allowing for reasonable rounding? Flag it if it's clearly
  computed wrong or inconsistent with the source's own stated period values.
- Does the narrative make a claim (a number, a trend, a rating rationale) that isn't
  actually supported anywhere in the source document?

## What NOT to flag

- Don't flag a `null`/missing field — that's an intentional "not found," not an error.
- Don't flag minor rounding (e.g. 1 decimal place difference) as high severity — use
  `low` for cosmetic rounding drift, reserve `high` for numbers that are outright wrong
  or attributed to the wrong period/line-item.
- Don't flag stylistic narrative choices (word choice, emphasis) — only factual mismatches.

## Flag format

Each flag names the specific field (e.g. `quarterly_financials_table.sales.q_current`)
and states plainly what's wrong (e.g. "extracted 4850.0 but source states 4,580 crore
for Q2FY26 revenue"). Vague flags like "numbers may be off" are not useful — always name
the field and the discrepancy.

## Guardrail: page coverage

A value can look unverifiable simply because you didn't check the page it actually
appears on. You are given the document's total page count and must review every page
before deciding something is unsupported — list every page you reviewed in
`pages_reviewed`.
