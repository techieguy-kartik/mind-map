"""SQS worker for durable ingestion and investigation execution."""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import signal
import time

from . import cloud, db, research, sources
from .runtime_config import load_runtime_secrets

log = logging.getLogger('atlas.worker')
running = True


def stop(_signum, _frame):
    global running
    running = False


def _watchlist() -> list[str]:
    with db.connect() as connection:
        return [row['entity_id'] for row in connection.execute('SELECT entity_id FROM watchlist ORDER BY entity_id')]


def _checkpoint(job_id: str, state: str, **details) -> None:
    try:
        cloud.checkpoint(job_id, state, **details)
    except Exception:
        log.warning('checkpoint write failed id=%s state=%s', job_id, state, exc_info=True)


def execute(message: dict, queue_kind: str) -> dict:
    if message.get('version') != 1 or not isinstance(message.get('job_id'), str) or not re.fullmatch(r'[A-Za-z0-9._-]{1,128}',message['job_id']):
        raise ValueError('unsupported or missing message envelope')
    action = message.get('action')
    job_id = message['job_id']
    _checkpoint(job_id, 'running', action=action, queue=queue_kind)
    if action == 'sync_entity' and queue_kind == 'ingestion':
        result = sources.sync(message.get('entity_id', ''))
        if result.get('status') != 'Healthy':
            raise RuntimeError('Source collection failed; SQS must retry this message')
    elif action == 'sync_watchlist' and queue_kind == 'ingestion':
        results = []
        for entity_id in _watchlist():
            results.append(sources.sync(entity_id))
            time.sleep(float(os.getenv('ATLAS_SOURCE_DELAY_SECONDS', '1')))
        if any(item.get('status') != 'Healthy' for item in results):
            raise RuntimeError('Watchlist collection incomplete; SQS must retry this message')
        result = {'entities': len(results), 'inserted': sum(r.get('inserted', 0) for r in results)}
    elif action == 'run_investigation' and queue_kind == 'analysis':
        investigation_id = message.get('investigation_id', '')
        with db.connect() as connection:
            row = connection.execute('SELECT data FROM investigations WHERE id=?', (investigation_id,)).fetchone()
        if not row:
            raise ValueError('investigation no longer exists')
        job = json.loads(row['data'])
        if job.get('status') == 'completed':
            return {'investigation_id': investigation_id, 'status': 'already_completed'}
        research.run(job)
        outcome=db.get_job(investigation_id) or {}
        if outcome.get('status') in ('deferred','failed'):
            raise RuntimeError('Analysis incomplete; SQS must retry or redrive this message')
        result = {'investigation_id': investigation_id}
    else:
        raise ValueError(f'action {action!r} is not valid for the {queue_kind} queue')
    _checkpoint(job_id, 'completed', result=result)
    return result


def run(queue_kind: str, once: bool = False) -> None:
    url = cloud.queue_url(queue_kind)
    if not url:
        raise RuntimeError(f'ATLAS_{queue_kind.upper()}_QUEUE_URL is required')
    client = cloud._boto3().client('sqs', region_name=os.getenv('AWS_REGION', 'us-east-1'))
    db.initialize(recover_jobs=False)
    log.info('worker ready queue=%s', queue_kind)
    while running:
        response = client.receive_message(
            QueueUrl=url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=1 if once else 20,
            VisibilityTimeout=int(os.getenv('ATLAS_QUEUE_VISIBILITY_SECONDS', '300')),
            AttributeNames=['ApproximateReceiveCount'],
        )
        messages = response.get('Messages', [])
        if not messages and once:
            return
        for envelope in messages:
            job_id = 'unknown'
            try:
                message = json.loads(envelope['Body'])
                job_id = message.get('job_id', job_id)
                result = execute(message, queue_kind)
                client.delete_message(QueueUrl=url, ReceiptHandle=envelope['ReceiptHandle'])
                try:
                    cloud.write_run_manifest(job_id, 'completed', queue=queue_kind, result=result)
                except Exception:
                    log.warning('run manifest write failed id=%s', job_id, exc_info=True)
                log.info('job completed id=%s result=%s', job_id, result)
            except Exception as exc:
                _checkpoint(job_id, 'failed_attempt', error=type(exc).__name__)
                try:
                    cloud.write_run_manifest(job_id, 'failed_attempt', queue=queue_kind, error=type(exc).__name__)
                except Exception:
                    log.warning('failure manifest write failed id=%s', job_id, exc_info=True)
                log.exception('job failed id=%s; SQS will retry or redrive it', job_id)
        if once:
            return


def main() -> None:
    load_runtime_secrets()
    parser = argparse.ArgumentParser()
    parser.add_argument('--queue', choices=('ingestion', 'analysis'), required=True)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    logging.basicConfig(level=os.getenv('ATLAS_LOG_LEVEL', 'INFO'), format='%(asctime)s %(levelname)s %(name)s %(message)s')
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    run(args.queue, args.once)


if __name__ == '__main__':
    main()
