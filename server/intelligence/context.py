"""Priority-aware evidence packing with an explicit token budget."""

from __future__ import annotations

import json
from typing import Any


def estimate_tokens(text: str) -> int:
    return max(1, (len(text) + 3) // 4)


def pack_context(evidence: list[dict[str, Any]], *, token_budget: int = 3200) -> tuple[str, list[dict[str, Any]]]:
    blocks: list[str] = []
    included: list[dict[str, Any]] = []
    used = 0
    for item in evidence:
        compact = {
            "id": item["id"], "title": item["title"], "summary": item["summary"],
            "published_at": item.get("published_at"), "event_type": item.get("event_type"),
            "evidence_class": item.get("evidence_class"), "trust_tier": item.get("trust_tier"),
            "direct": item.get("direct"), "graph_hop": item.get("graph_hop"), "url": item.get("url"),
        }
        block = json.dumps(compact, ensure_ascii=False, separators=(",", ":"))
        cost = estimate_tokens(block)
        if used + cost > token_budget:
            continue
        blocks.append(block)
        included.append(item)
        used += cost
    return "\n".join(blocks), included
