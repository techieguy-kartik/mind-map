"""SQS worker for durable ingestion and investigation execution."""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import signal
import time
import threading
from contextlib import contextmanager

from . import cloud, db, research, sources,primary_sources
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


def _sync_with_budget(entity_id,source_id='gdelt',feed='announcements'):
    for attempt in range(4):
        result=sources.sync(entity_id) if source_id=='gdelt' else primary_sources.sync(entity_id,source_id,feed=feed)
        if result.get('status')!='Deferred' or attempt==3:
            return result
        time.sleep(min(120,max(1,result.get('retry_after_seconds',1)))+1)


@contextmanager
def renew_lease(client,url,receipt):
    stop_renewal=threading.Event()
    visibility=max(60,int(os.getenv('ATLAS_QUEUE_VISIBILITY_SECONDS','300')))
    def heartbeat():
        while not stop_renewal.wait(visibility/3):
            try:
                client.change_message_visibility(QueueUrl=url,ReceiptHandle=receipt,VisibilityTimeout=visibility)
            except Exception:
                log.warning('SQS lease renewal failed; job may be redelivered')
    thread=threading.Thread(target=heartbeat,daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop_renewal.set()
        thread.join(timeout=5)


def execute(message: dict, queue_kind: str) -> dict:
    if message.get('version') != 1 or not isinstance(message.get('job_id'), str) or not re.fullmatch(r'[A-Za-z0-9._-]{1,128}',message['job_id']):
        raise ValueError('unsupported or missing message envelope')
    action = message.get('action')
    job_id = message['job_id']
    _checkpoint(job_id, 'running', action=action, queue=queue_kind)
    if action == 'sync_entity' and queue_kind == 'ingestion':
        result = _sync_with_budget(message.get('entity_id', ''),message.get('source_id','gdelt'),message.get('feed','announcements'))
        if result.get('status') != 'Healthy':
            raise RuntimeError('Source collection failed; SQS must retry this message')
    elif action == 'sync_watchlist' and queue_kind == 'ingestion':
        from .freshness import collection_status
        pending=[]
        for entity_id in _watchlist():
            rule=db.get('watch_rule',entity_id) or {'enabled':True,'priority':3,'interval_seconds':1800,'sources':['gdelt']}
            if not rule['enabled']:continue
            for source_id in rule['sources']:
                age=collection_status(entity_id,source_id=source_id)['collection_age_seconds']
                if age is None or age>=rule['interval_seconds']:
                    pending.append((rule['priority'],entity_id,source_id,age))
        limit=max(1,min(1000,int(os.getenv('ATLAS_SCHEDULE_BATCH_SIZE','100'))))
        selected=sorted(pending,key=lambda item:(-item[0],-(item[3] if item[3] is not None else float('inf')),item[1],item[2]))[:limit]
        for _,entity_id,source_id,_ in selected:
            cloud.dispatch('ingestion','sync_entity',entity_id=entity_id,source_id=source_id)
        result={'queued':len(selected),'entities':len({item[1] for item in selected}),'due':len(pending),'remaining':len(pending)-len(selected)}
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
                with renew_lease(client,url,envelope['ReceiptHandle']):
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
