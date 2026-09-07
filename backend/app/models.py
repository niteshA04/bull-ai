import asyncio
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


PIPELINE_STEPS = [
    ("ingestion", "Reading uploaded document"),
    ("classification", "Identifying company and report sections"),
    ("financial_table", "Extracting financial tables"),
    ("narrative", "Writing narrative and highlights"),
    ("metrics", "Computing derived ratios"),
    ("chart_data", "Preparing chart data"),
    ("reconciliation", "Reconciling figures against the source"),
    ("assembly", "Assembling report data"),
    ("render", "Rendering PDF"),
]


@dataclass
class Job:
    id: str
    company_name: str
    filename: str
    file_path: str
    created_at: float = field(default_factory=time.time)
    status: str = "pending"  # pending | running | done | failed
    error: Optional[str] = None
    output_path: Optional[str] = None
    steps: dict = field(default_factory=lambda: {k: StepStatus.PENDING for k, _ in PIPELINE_STEPS})
    outputs: dict = field(default_factory=dict)
    queue: "asyncio.Queue" = field(default_factory=asyncio.Queue)

    def emit(self, step: str, status: StepStatus, detail: str = ""):
        self.steps[step] = status
        label = dict(PIPELINE_STEPS).get(step, step)
        event = {
            "step": step,
            "label": label,
            "status": status.value,
            "detail": detail,
            "ts": time.time(),
        }
        self.queue.put_nowait(event)


class JobStore:
    def __init__(self):
        self._jobs: dict[str, Job] = {}

    def create(self, company_name: str, filename: str, file_path: str) -> Job:
        job_id = uuid.uuid4().hex[:12]
        job = Job(id=job_id, company_name=company_name, filename=filename, file_path=file_path)
        self._jobs[job_id] = job
        return job

    def get(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)


job_store = JobStore()
