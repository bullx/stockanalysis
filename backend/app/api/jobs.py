import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.utils.llm import LlmGate
from backend.app.utils.parse import hydrate_agent, hydrate_debate


@dataclass
class Job:
    id: str
    status: str = "queued"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    query: dict | None = None
    round1: dict = field(default_factory=dict)
    round2: dict | None = None
    report: dict | None = None
    error: str | None = None
    gate: LlmGate = field(default_factory=LlmGate)
    events: list[dict] = field(default_factory=list)
    subscribers: list[asyncio.Queue] = field(default_factory=list)
    meta: dict = field(default_factory=dict)


def _jobs_dir() -> Path:
    from backend.app.settings import get_settings

    path = Path(get_settings().output_dir) / "jobs"
    path.mkdir(parents=True, exist_ok=True)
    return path


class JobStore:
    def __init__(self) -> None:
        self.jobs: dict[str, Job] = {}

    def create(self) -> Job:
        job = Job(id=uuid.uuid4().hex[:12])
        self.jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        if job_id in self.jobs:
            return self.jobs[job_id]
        loaded = self._load(job_id)
        if loaded:
            self.jobs[job_id] = loaded
        return loaded

    async def emit(self, job: Job, event: dict[str, Any]) -> None:
        event = {"ts": datetime.now(timezone.utc).isoformat(), **event}
        etype = event.get("type")
        if etype == "query.normalized":
            job.query = event.get("query")
        elif etype == "agent.completed":
            job.round1[event["agent_id"]] = {
                k: event[k]
                for k in ("agent_id", "agent_name", "tag", "output", "conviction", "stance", "error", "timestamp")
                if k in event
            }
        elif etype in {"round2.completed", "round2.skipped"}:
            job.round2 = event.get("debate")
        elif etype == "analysis.started":
            job.status = "running"
            job.meta = {k: event[k] for k in event if k not in {"type", "ts"}}
        elif etype == "round1.started":
            job.meta["agent_ids"] = event.get("agent_ids")
            job.meta["agent_count"] = event.get("total")
        elif etype == "analysis.done":
            job.status = "done"
            job.report = event.get("report")
            job.round1 = event.get("round1") or job.round1
            job.round2 = event.get("round2") or job.round2
            self._save(job)
        elif etype == "analysis.error":
            job.status = "error"
            job.error = event.get("error")
            self._save(job)
        elif etype == "analysis.stopped":
            job.status = "stopped"
            job.error = event.get("error")
            self._save(job)
        job.events.append(event)
        for q in list(job.subscribers):
            await q.put(event)

    def snapshot(self, job: Job) -> dict:
        round1 = {
            key: hydrate_agent(dict(value)) for key, value in (job.round1 or {}).items()
        }
        return {
            "id": job.id,
            "status": job.status,
            "created_at": job.created_at,
            "query": job.query,
            "round1": round1,
            "round2": hydrate_debate(job.round2),
            "report": job.report,
            "error": job.error,
            "meta": job.meta,
        }

    def _save(self, job: Job) -> None:
        payload = {
            "id": job.id,
            "status": job.status,
            "created_at": job.created_at,
            "query": job.query,
            "round1": job.round1,
            "round2": job.round2,
            "report": job.report,
            "error": job.error,
            "meta": job.meta,
        }
        path = _jobs_dir() / f"{job.id}.json"
        path.write_text(json.dumps(payload, default=str), encoding="utf-8")

    def _load(self, job_id: str) -> Job | None:
        path = _jobs_dir() / f"{job_id}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        job = Job(
            id=data.get("id") or job_id,
            status=data.get("status") or "done",
            created_at=data.get("created_at") or datetime.now(timezone.utc).isoformat(),
        )
        job.query = data.get("query")
        job.round1 = data.get("round1") or {}
        job.round2 = data.get("round2")
        job.report = data.get("report")
        job.error = data.get("error")
        job.meta = data.get("meta") or {}
        return job


store = JobStore()
