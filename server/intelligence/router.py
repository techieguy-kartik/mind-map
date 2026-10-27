"""Deterministic query routing before retrieval."""

from __future__ import annotations

import re

ROUTES: dict[str, tuple[str, ...]] = {
    "capital": ("invest", "investing", "investment", "funding", "funded", "deal", "acquisition", "stake", "valuation", "capital", "merger"),
    "people": ("founder", "owner", "leader", "executive", "board", "investor", "advisor", "meeting", "hiring", "talent"),
    "technology": ("ai", "model", "compute", "chip", "quantum", "energy", "6g", "patent", "research", "product", "technology"),
    "geography": ("country", "market", "regulator", "approval", "government", "india", "china", "europe", "united states", "sanction"),
    "risk": ("risk", "lawsuit", "probe", "investigation", "recall", "breach", "outage", "controversy", "threat"),
    "strategy": ("strategy", "next", "future", "direction", "priority", "plan", "interest", "signal", "signals", "why", "changing"),
}


def route_question(question: str, *, limit: int = 3) -> list[str]:
    text = re.sub(r"\s+", " ", question.casefold()).strip()
    scored: list[tuple[int, str]] = []
    for route, phrases in ROUTES.items():
        score = sum((2 if " " in phrase else 1) for phrase in phrases if re.search(rf"\b{re.escape(phrase)}\b", text))
        if score:
            scored.append((score, route))
    scored.sort(key=lambda item: (-item[0], item[1]))
    selected = [route for _, route in scored[:limit]]
    return selected or ["strategy"]
