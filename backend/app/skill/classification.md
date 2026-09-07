# classification-agent

Skill for the Classification agent only. This agent runs first in the pipeline and its
output (`company_name`, `doc_type`, `sections_present`/`sections_absent`) gates which
sections the rest of the pipeline attempts to fill.

## Your job

Identify, from the source document alone:
1. The company name — confirm or correct the user-supplied name against what the
   document itself states (letterhead, cover page, footer). Prefer the document over
   the user's input if they conflict; the user's input is often a shorthand or typo.
2. `doc_type` — one of: `quarterly_results`, `annual_report`, `investor_presentation`,
   `financial_statement_csv`, or another short snake_case label if none of those fit.
3. `sector`, `report_period` (e.g. `Q2FY26`) if stated or clearly inferable from dates
   in the document — otherwise `null`. Do not guess a fiscal quarter from a filing date
   alone if the document doesn't state the period itself.

## Section presence — the decision that matters most

`report_schema.json` (loaded alongside this file, `config.REPORT_SCHEMA`) lists every
section id the final report can contain. For each section id, decide:

- **Present**: the document contains *enough concrete data* to fill that section
  (a full table, or narrative text with the specific numbers/facts the section needs).
  A section heading alone with no data under it is NOT present.
- **Absent**: the document doesn't cover that topic at all, or only in passing without
  the numbers the section needs.

Be conservative — marking a section "present" when it isn't causes downstream agents to
return mostly-null data for it, which is worse than omitting the section entirely. When
genuinely unsure, mark it absent.

## Guardrail: page coverage

You are given the document's total page count and must review every page before
deciding section presence — a section's data is often on a page other than where its
heading appears (e.g. segment-wise revenue tables in an annexure at the end). List every
page you reviewed in `pages_reviewed`; this is checked against the true page count.

## Do not

- Do not fabricate a company name, sector, or period not stated in the document.
- Do not use general knowledge about the company (e.g. "I know this company is in the
  IT sector") to fill `sector` if the document itself doesn't state it — return `null`.
