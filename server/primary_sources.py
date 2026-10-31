"""Fixed-host SEC JSON and official NSE RSS adapters."""
import hashlib
import json
import os
import re
import time
from datetime import datetime,timezone,date
from decimal import Decimal
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

import httpx

from . import db,evidence
from .financials import FinancialObservation,record
from .sources import safe_url

NSE_FEEDS={
    'announcements':'https://nsearchives.nseindia.com/content/RSS/Online_announcements.xml',
    'results':'https://nsearchives.nseindia.com/content/RSS/Financial_Results.xml',
    'board':'https://nsearchives.nseindia.com/content/RSS/Board_Meetings.xml',
    'ownership':'https://nsearchives.nseindia.com/content/RSS/Shareholding_Pattern.xml',
    'annual':'https://nsearchives.nseindia.com/content/RSS/Annual_Reports.xml',
}


class Cooldown(Exception):
    def __init__(self,seconds):
        self.seconds=seconds


def _lease(source,interval=60):
    now=time.time()
    with db.connect() as connection:
        connection.execute('BEGIN IMMEDIATE')
        row=connection.execute('SELECT next_allowed FROM source_leases WHERE source=?',(source,)).fetchone()
        if row and row['next_allowed']>now:raise Cooldown(max(1,int(row['next_allowed']-now)))
        connection.execute('INSERT INTO source_leases VALUES(?,?) ON CONFLICT(source) DO UPDATE SET next_allowed=excluded.next_allowed',(source,now+interval))


def _normalize(name):
    return ' '.join(x for x in re.findall(r'[a-z0-9]+',name.casefold()) if x not in {'inc','corp','corporation','limited','ltd','plc','company'})


def _store_event(entity,source_id,title,summary,url,published,source_class,kind):
    if not safe_url(url):
        return 0
    id='primary-'+hashlib.sha256((source_id+entity['id']+url+title).encode()).hexdigest()[:24]
    if db.get('event',id):
        return 0
    observed=datetime.now(timezone.utc).isoformat()
    ev={'id':id+'-source','text':summary,'url':url,'publisher':source_id.upper(),'kind':kind,**evidence.envelope(source_class)}
    db.put('event',{'id':id,'entity_id':entity['id'],'entities':[entity['id']],'title':title,'summary':summary,
        'published_at':published,'observed_at':observed,'event_type':kind,'priority':'Unranked','source_id':source_id,
        'source_name':source_id.upper(),'source_url':url,'status':'Official record metadata','demo':False,'evidence':[ev]})
    return 1


def _json(client,url):
    response=client.get(url)
    response.raise_for_status()
    return response.json()


def _resolve_cik(client,entity):
    if entity.get('sec_cik') and entity.get('sec_mapping_reviewed'):
        return str(entity['sec_cik']).zfill(10)
    cache=db.get('connector_cache','sec-directory')
    if not cache or time.time()-cache['fetched']>86400:
        directory=_json(client,'https://www.sec.gov/files/company_tickers.json')
        cache={'id':'sec-directory','fetched':time.time(),'items':list(directory.values())}
        db.put('connector_cache',cache)
    names={_normalize(x) for x in [entity['name'],*entity.get('aliases',[])] if len(_normalize(x))>2}
    matches={str(row['cik_str']).zfill(10) for row in cache['items'] if _normalize(row['title']) in names}
    if len(matches)!=1:
        raise ValueError('No unique SEC directory name match. Review the CIK mapping in the entity dossier.')
    cik=matches.pop()
    db.put('identifier',{'id':'sec:'+entity['id'],'entity_id':entity['id'],'cik':cik,'method':'SEC directory exact normalized-name match','source_url':'https://www.sec.gov/files/company_tickers.json'})
    return cik


def _sec(client,entity):
    _lease('sec')
    cik=_resolve_cik(client,entity)
    time.sleep(.2)
    filings=_json(client,f'https://data.sec.gov/submissions/CIK{cik}.json')
    if str(filings.get('cik','')).zfill(10)!=cik:
        raise ValueError('SEC issuer response does not match requested CIK')
    recent=filings.get('filings',{}).get('recent',{})
    inserted=0
    for index,accession in enumerate(recent.get('accessionNumber',[])[:60]):
        if not re.fullmatch(r'\d{10}-\d{2}-\d{6}',accession):
            continue
        form=recent.get('form',[])[index]
        if form not in {'10-K','10-K/A','10-Q','8-K','20-F','6-K','SC 13D','SC 13G','4'}:
            continue
        published=recent['filingDate'][index]+'T00:00:00+00:00'
        url=f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace("-","")}/{accession}-index.html'
        summary=f"SEC records form {form} filed by {filings.get('name',entity['name'])} on {recent['filingDate'][index]}. Accession {accession}. Filing metadata alone does not establish a transaction or its completion."
        inserted+=_store_event(entity,'sec',f"{entity['name']}: SEC {form} filing",summary,url,published,'primary_regulatory','Regulatory filing')
    time.sleep(.2)
    facts=_json(client,f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json')
    if str(facts.get('cik','')).zfill(10)!=cik:
        raise ValueError('SEC financial response does not match issuer')
    annual=[]
    for item in facts.get('facts',{}).get('us-gaap',{}).get('NetIncomeLoss',{}).get('units',{}).get('USD',[]):
        try:
            duration=(date.fromisoformat(item['end'])-date.fromisoformat(item['start'])).days
            if item.get('form') in {'10-K','10-K/A','20-F'} and 330<=duration<=400 and item.get('fp')=='FY':
                annual.append(item)
        except (ValueError,KeyError):
            continue
    if annual:
        fact=max(annual,key=lambda item:(item['end'],item.get('filed','')))
        observation=FinancialObservation(metric='net_profit',amount=Decimal(str(fact['val'])),currency='USD',
            as_of=fact['end'],period_start=fact['start'],source_url=f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json',publisher='SEC XBRL us-gaap:NetIncomeLoss',reviewed=True)
        record(entity['id'],observation,source_class='primary_regulatory')
    return inserted


def _nse(client,entity,feed):
    key='nse:'+feed
    cache=db.get('connector_cache',key)
    if not cache or time.time()-cache['fetched']>300:
        _lease(key)
        response=client.get(NSE_FEEDS[feed])
        response.raise_for_status()
        raw=response.content
        if len(raw)>5_000_000 or b'<!ENTITY' in raw.upper() or b'<!DOCTYPE' in raw.upper():
            raise ValueError('Unexpected or oversized XML feed')
        root=ElementTree.fromstring(raw)
        items=[{tag:item.findtext(tag,'') for tag in ('title','description','link','pubDate')} for item in root.findall('.//item')[:1000]]
        cache={'id':key,'fetched':time.time(),'items':items}
        db.put('connector_cache',cache)
    inserted=0
    aliases=[entity['name'],*entity.get('aliases',[])]
    for item in cache['items']:
        text=item['title']+' '+item['description']
        if not any(re.search(r'(?<!\w)'+re.escape(alias)+r'(?!\w)',text,re.I) for alias in aliases if len(alias)>2):
            continue
        try:
            published=parsedate_to_datetime(item['pubDate']).astimezone(timezone.utc).isoformat()
            date_note=''
        except (ValueError,TypeError):
            published=datetime.now(timezone.utc).isoformat()
            date_note=' Publication date unavailable or invalid; the displayed timestamp is the collection time.'
        summary=re.sub('<[^>]+>',' ',item['description'])[:5000]
        summary+=date_note
        inserted+=_store_event(entity,'india-filings',item['title'][:500],summary,item['link'],published,'official_public_record','Exchange disclosure: '+feed)
    return inserted


def sync(entity_id,source_id,*,feed='announcements'):
    entity=db.get('entity',entity_id)
    if not entity or entity['type']!='company':
        raise ValueError('Select a registered company')
    if source_id not in {'sec','india-filings'} or feed not in NSE_FEEDS:
        raise ValueError('Unknown connector or feed')
    started=datetime.now(timezone.utc).isoformat()
    run_id=source_id+':'+entity_id+(':'+feed if source_id=='india-filings' and feed!='announcements' else '')
    prior=db.get('source_entity_run',run_id) or {}
    state={'id':source_id,'entity_id':entity_id,'feed':feed if source_id=='india-filings' else None,
        'last_attempt':started,'last_success':prior.get('last_success'),'status':'Syncing'}
    try:
        user_agent=os.getenv('SEC_USER_AGENT','').strip()
        if source_id=='sec' and '@' not in user_agent:
            raise ValueError('Configure SEC_USER_AGENT with an identifying contact email')
        with httpx.Client(timeout=25,follow_redirects=False,headers={'User-Agent':user_agent if source_id=='sec' else 'AtlasIntelligence/0.3 (public NSE RSS reader)'}) as client:
            inserted=_sec(client,entity) if source_id=='sec' else _nse(client,entity,feed)
        state.update(status='Healthy',inserted=inserted,last_success=started,error=None)
    except Cooldown as exc:
        return {**state,'status':'Deferred','retry_after_seconds':exc.seconds,'error':'Official-source cooldown is active'}
    except (httpx.HTTPError,ValueError,KeyError,IndexError,TypeError,ElementTree.ParseError) as exc:
        state.update(status='Error',error=str(exc)[:300] if isinstance(exc,ValueError) else 'Official source unavailable or returned an invalid response')
    db.put('source_run',state)
    db.put('source_entity_run',{**state,'id':run_id})
    return state
