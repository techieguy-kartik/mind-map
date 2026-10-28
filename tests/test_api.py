import json
import time
from datetime import datetime,timezone
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from server import backup,cloud,db,evidence,research,sources,worker
from server.app import app,login_attempts


@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('ATLAS_DB',str(tmp_path/'test.sqlite3'))
    monkeypatch.setenv('ATLAS_DEMO','true')
    monkeypatch.setenv('ATLAS_HOST','127.0.0.1')
    monkeypatch.delenv('ATLAS_ACCESS_TOKEN',raising=False)
    monkeypatch.delenv('GROQ_API_KEY',raising=False)
    monkeypatch.delenv('ATLAS_INGESTION_QUEUE_URL',raising=False)
    monkeypatch.delenv('ATLAS_ANALYSIS_QUEUE_URL',raising=False)
    monkeypatch.delenv('ATLAS_CONTROL_TABLE',raising=False)
    monkeypatch.delenv('ATLAS_EVIDENCE_BUCKET',raising=False)
    monkeypatch.delenv('ATLAS_RUNTIME_SECRET_ID',raising=False)
    login_attempts.clear()
    with TestClient(app) as c:
        yield c


def test_seed_truth_and_idempotence(client):
    first=client.get('/api/workspace').json()
    assert len(first['entities'])==22
    assert len(first['events'])==6
    assert all(e['demo'] and e['source_url'] is None for e in first['events'])
    assert all(e['qualification']=='Not yet verified' for e in first['entities'] if e['type']=='company')
    db.initialize()
    assert len(client.get('/api/workspace').json()['events'])==6


def test_watchlist_persists_and_validates_identity(client):
    assert client.put('/api/watchlist/tesla',json={'watched':True}).status_code==200
    assert 'tesla' in client.get('/api/workspace').json()['watchlist']
    client.put('/api/watchlist/tesla',json={'watched':False})
    assert 'tesla' not in client.get('/api/workspace').json()['watchlist']
    assert client.put('/api/watchlist/unknown',json={'watched':True}).status_code==404


def test_missing_evidence_does_not_use_demo(client):
    job={'id':'no-evidence','entity_id':'jio','question':'What is the strategy?','created_at':datetime.now(timezone.utc).isoformat(),'demo':False,'status':'queued'}
    research.run(job)
    saved=client.get('/api/investigations/no-evidence').json()
    assert saved['status']=='completed' and saved['citations']==[]
    assert 'Insufficient evidence' in saved['result']


def test_no_key_is_not_fake_ai(client):
    job={'id':'demo-job','entity_id':'jio','question':'What is changing?','created_at':datetime.now(timezone.utc).isoformat(),'demo':True,'status':'queued'}
    research.run(job)
    saved=client.get('/api/investigations/demo-job').json()
    assert saved['mode']=='evidence-only'
    assert 'synthetic' in saved['result'] and 'no AI synthesis' in saved['result']


def test_daily_limit_is_enforced(client,monkeypatch):
    monkeypatch.setenv('ATLAS_DAILY_INVESTIGATIONS','1')
    with patch('server.app.pool.submit'):
        assert client.post('/api/investigations',json={'entity_id':'tesla','question':'What are the next steps?','demo':False}).status_code==202
        assert client.post('/api/investigations',json={'entity_id':'tesla','question':'What are the next steps?','demo':False}).status_code==429


def test_authentication_and_cross_origin(client,monkeypatch):
    token='test-private-token-with-enough-length'
    monkeypatch.setenv('ATLAS_ACCESS_TOKEN',token)
    assert client.get('/api/workspace').status_code==401
    assert client.post('/api/session',json={'token':'wrong'}).status_code==401
    response=client.post('/api/session',json={'token':token})
    assert response.status_code==200 and 'HttpOnly' in response.headers['set-cookie']
    assert client.get('/api/workspace').status_code==200
    assert client.put('/api/watchlist/tesla',json={'watched':True},headers={'Origin':'https://evil.invalid'}).status_code==403


def test_real_evidence_creates_idempotent_graph_edge(client):
    body={'source_entity':'jio','target_entity':'reliance','relation':'subsidiary_of','statement':'A test-only reviewed relationship statement; not real corporate evidence.','source_url':'https://example.org/disclosure','publisher':'Test publisher','effective_date':'2026-01-01','reviewed':True}
    response=client.post('/api/evidence',json=body)
    assert response.status_code==201
    client.post('/api/evidence',json=body)
    workspace=client.get('/api/workspace').json()
    assert len([e for e in workspace['events'] if not e['demo']])==1
    edge=[e for e in workspace['edges'] if not e['demo']][0]
    assert edge['status']=='User-reviewed'
    assert edge['evidence'][0]['text']==body['statement']
    assert client.post('/api/evidence',json={**body,'source_url':'javascript:alert(1)'}).status_code==422
    assert client.post('/api/evidence',json={**body,'target_entity':'jio'}).status_code==422
    assert client.post('/api/evidence',json={**body,'effective_date':'2026-02-31'}).status_code==422
    assert client.post('/api/evidence',json={**body,'reviewed':False}).status_code==422


def test_groq_invalid_citations_rejected(client,monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY','fake-test-key')
    job={'id':'bad-cite','entity_id':'jio','question':'What is changing?','created_at':datetime.now(timezone.utc).isoformat(),'demo':True,'status':'queued'}
    with patch('server.research.httpx.Client') as mocked:
        response=mocked.return_value.__enter__.return_value.post.return_value
        response.status_code=200
        response.json.return_value={'choices':[{'message':{'content':json.dumps({'result':'Untrusted answer','citations':['invented-id']})}}]}
        research.run(job)
    assert client.get('/api/investigations/bad-cite').json()['status']=='failed'


def test_groq_rate_limit_is_explicit(client,monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY','fake-test-key')
    job={'id':'rate-limit','entity_id':'jio','question':'What is changing?','created_at':datetime.now(timezone.utc).isoformat(),'demo':True,'status':'queued'}
    with patch('server.research.httpx.Client') as mocked:
        mocked.return_value.__enter__.return_value.post.return_value.status_code=429
        research.run(job)
    saved=client.get('/api/investigations/rate-limit').json()
    assert saved['status']=='deferred' and saved['evidence']


def test_ingest_deduplicates_rejects_bad_urls_and_matches_alias(client):
    with patch('server.sources.httpx.Client') as mocked:
        response=mocked.return_value.__enter__.return_value.get.return_value
        response.json.return_value={'articles':[
            {'title':'Tesla announces a test example','url':'https://example.org/test','seendate':'20260101T120000Z'},
            {'title':'Tesla unsafe source','url':'javascript:alert(1)'},
            {'title':'Not the company requested','url':'https://example.org/other'},
        ]}
        assert sources.sync('tesla')['inserted']==1
        assert sources.sync('tesla')['inserted']==0
    events=[e for e in db.records('event') if not e['demo']]
    assert len(events)==1 and events[0]['status']=='Reported'
    assert events[0]['evidence'][0]['kind']=='headline'
    assert not [e for e in db.records('edge') if not e['demo']]


def test_restart_marks_interrupted_job(client):
    db.save_job({'id':'interrupted','created_at':'2026-01-01','status':'running'})
    db.initialize()
    assert client.get('/api/investigations/interrupted').json()['status']=='interrupted'


def test_input_validation_and_missing_job(client):
    assert client.post('/api/investigations',json={'entity_id':'tesla','question':'short'}).status_code==422
    assert client.get('/api/investigations/not-found').status_code==404


def test_freshness_endpoint_validates_entity_and_does_not_invent_collection(client):
    result=client.get('/api/entities/tesla/freshness')
    assert result.status_code==200
    assert result.json()['status']=='never_collected'
    assert result.json()['last_success'] is None
    assert client.get('/api/entities/unknown/freshness').status_code==404


def test_empty_live_initialization(tmp_path,monkeypatch):
    monkeypatch.setenv('ATLAS_DB',str(tmp_path/'live.sqlite3'))
    monkeypatch.setenv('ATLAS_DEMO','false')
    db.initialize()
    assert len(db.records('entity'))==19
    assert db.records('event')==[] and db.records('edge')==[]


def test_evidence_policy_is_explicit_and_bounded():
    primary=evidence.envelope('primary_regulatory',retrieved_at='2026-01-01T00:00:00+00:00')
    lead=evidence.envelope('reporting_lead',retrieved_at='2026-01-01T00:00:00+00:00')
    assert primary['trust_tier'] < lead['trust_tier']
    assert primary['source_prior'] > lead['source_prior']
    with pytest.raises(ValueError):
        evidence.envelope('invented')


def test_durable_source_dispatch_is_visible(client,monkeypatch):
    sent=[]
    class SQS:
        def send_message(self,**kwargs): sent.append(kwargs)
    class AWS:
        def client(self,*_args,**_kwargs): return SQS()
    monkeypatch.setenv('ATLAS_INGESTION_QUEUE_URL','https://sqs.us-east-1.amazonaws.com/123/ingestion')
    monkeypatch.setattr(cloud,'_boto3',lambda:AWS())
    response=client.post('/api/sources/gdelt/sync',json={'entity_id':'tesla'})
    assert response.status_code==200 and response.json()['status']=='Queued'
    assert sent and json.loads(sent[0]['MessageBody'])['entity_id']=='tesla'
    source=[s for s in client.get('/api/workspace').json()['sources'] if s['id']=='gdelt'][0]
    assert source['status']=='Queued'


def test_worker_rejects_wrong_queue_action(monkeypatch):
    monkeypatch.setattr(cloud,'checkpoint',lambda *_args,**_kwargs:None)
    with pytest.raises(ValueError):
        worker.execute({'version':1,'job_id':'job-1','action':'run_investigation'},'ingestion')
    with pytest.raises(ValueError):
        worker.execute({'version':1,'job_id':'../../bad','action':'sync_watchlist'},'ingestion')


def test_sqlite_backup_is_consistent(client,tmp_path):
    destination=backup.create_backup(tmp_path/'backup.sqlite3')
    import sqlite3
    with sqlite3.connect(destination) as connection:
        assert connection.execute("SELECT value FROM meta WHERE key='seed_version'").fetchone()[0]=='1'
        assert connection.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
