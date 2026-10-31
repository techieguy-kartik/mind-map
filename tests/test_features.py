from datetime import date,datetime,timedelta,timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from server.app import app
from server import db,primary_sources


@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('ATLAS_DB',str(tmp_path/'features.sqlite3'))
    monkeypatch.setenv('ATLAS_HOST','127.0.0.1')
    monkeypatch.setenv('SEC_USER_AGENT','Atlas tests research@example.org')
    for key in ('ATLAS_RUNTIME_SECRET_ID','ATLAS_ACCESS_TOKEN','ATLAS_ANALYSIS_QUEUE_URL','ATLAS_INGESTION_QUEUE_URL','GROQ_API_KEY'):
        monkeypatch.delenv(key,raising=False)
    with TestClient(app) as client:yield client


def observation(**overrides):
    return {'metric':'valuation','amount':'500000000','currency':'USD','as_of':date.today().isoformat(),
            'source_url':'https://example.org/test-disclosure','publisher':'Test-only fixture','reviewed':True,**overrides}


def test_threshold_is_strict_and_currency_is_not_silently_converted(client):
    result=client.post('/api/entities/jio/financials',json=observation())
    assert result.status_code==201 and result.json()['status']=='below_threshold'
    assert client.post('/api/entities/jio/financials',json=observation(currency='INR')).status_code==422
    result=client.post('/api/entities/jio/financials',json=observation(amount='50000000000',currency='INR',usd_per_unit='0.012',fx_source_url='https://example.org/fx',fx_as_of=date.today().isoformat()))
    assert result.json()['status']=='qualified'
    assert result.json()['supporting'][0]['amount_usd']=='600000000.000'


def test_quarterly_profit_cannot_qualify_and_old_valuation_is_stale(client):
    end=date.today()
    assert client.post('/api/entities/jio/financials',json=observation(metric='net_profit',period_start=(end-timedelta(days=90)).isoformat())).status_code==422
    result=client.post('/api/entities/jio/financials',json=observation(amount='900000000',as_of=(end-timedelta(days=150)).isoformat()))
    assert result.json()['status']=='stale'


def test_sec_extracts_annual_profit_and_keeps_filing_metadata_separate(client):
    submissions={'cik':1318605,'name':'TESLA INC','filings':{'recent':{
        'accessionNumber':['0001318605-26-000001'],'form':['10-K'],'filingDate':['2026-01-31']}}}
    facts={'cik':1318605,'facts':{'us-gaap':{'NetIncomeLoss':{'units':{'USD':[
        {'val':700000000,'start':'2025-01-01','end':'2025-12-31','form':'10-K','fp':'FY','filed':'2026-01-31'},
        {'val':9999999999,'start':'2026-07-01','end':'2026-09-30','form':'10-Q','fp':'Q3','filed':'2026-10-15'}
    ]}}}}}
    with patch('server.primary_sources.httpx.Client') as mocked:
        response=mocked.return_value.__enter__.return_value.get.return_value
        response.json.side_effect=[{'0':{'cik_str':1318605,'title':'TESLA INC'}},submissions,facts]
        result=primary_sources.sync('tesla','sec')
    assert result['status']=='Healthy' and result['inserted']==1
    financials=db.records('financial')
    assert len(financials)==1 and financials[0]['amount_usd']=='700000000'
    assert financials[0]['source_class']=='primary_regulatory'
    assert primary_sources.sync('tesla','sec')['status']=='Deferred'


def test_nse_shared_feed_cache_and_entity_matching(client):
    xml=b'<rss><channel><item><title>Reliance Industries disclosure</title><description>Annual results published</description><link>https://nsearchives.nseindia.com/test.pdf</link><pubDate>Wed, 28 Oct 2026 10:00:00 GMT</pubDate></item></channel></rss>'
    with patch('server.primary_sources.httpx.Client') as mocked:
        response=mocked.return_value.__enter__.return_value.get.return_value
        response.content=xml
        assert primary_sources.sync('reliance','india-filings')['inserted']==1
        assert primary_sources.sync('jio','india-filings')['inserted']==0
        assert mocked.return_value.__enter__.return_value.get.call_count==1
    assert db.records('event')[-1]['source_id']=='india-filings'


def test_rules_alert_deduplication_and_correction_propagation(client):
    assert client.put('/api/watchlist/jio/rule',json={'sources':['unknown']}).status_code==422
    assert client.put('/api/watchlist/jio/rule',json={'sources':['gdelt'],'min_materiality':3}).status_code==200
    now=datetime.now(timezone.utc).isoformat()
    event={'id':'deal','entity_id':'jio','entities':['jio'],'title':'Jio acquisition announcement','summary':'Test-only fixture',
           'source_id':'gdelt','demo':False,'status':'Reported','published_at':now,'observed_at':now}
    db.put('event',event)
    db.put('event',event)
    alerts=client.get('/api/alerts').json()
    assert len(alerts)==1 and alerts[0]['reasons']==['acquisition']
    db.put('hypothesis',{'id':'linked','supporting':['deal'],'status':'Draft'})
    result=client.post('/api/events/deal/review',json={'status':'Retracted','statement':'Test-only correction: this source withdrew the statement.','source_url':'https://example.org/correction','reviewed':True})
    assert result.status_code==200 and result.json()['affected_hypotheses']==['linked']
    assert db.get('hypothesis','linked')['status']=='Needs review'
    assert client.get('/api/alerts').json()[0]['status']=='withdrawn'


def test_sourced_person_and_dossier(client):
    result=client.post('/api/entities',json={'name':'Test Research Person','country':'India','type':'person','sector':'Research',
        'description':'Test-only professional profile fixture.','source_url':'https://example.org/profile'})
    assert result.status_code==201
    assert client.get('/api/entities/'+result.json()['id']+'/dossier').status_code==200


def test_history_preserves_the_record_before_retraction(client):
    original={'id':'historical','entity_id':'jio','entities':['jio'],'title':'Original test disclosure','summary':'Test only',
              'source_id':'gdelt','demo':False,'status':'Reported','published_at':'2026-01-01T00:00:00+00:00','observed_at':'2026-01-02T00:00:00+00:00'}
    db.put('event',original)
    client.post('/api/events/historical/review',json={'status':'Retracted','statement':'This fixture was retracted by its test source.','source_url':'https://example.org/correction','reviewed':True})
    prior=[row for row in db.records_at('event','2026-02-01T00:00:00+00:00') if row['id']=='historical']
    assert prior[0]['status']=='Reported'
    assert db.get('event','historical')['status']=='Retracted'


def test_financial_evidence_reaches_research_and_retraction_removes_qualification(client):
    from server import research
    client.post('/api/entities/jio/financials',json=observation(amount='800000000'))
    event=next(row for row in db.records('event') if row.get('financial_id'))
    research.run({'id':'financial-research','entity_id':'jio','question':'What valuation evidence exists?',
        'demo':False,'created_at':datetime.now(timezone.utc).isoformat()})
    assert event['id'] in db.get_job('financial-research')['citations']
    assert client.post('/api/events/'+event['id']+'/review',json={'status':'Retracted',
        'statement':'Test fixture: the recorded amount was withdrawn by the source.',
        'source_url':'https://example.org/withdrawal','reviewed':True}).status_code==200
    assert client.get('/api/entities/jio/dossier').json()['financials']['status']=='unverified'
    assert next(row for row in client.get('/api/workspace').json()['entities'] if row['id']=='jio')['qualification']=='Not yet verified'


def test_read_does_not_hide_alert_withdrawal(client):
    db.put('alert',{'id':'withdrawn','event_id':'some-event','entity_id':'jio','created_at':'2026-01-01','status':'withdrawn'})
    assert client.post('/api/alerts/withdrawn/read').json()['status']=='withdrawn'


def test_nse_ownership_poll_does_not_mark_announcements_fresh(client):
    from server.freshness import collection_status
    with patch('server.primary_sources.httpx.Client') as mocked:
        mocked.return_value.__enter__.return_value.get.return_value.content=b'<rss><channel/></rss>'
        assert primary_sources.sync('reliance','india-filings',feed='ownership')['status']=='Healthy'
    assert collection_status('reliance',source_id='india-filings')['status']=='never_collected'
    assert db.get('source_entity_run','india-filings:reliance:ownership')['status']=='Healthy'


def test_financial_disclaimer_does_not_create_an_investment_alert(client):
    from server.financials import FinancialObservation,record
    record('jio',FinancialObservation(**observation(amount='800000000')),source_class='primary_regulatory')
    assert client.get('/api/alerts').json()==[]
