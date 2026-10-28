"""Investigation entry point used by the API and durable analysis worker."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx

from . import db
from .intelligence.workflow import run_workflow


def _persist_stage(job: dict, node: str, update: dict) -> None:
    if not job:
        return
    current = db.get_job(job["id"]) or job.copy()
    current["workflow_node"] = node
    current["workflow_updated_at"] = datetime.now(timezone.utc).isoformat()
    current["trace"] = (current.get("trace") or []) + (update.get("trace") or [])
    for key in ("routes", "retrieval", "sufficiency", "audit", "evidence", "status", "mode", "result", "citations", "alternatives", "missing_evidence", "error"):
        if key in update:
            current[key] = update[key]
    db.save_job(current)


def run(job):
    job["status"] = "running"
    job["trace"] = []
    db.save_job(job)
    try:
        entity = db.get("entity", job["entity_id"])
        if not entity:
            raise KeyError("unknown entity")
        state = run_workflow(job, entity, persist=_persist_stage)
        for key in ("routes", "retrieval", "sufficiency", "audit", "evidence", "status", "mode", "result", "citations", "alternatives", "missing_evidence", "error", "trace"):
            if key in state:
                job[key] = state[key]
        job["workflow_node"] = "complete"
    except (httpx.HTTPError, json.JSONDecodeError, ValueError, KeyError, IndexError, TypeError):
        job.update(db.get_job(job['id']) or {})
        job.update(status="failed", error="The research provider response could not be validated. Evidence was retained; no conclusion was accepted.")
    except Exception:
        job.update(db.get_job(job['id']) or {})
        job.update(status="failed", error="Investigation interrupted by an internal error. No conclusion was accepted.")
    job["finished_at"] = datetime.now(timezone.utc).isoformat()
    db.save_job(job)
