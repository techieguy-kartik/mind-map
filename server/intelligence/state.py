from __future__ import annotations

import operator
from typing import Annotated, Any
from typing_extensions import TypedDict


class InvestigationState(TypedDict, total=False):
    job: dict[str, Any]
    entity: dict[str, Any]
    question: str
    demo: bool
    routes: list[str]
    candidates: list[dict[str, Any]]
    graph_context: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    context: str
    retrieval: dict[str, Any]
    sufficiency: dict[str, Any]
    draft: dict[str, Any]
    validation_passed: bool
    audit: dict[str, Any]
    mode: str
    status: str
    result: str
    citations: list[str]
    alternatives: list[str]
    missing_evidence: list[str]
    error: str
    trace: Annotated[list[dict[str, Any]], operator.add]
