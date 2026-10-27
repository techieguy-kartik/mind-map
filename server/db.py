import json
import os
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from .seed import seed_data


@contextmanager
def connect():
    path = Path(os.getenv('ATLAS_DB', 'var/atlas.sqlite3'))
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('PRAGMA foreign_keys=ON')
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def initialize():
    with connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS records(kind TEXT NOT NULL, id TEXT NOT NULL, data TEXT NOT NULL, PRIMARY KEY(kind,id));
        CREATE TABLE IF NOT EXISTS watchlist(entity_id TEXT PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS investigations(id TEXT PRIMARY KEY, created_at TEXT NOT NULL, data TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS usage(day TEXT PRIMARY KEY, investigations INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        ''')
        if not db.execute("SELECT 1 FROM meta WHERE key='seed_version'").fetchone():
            for kind, rows in zip(('entity','event','edge','hypothesis'), seed_data(os.getenv('ATLAS_DEMO','true').lower()=='true')):
                for row in rows:
                    db.execute('INSERT OR IGNORE INTO records VALUES(?,?,?)',(kind,row['id'],json.dumps(row)))
            db.executemany('INSERT OR IGNORE INTO watchlist VALUES(?)',[(x,) for x in ('reliance','jio','tata-power','tata-sons','nvidia')])
            db.execute("INSERT INTO meta VALUES('seed_version','1')")
        # In-process jobs cannot survive a crash; never leave a false running status.
        for row in db.execute('SELECT id,data FROM investigations').fetchall():
            data=json.loads(row['data'])
            if data['status'] in ('queued','running'):
                data.update(status='interrupted',error='The server restarted. Submit the investigation again.')
                db.execute('UPDATE investigations SET data=? WHERE id=?',(json.dumps(data),row['id']))


def records(kind):
    with connect() as db:
        return [json.loads(r['data']) for r in db.execute('SELECT data FROM records WHERE kind=?',(kind,))]


def get(kind, id):
    with connect() as db:
        row=db.execute('SELECT data FROM records WHERE kind=? AND id=?',(kind,id)).fetchone()
        return json.loads(row['data']) if row else None


def put(kind, row):
    with connect() as db:
        db.execute('INSERT INTO records VALUES(?,?,?) ON CONFLICT(kind,id) DO UPDATE SET data=excluded.data',(kind,row['id'],json.dumps(row)))


def save_job(job):
    with connect() as db:
        db.execute('INSERT INTO investigations VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data',(job['id'],job['created_at'],json.dumps(job)))


def jobs():
    with connect() as db:
        return [json.loads(r['data']) for r in db.execute('SELECT data FROM investigations ORDER BY created_at DESC LIMIT 100')]
