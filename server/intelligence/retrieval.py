"""Hybrid lexical, temporal and bounded knowledge-graph retrieval."""

from __future__ import annotations

import math
import re
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any

ROUTE_TERMS = {
    "capital": {"invest", "funding", "deal", "acquisition", "stake", "valuation", "capital", "merger", "commitment"},
    "people": {"founder", "owner", "leader", "executive", "board", "advisor", "meeting", "hiring", "roles", "talent"},
    "technology": {"ai", "compute", "chip", "quantum", "energy", "6g", "research", "product", "technology", "infrastructure"},
    "geography": {"market", "regulator", "approval", "government", "country", "sanction"},
    "risk": {"risk", "lawsuit", "probe", "recall", "breach", "outage", "controversy", "threat"},
    "strategy": {"strategy", "next", "future", "direction", "plan", "signal", "changing", "milestone", "partnership"},
}


def tokens(value: str) -> set[str]:
    return {word for word in re.findall(r"[a-z0-9]+", value.casefold()) if len(word) > 1}


def _age_score(published_at: str) -> float:
    try:
        value = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        days = max(0.0, (datetime.now(timezone.utc) - value).total_seconds() / 86400)
        return math.exp(-days / 180)
    except (AttributeError, TypeError, ValueError):
        return 0.0


def _provenance(event: dict[str, Any]) -> dict[str, Any]:
    first = (event.get("evidence") or [{}])[0]
    evidence_class = first.get("evidence_class", "synthetic" if event.get("demo") else "unclassified")
    tier = first.get("trust_tier", 9 if event.get("demo") else 8)
    prior = first.get("source_prior", 0.0 if event.get("demo") else 0.2)
    return {"evidence_class": evidence_class, "trust_tier": tier, "source_prior": prior}


def graph_neighborhood(entity_id: str, edges: list[dict[str, Any]], *, demo: bool, max_hops: int = 2, max_nodes: int = 100) -> list[dict[str, Any]]:
    adjacency: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    for edge in edges:
        if bool(edge.get("demo")) != demo:
            continue
        source, target = edge.get("source"), edge.get("target")
        if not source or not target:
            continue
        adjacency[source].append((target, edge))
        adjacency[target].append((source, edge))
    queue = deque([(entity_id, 0)])
    seen = {entity_id}
    result: list[dict[str, Any]] = []
    while queue and len(seen) <= max_nodes:
        node, hop = queue.popleft()
        if hop >= max_hops:
            continue
        for neighbor, edge in adjacency.get(node, []):
            if neighbor in seen:
                continue
            seen.add(neighbor)
            result.append({"entity_id": neighbor, "hop": hop + 1, "edge_id": edge.get("id"), "event_id": edge.get("event_id"), "relation": edge.get("relation")})
            if len(seen) >= max_nodes:
                break
            queue.append((neighbor, hop + 1))
    return result


def _timestamp(value):
    parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _known_at(row, cutoff, *, edge=False):
    try:
        if _timestamp(row['observed_at'])>cutoff:
            return False
        effective=row.get('effective_from') if edge else row['published_at']
        if effective and _timestamp(effective)>cutoff:
            return False
        if edge and row.get('effective_to') and _timestamp(row['effective_to'])<=cutoff:
            return False
        return True
    except (KeyError,ValueError,TypeError,AttributeError):
        return False


def retrieve(entity: dict[str, Any], question: str, routes: list[str], events: list[dict[str, Any]], edges: list[dict[str, Any]], *, demo: bool, candidate_limit: int = 60, as_of: str | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if as_of:
        cutoff=_timestamp(as_of)
        events=[row for row in events if _known_at(row,cutoff)]
        edges=[row for row in edges if _known_at(row,cutoff,edge=True)]
    neighborhood = graph_neighborhood(entity["id"], edges, demo=demo)
    related = {item["entity_id"]: item["hop"] for item in neighborhood}
    graph_event_ids = {item["event_id"] for item in neighborhood if item.get("event_id")}
    query_tokens = tokens(question) | tokens(entity.get("name", ""))
    route_terms = set().union(*(ROUTE_TERMS.get(route, set()) for route in routes))
    candidates: list[dict[str, Any]] = []
    for event in events:
        if bool(event.get("demo")) != demo:
            continue
        event_entities = set(event.get("entities") or [])
        direct = entity["id"] in event_entities or event.get("entity_id") == entity["id"]
        hop_values = [related[item] for item in event_entities if item in related]
        graph_match = event.get("id") in graph_event_ids or bool(hop_values)
        if not direct and not graph_match:
            continue
        text = " ".join(str(event.get(key, "")) for key in ("title", "summary", "event_type"))
        event_tokens = tokens(text)
        lexical = len(query_tokens & event_tokens) / max(1, len(query_tokens))
        intent = len(route_terms & event_tokens) / max(1, min(5, len(route_terms)))
        provenance = _provenance(event)
        hop = 0 if direct else min(hop_values or [2])
        recency=_age_score(event.get('published_at','')) if not as_of else math.exp(-max(0,(cutoff-_timestamp(event['published_at'])).total_seconds()/86400)/180)
        score = (0.34 * lexical) + (0.22 if direct else 0.08 / max(1, hop)) + (0.18 * recency) + (0.16 * float(provenance["source_prior"])) + (0.10 * intent)
        candidates.append({
            "id": event["id"], "title": event.get("title", ""), "summary": event.get("summary", ""),
            "url": event.get("source_url"), "published_at": event.get("published_at"), "observed_at": event.get("observed_at"),
            "event_type": event.get("event_type"), "entities": event.get("entities", []), "demo": bool(event.get("demo")),
            "direct": direct, "graph_hop": hop, "score": round(score, 6), **provenance,
        })
    candidates.sort(key=lambda item: (-item["score"], item.get("published_at") or "", item["id"]))
    return candidates[:candidate_limit], neighborhood


def diverse_rerank(candidates: list[dict[str, Any]], *, limit: int = 16, diversity: float = 0.25) -> list[dict[str, Any]]:
    """Greedy MMR-style selection using transparent token Jaccard similarity."""
    pool = candidates.copy()
    selected: list[dict[str, Any]] = []
    while pool and len(selected) < limit:
        best = None
        best_value = -1.0
        for item in pool:
            item_tokens = tokens(item["title"] + " " + item["summary"])
            redundancy = 0.0
            for prior in selected:
                prior_tokens = tokens(prior["title"] + " " + prior["summary"])
                redundancy = max(redundancy, len(item_tokens & prior_tokens) / max(1, len(item_tokens | prior_tokens)))
            value = (1 - diversity) * item["score"] - diversity * redundancy
            if value > best_value:
                best, best_value = item, value
        assert best is not None
        selected.append(best)
        pool.remove(best)
    return selected
