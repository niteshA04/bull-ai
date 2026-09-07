"""Fixed dependency-graph orchestrator (not agent-decided routing) — see PLAN.md §3.

Classification runs first; Financial Table, Narrative, and Chart Data run in parallel
once classification completes; Metrics depends on Financial Table; Reconciliation
depends on Financial Table + Narrative + Chart Data; Assembly depends on everything;
Render depends on Assembly.
"""
from __future__ import annotations

import asyncio

from . import config
from .agents import assembly, chart_data, classification, financial_table, ingestion, metrics, narrative, reconciliation, render
from .models import Job, StepStatus


def _coverage_detail(ingested: dict, agent_name: str, ok_detail: str = "") -> str:
    cov = (ingested.get("_coverage") or {}).get(agent_name)
    if not cov or not cov["total"]:
        return ok_detail
    if cov["missing"]:
        return f"WARNING: read {len(cov['reviewed'])}/{cov['total']} pages, missed {cov['missing']}"
    return ok_detail


async def run_pipeline(job: Job):
    try:
        job.status = "running"

        job.emit("ingestion", StepStatus.RUNNING)
        ingested = await asyncio.to_thread(ingestion.ingest, job.file_path)
        job.outputs["ingested"] = ingested
        job.emit("ingestion", StepStatus.DONE)

        job.emit("classification", StepStatus.RUNNING)
        cls = await asyncio.to_thread(classification.classify, ingested, job.company_name)
        job.outputs["classification"] = cls
        job.emit(
            "classification",
            StepStatus.DONE,
            detail=_coverage_detail(ingested, "classification", cls.get("company_name", "")),
        )

        job.emit("financial_table", StepStatus.RUNNING)
        job.emit("narrative", StepStatus.RUNNING)
        job.emit("chart_data", StepStatus.RUNNING)

        tables_task = asyncio.create_task(asyncio.to_thread(financial_table.extract_tables, ingested))
        chart_task = asyncio.create_task(asyncio.to_thread(chart_data.extract_charts, ingested))

        tables = await tables_task
        job.outputs["tables_raw"] = tables
        job.emit("financial_table", StepStatus.DONE, detail=_coverage_detail(ingested, "financial_table"))

        narr = await asyncio.to_thread(narrative.write_narrative, ingested, cls, tables)
        job.outputs["narrative"] = narr
        job.emit("narrative", StepStatus.DONE, detail=_coverage_detail(ingested, "narrative"))

        charts = await chart_task
        job.outputs["charts"] = charts
        job.emit("chart_data", StepStatus.DONE, detail=_coverage_detail(ingested, "chart_data"))

        job.emit("metrics", StepStatus.RUNNING)
        tables_with_metrics = await asyncio.to_thread(metrics.compute_metrics, tables)
        job.outputs["tables"] = tables_with_metrics
        job.emit("metrics", StepStatus.DONE)

        job.emit("reconciliation", StepStatus.RUNNING)
        recon = await asyncio.to_thread(reconciliation.reconcile, ingested, tables_with_metrics, narr)
        chart_flags = reconciliation.verify_chart_points(charts, ingested)
        flags = recon.get("flags", []) + chart_flags
        job.outputs["flags"] = flags
        recon_detail = _coverage_detail(ingested, "reconciliation", f"{len(flags)} flag(s)")
        job.emit("reconciliation", StepStatus.DONE, detail=recon_detail)

        job.emit("assembly", StepStatus.RUNNING)
        ctx = assembly.assemble(
            company_name=job.company_name,
            classification=cls,
            tables=tables_with_metrics,
            narrative=narr,
            chart_data=charts,
            flags=flags,
        )
        job.outputs["context"] = ctx
        job.emit("assembly", StepStatus.DONE)

        job.emit("render", StepStatus.RUNNING)
        output_path = str(config.OUTPUTS_DIR / f"{job.id}.pdf")
        await asyncio.to_thread(render.render_pdf, ctx, output_path)
        job.output_path = output_path
        job.emit("render", StepStatus.DONE)

        job.status = "done"
        job.queue.put_nowait({"step": "_complete", "label": "Complete", "status": "done", "detail": "", "ts": 0})
    except Exception as e:  # noqa: BLE001
        job.status = "failed"
        job.error = str(e)
        job.queue.put_nowait({"step": "_error", "label": "Failed", "status": "failed", "detail": str(e), "ts": 0})
