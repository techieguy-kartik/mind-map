"""Per-company collection freshness, distinct from source publication latency."""
from datetime import datetime, timezone
import os

from . import db


def collection_status(entity_id, *, now=None,source_id='gdelt'):
    now = now or datetime.now(timezone.utc)
    state = db.get('source_entity_run', f'{source_id}:{entity_id}') or {}
    threshold = max(60, int(os.getenv('ATLAS_FRESHNESS_SECONDS', '1800')))
    age = None
    try:
        timestamp = datetime.fromisoformat(state['last_success'].replace('Z', '+00:00'))
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        age = max(0, int((now - timestamp).total_seconds()))
    except (KeyError, TypeError, ValueError, AttributeError):
        pass
    status = 'never_collected' if age is None else ('fresh' if age <= threshold else 'stale')
    if state.get('status') == 'Error':
        status = 'error'
    return {
        'entity_id': entity_id, 'source_id': source_id, 'status': status,
        'last_attempt': state.get('last_attempt'), 'last_success': state.get('last_success'),
        'collection_age_seconds': age, 'freshness_threshold_seconds': threshold,
        'last_error': state.get('error'),
        'meaning': 'Time since a successful collection check; not a guarantee of publisher coverage or publication latency.',
    }
