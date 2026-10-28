import json
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from server import db, research
from server.intelligence.context import estimate_tokens, pack_context
from server.intelligence.retrieval import graph_neighborhood
from server.intelligence.router import route_question
from server.intelligence.workflow import build_workflow


@pytest.fixture
def intelligence_db(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DB", str(tmp_path / "intelligence.sqlite3"))
    monkeypatch.setenv("ATLAS_DEMO", "true")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    db.initialize()


def make_job(id="rag-job"):
    return {
        "id": id, "entity_id": "jio",
        "question": "Where is Jio investing in AI infrastructure and what strategy signals exist?",
        "created_at": datetime.now(timezone.utc).isoformat(), "demo": True, "status": "queued",
    }


def test_router_selects_bounded_retrieval_units():
    routes = route_question("Which investors funded its quantum technology and who is on the board?")
    assert set(routes) == {"capital", "people", "technology"}
    assert route_question("Explain this company") == ["strategy"]


def test_graph_has_real_conditional_nodes():
    graph = build_workflow().get_graph()
    assert {"route", "retrieve", "assess", "synthesize", "validate", "audit", "finalize_inventory"} <= set(graph.nodes)
    assert any(edge.source == "assess" and edge.conditional for edge in graph.edges)


def test_graph_traversal_is_bounded_and_dataset_isolated():
    edges = [
        {"id": "a", "source": "root", "target": "one", "event_id": "e1", "demo": False},
        {"id": "b", "source": "one", "target": "two", "event_id": "e2", "demo": False},
        {"id": "c", "source": "two", "target": "three", "event_id": "e3", "demo": False},
        {"id": "demo", "source": "root", "target": "fiction", "event_id": "e4", "demo": True},
    ]
    result = graph_neighborhood("root", edges, demo=False, max_hops=2)
    assert [item["entity_id"] for item in result] == ["one", "two"]
    assert all(item["entity_id"] != "fiction" for item in result)


def test_context_packer_enforces_budget():
    items = [
        {"id": str(i), "title": "Signal", "summary": "x" * 180, "published_at": "2026-01-01", "event_type": "News", "evidence_class": "reporting_lead", "trust_tier": 3, "direct": True, "graph_hop": 0, "url": None}
        for i in range(20)
    ]
    context, included = pack_context(items, token_budget=350)
    assert included and len(included) < len(items)
    assert estimate_tokens(context) <= 350


def test_worker_initialization_does_not_interrupt_sqs_job(intelligence_db):
    job = make_job("queued-for-worker")
    db.save_job(job)
    db.initialize(recover_jobs=False)
    assert db.get_job("queued-for-worker")["status"] == "queued"


def test_evidence_only_workflow_exposes_trace_and_retrieval(intelligence_db):
    research.run(make_job())
    saved = db.get_job("rag-job")
    assert saved["status"] == "completed" and saved["mode"] == "evidence-only"
    assert set(saved["routes"]) == {"technology", "capital", "strategy"}
    assert saved["retrieval"]["direct_count"] >= 1
    assert saved["retrieval"]["max_graph_hops"] <= 2
    assert [item["node"] for item in saved["trace"]] == ["route", "retrieve", "assess", "finalize"]


def test_valid_groq_output_is_audited(intelligence_db, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "fake-test-key")
    with patch("server.intelligence.workflow.httpx.Client") as mocked:
        response = mocked.return_value.__enter__.return_value.post.return_value
        response.status_code = 200
        response.json.return_value = {"choices": [{"message": {"content": json.dumps({
            "result": "The fictional records suggest a possible infrastructure theme; this is not real company activity.",
            "citations": ["demo-1"],
            "alternatives": ["The scenario may describe routine capacity work."],
            "missing_evidence": ["A primary company disclosure is absent."],
        })}}]}
        research.run(make_job("audited-job"))
    saved = db.get_job("audited-job")
    assert saved["status"] == "completed" and saved["mode"] == "groq-rag"
    assert saved["audit"]["citation_allowlist_passed"] is True
    assert saved["audit"]["cited_evidence_count"] == 1
    assert saved["trace"][-1]["node"] == "audit"


def test_provider_exception_retains_persisted_retrieval(intelligence_db, monkeypatch):
    import httpx
    monkeypatch.setenv('GROQ_API_KEY','fake-test-key')
    with patch('server.intelligence.workflow.httpx.Client') as client:
        client.return_value.__enter__.return_value.post.side_effect=httpx.ConnectError('provider unavailable')
        research.run(make_job('provider-failure'))
    saved=db.get_job('provider-failure')
    assert saved['status']=='failed'
    assert saved['evidence']
    assert saved['trace'][-1]['node']=='assess'
