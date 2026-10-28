from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import httpx
import pytest

from server import db, sources, worker
from server.freshness import collection_status


@pytest.fixture
def storage(tmp_path, monkeypatch):
    monkeypatch.setenv('ATLAS_DB',str(tmp_path/'freshness.sqlite3'))
    monkeypatch.setenv('ATLAS_FRESHNESS_SECONDS','1800')
    db.initialize(recover_jobs=False)


def test_freshness_is_per_company_and_expires(storage):
    now=datetime.now(timezone.utc)
    db.put('source_entity_run',{'id':'gdelt:tesla','status':'Healthy','last_success':now.isoformat()})
    assert collection_status('tesla',now=now)['status']=='fresh'
    assert collection_status('jio',now=now)['status']=='never_collected'
    assert collection_status('tesla',now=now+timedelta(hours=1))['status']=='stale'


def test_failure_preserves_previous_success(storage):
    previous=(datetime.now(timezone.utc)-timedelta(minutes=5)).isoformat()
    db.put('source_entity_run',{'id':'gdelt:tesla','status':'Healthy','last_success':previous})
    with patch('server.sources.httpx.Client') as client:
        client.return_value.__enter__.return_value.get.side_effect=httpx.ConnectError('unavailable')
        result=sources.sync('tesla')
    assert result['status']=='Error'
    assert collection_status('tesla')['last_success']==previous
    assert collection_status('tesla')['status']=='error'


def test_worker_does_not_acknowledge_source_failure(storage):
    with patch('server.worker._checkpoint'), patch('server.worker.sources.sync',return_value={'status':'Error'}):
        with pytest.raises(RuntimeError,match='SQS must retry'):
            worker.execute({'version':1,'job_id':'failed-source','action':'sync_entity','entity_id':'tesla'},'ingestion')


def test_empty_aliases_still_match_registered_name(storage):
    row=db.get('entity','tesla')
    row['aliases']=[]
    db.put('entity',row)
    with patch('server.sources.httpx.Client') as client:
        client.return_value.__enter__.return_value.get.return_value.json.return_value={'articles':[
            {'title':'Tesla test announcement','url':'https://example.org/new-test'}
        ]}
        assert sources.sync('tesla')['inserted']==1


def test_worker_defers_failed_analysis_and_skips_completed_replay(storage):
    db.save_job({'id':'analysis-1','created_at':'2026-10-29','status':'queued'})
    message={'version':1,'job_id':'delivery-1','action':'run_investigation','investigation_id':'analysis-1'}
    def defer(job):
        db.save_job({**job,'status':'deferred'})
    with patch('server.worker._checkpoint'), patch('server.worker.research.run',side_effect=defer):
        with pytest.raises(RuntimeError,match='SQS must retry'):
            worker.execute(message,'analysis')
    db.save_job({'id':'analysis-1','created_at':'2026-10-29','status':'completed'})
    with patch('server.worker._checkpoint'), patch('server.worker.research.run') as research:
        result=worker.execute(message,'analysis')
        assert result['status']=='already_completed'
        research.assert_not_called()


def test_source_cooldown_is_shared_across_companies(storage):
    with patch('server.sources._collect',return_value={'status':'Healthy'}) as collect:
        assert sources.sync('tesla')['status']=='Healthy'
        assert sources.sync('jio')['status']=='Deferred'
        assert collect.call_count==1


def test_one_article_can_link_multiple_named_companies_without_duplicate_events(storage):
    with patch('server.sources.httpx.Client') as client:
        client.return_value.__enter__.return_value.get.return_value.json.return_value={'articles':[
            {'title':'Tesla and Jio Platforms illustrative test story','url':'https://example.org/multi-company'}
        ]}
        assert sources._collect('tesla')['inserted']==1
        assert sources._collect('jio')['inserted']==0
    matched=[row for row in db.records('event') if row.get('source_url')=='https://example.org/multi-company']
    assert len(matched)==1 and set(matched[0]['entities'])=={'tesla','jio'}
