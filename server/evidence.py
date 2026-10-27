"""Deterministic provenance envelopes used before any model sees evidence."""
from __future__ import annotations

from datetime import datetime, timezone

CLASSES = {
    'primary_regulatory': (1, 0.98),
    'issuer_disclosure': (1, 0.95),
    'official_public_record': (1, 0.93),
    'official_social_statement': (2, 0.78),
    'user_reviewed': (2, 0.80),
    'reporting_lead': (3, 0.60),
    'open_source_discovery': (4, 0.45),
    'synthetic': (9, 0.0),
}


def envelope(evidence_class: str, *, retrieved_at: str | None = None) -> dict:
    if evidence_class not in CLASSES:
        raise ValueError(f'unknown evidence class: {evidence_class}')
    tier, prior = CLASSES[evidence_class]
    return {
        'evidence_class': evidence_class,
        'trust_tier': tier,
        'source_prior': prior,
        'retrieved_at': retrieved_at or datetime.now(timezone.utc).isoformat(),
    }
