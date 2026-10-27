"""Small AWS control-plane adapter with no silent mock mode.

The web process can run without AWS for local development. Once a queue URL is
configured, dispatch failures are explicit so work is never reported as queued
when it was actually dropped.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4


def queue_url(kind: str) -> str:
    key = 'ATLAS_INGESTION_QUEUE_URL' if kind == 'ingestion' else 'ATLAS_ANALYSIS_QUEUE_URL'
    return os.getenv(key, '').strip()


def enabled(kind: str) -> bool:
    return bool(queue_url(kind))


def _boto3():
    try:
        import boto3
        return boto3
    except ImportError as exc:
        raise RuntimeError('AWS queue configured but boto3 is not installed') from exc


def dispatch(kind: str, action: str, **payload) -> str:
    url = queue_url(kind)
    if not url:
        raise RuntimeError(f'{kind} queue is not configured')
    job_id = payload.pop('job_id', None) or str(uuid4())
    message = {
        'version': 1,
        'job_id': job_id,
        'action': action,
        'created_at': datetime.now(timezone.utc).isoformat(),
        **payload,
    }
    client = _boto3().client('sqs', region_name=os.getenv('AWS_REGION', 'us-east-1'))
    client.send_message(QueueUrl=url, MessageBody=json.dumps(message, separators=(',', ':')))
    return job_id


def checkpoint(job_id: str, state: str, **details) -> None:
    table = os.getenv('ATLAS_CONTROL_TABLE', '').strip()
    if not table:
        return
    now = datetime.now(timezone.utc).isoformat()
    item = {
        'pk': {'S': f'JOB#{job_id}'},
        'sk': {'S': f'STATE#{now}'},
        'state': {'S': state},
        'updated_at': {'S': now},
        'details': {'S': json.dumps(details, separators=(',', ':'), default=str)[:12000]},
        'expires_at': {'N': str(int((datetime.now(timezone.utc) + timedelta(days=90)).timestamp()))},
    }
    client = _boto3().client('dynamodb', region_name=os.getenv('AWS_REGION', 'us-east-1'))
    client.put_item(TableName=table, Item=item)


def write_run_manifest(job_id: str, state: str, **details) -> None:
    bucket = os.getenv('ATLAS_EVIDENCE_BUCKET', '').strip()
    if not bucket:
        return
    now = datetime.now(timezone.utc)
    body = json.dumps({
        'version': 1,
        'job_id': job_id,
        'state': state,
        'recorded_at': now.isoformat(),
        'details': details,
    }, separators=(',', ':'), default=str).encode()
    key = f"runs/{now:%Y/%m/%d}/{job_id}-{now:%H%M%S%f}.json"
    _boto3().client('s3', region_name=os.getenv('AWS_REGION', 'us-east-1')).put_object(
        Bucket=bucket,
        Key=key,
        Body=body,
        ContentType='application/json',
        ServerSideEncryption='AES256',
    )
