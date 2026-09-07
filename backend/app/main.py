from __future__ import annotations

import asyncio
import json
import logging
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .models import job_store
from .orchestrator import run_pipeline

logging.basicConfig(level=logging.INFO)
logging.getLogger("app").setLevel(logging.INFO)

app = FastAPI(title="Financial Research Report Generator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ALLOWED_EXT = {".pdf", ".csv", ".txt"}


@app.post("/api/jobs")
async def create_job(company_name: str = Form(...), file: UploadFile = File(...)):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"Unsupported file type '{ext}'. Use PDF, CSV, or TXT.")

    dest_name = f"{uuid.uuid4().hex[:12]}{ext}"
    dest_path = config.UPLOADS_DIR / dest_name
    contents = await file.read()
    dest_path.write_bytes(contents)

    job = job_store.create(company_name=company_name, filename=file.filename or dest_name, file_path=str(dest_path))
    asyncio.create_task(run_pipeline(job))
    return {"job_id": job.id}


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return {
        "id": job.id,
        "status": job.status,
        "error": job.error,
        "steps": {k: v.value for k, v in job.steps.items()},
        "has_output": job.output_path is not None,
    }


@app.get("/api/jobs/{job_id}/events")
async def job_events(request: Request, job_id: str):
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    async def _idle_until_disconnect():
        # Keep the SSE connection open after the terminal event instead of ending the
        # HTTP response — if we end it, the browser's EventSource treats that as an
        # unexpected disconnect and auto-reconnects, which replays the terminal event a
        # second time and can flip the UI to the error state right after showing success.
        while not await request.is_disconnected():
            await asyncio.sleep(1)

    async def stream():
        if job.status in ("done", "failed"):
            step = "_complete" if job.status == "done" else "_error"
            yield f"data: {json.dumps({'step': step, 'label': '', 'status': job.status, 'detail': job.error or '', 'ts': 0})}\n\n"
            await _idle_until_disconnect()
            return
        while True:
            event = await job.queue.get()
            yield f"data: {json.dumps(event)}\n\n"
            if event["step"] in ("_complete", "_error"):
                await _idle_until_disconnect()
                break

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/api/jobs/{job_id}/download")
async def download(job_id: str):
    job = job_store.get(job_id)
    if not job or not job.output_path:
        raise HTTPException(404, "Report not ready")
    filename = f"{job.company_name.replace(' ', '_')}_Research_Report.pdf"
    return FileResponse(job.output_path, media_type="application/pdf", filename=filename)


frontend_dir = Path(__file__).resolve().parent.parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
