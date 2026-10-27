"""Consistent SQLite backup and optional S3 upload."""
from __future__ import annotations

import argparse
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def create_backup(destination: Path) -> Path:
    source = Path(os.getenv('ATLAS_DB', 'var/atlas.sqlite3'))
    if not source.exists():
        raise FileNotFoundError(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source) as src, sqlite3.connect(destination) as dst:
        src.backup(dst)
    return destination


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    parser.add_argument('--upload', action='store_true')
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime('%Y/%m/%d/atlas-%Y%m%dT%H%M%SZ.sqlite3')
    output = args.output or Path('/app/var/backups') / Path(stamp).name
    create_backup(output)
    if args.upload:
        bucket = os.getenv('ATLAS_EVIDENCE_BUCKET', '')
        if not bucket:
            raise RuntimeError('ATLAS_EVIDENCE_BUCKET is required for upload')
        from .cloud import _boto3
        _boto3().client('s3', region_name=os.getenv('AWS_REGION', 'us-east-1')).upload_file(
            str(output), bucket, f'backups/{stamp}', ExtraArgs={'ServerSideEncryption': 'AES256'}
        )
    print(output)


if __name__ == '__main__':
    main()
