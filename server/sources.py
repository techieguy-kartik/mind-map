"""Fixed-host, metadata-only discovery. Never fetch arbitrary user supplied URLs."""
import hashlib
import re
import time
import os
from datetime import datetime, timezone
from urllib.parse import urlparse
import httpx
from . import db, evidence as evidence_policy

CATALOG=[
    dict(id='gdelt',name='GDELT discovery',type='Global news metadata',access='Free public API',status='Ready',description='Fetches up to 75 news leads for a selected company. Titles and publisher links only; no article scraping.',url='https://gdeltproject.org/data.html',can_sync=True),
    dict(id='india-filings',name='India company disclosures',type='Primary evidence',access='Public websites',status='Ready',description='Official NSE announcement, financial-results, board, annual-report and ownership RSS adapters. Public feed availability and company matching are reported per run.',url='https://www.nseindia.com/static/rss-feed',can_sync=True),
    dict(id='sec',name='SEC EDGAR',type='Regulatory filings',access='Free official API',status='Ready',description='Official SEC submissions and annual US-GAAP net-income facts. Uses a reviewed CIK or unique SEC-directory match; identifying SEC_USER_AGENT contact is required.',url='https://www.sec.gov/search-filings/edgar-application-programming-interfaces',can_sync=True),
    dict(id='open-data',name='Patents · grants · trials · procurement',type='Primary and public records',access='Free official APIs',status='Planned',description='USPTO/EPO, NIH, ClinicalTrials.gov, USASpending and country procurement connectors are prioritized before social scraping.',url='https://www.usaspending.gov/data',can_sync=False),
    dict(id='open-social',name='Mastodon · Bluesky · permitted RSS',type='Public statements',access='Free public APIs and feeds',status='Planned',description='Open-network and publisher-feed adapters can collect attributable public statements with per-source rate and retention rules.',url='https://docs.joinmastodon.org/client/public/',can_sync=False),
    dict(id='x',name='X',type='Public statements',access='Metered official API',status='Optional',description='X currently charges per resource read. Add only with an API budget, credentials and a monitored-account allow-list.',url='https://developer.x.com/',can_sync=False),
    dict(id='linkedin',name='LinkedIn',type='Professional statements',access='Limited and approval-based APIs',status='Restricted',description='Open permissions support member sign-in and member-authorized posting; they do not provide unrestricted company-feed monitoring.',url='https://learn.microsoft.com/en-us/linkedin/shared/authentication/getting-access',can_sync=False),
    dict(id='social-oss',name='Open-source feed adapters',type='Discovery only',access='Self-hosted; route-specific',status='Evaluate',description='RSSHub and similar adapters may provide discovery feeds where collection is permitted. Availability and platform terms must be tested per route.',url='https://github.com/DIYgod/RSSHub',can_sync=False),
]


def safe_url(value):
    try:
        parsed=urlparse(value)
        return value if parsed.scheme in ('http','https') and parsed.hostname and not parsed.username else None
    except (ValueError,TypeError):
        return None


def sync(entity_id):
    if not db.get('entity',entity_id):
        raise ValueError('Select a company')
    now=time.time()
    interval=max(1,int(os.getenv('ATLAS_SOURCE_MIN_INTERVAL_SECONDS','60')))
    with db.connect() as connection:
        connection.execute('BEGIN IMMEDIATE')
        row=connection.execute("SELECT next_allowed FROM source_leases WHERE source='gdelt'").fetchone()
        if row and row['next_allowed']>now:
            return {'id':'gdelt','status':'Deferred','entity_id':entity_id,'retry_after_seconds':max(1,int(row['next_allowed']-now)),
                    'error':'Shared source request budget is cooling down. Stored evidence remains available.'}
        connection.execute("INSERT INTO source_leases VALUES('gdelt',?) ON CONFLICT(source) DO UPDATE SET next_allowed=excluded.next_allowed",(now+max(30,interval),))
    return _collect(entity_id)


def _collect(entity_id):
    entity=db.get('entity',entity_id)
    if not entity or entity['type']!='company':
        raise ValueError('Select a company')
    started=datetime.now(timezone.utc).isoformat()
    previous=db.get('source_entity_run',f'gdelt:{entity_id}') or {}
    state=dict(id='gdelt',status='Syncing',last_attempt=started,entity_id=entity_id,last_success=previous.get('last_success'))
    db.put('source_run',state)
    # Entity names come from the controlled registry, never arbitrary URLs or queries.
    query='"'+entity['name'].replace('"','')+'"'
    try:
        with httpx.Client(timeout=25,follow_redirects=False) as client:
            response=client.get('https://api.gdeltproject.org/api/v2/doc/doc',params={'query':query,'mode':'ArtList','format':'json','maxrecords':75,'timespan':'24h','sort':'DateDesc'},headers={'User-Agent':'AtlasIntelligence/0.1 (metadata research)'})
            response.raise_for_status()
            articles=response.json().get('articles',[])
        inserted=0
        for article in articles:
            url=safe_url(article.get('url'))
            title=article.get('title')
            if not url or not isinstance(title,str) or not title.strip():
                continue
            aliases=list(dict.fromkeys([entity['name'],*(entity.get('aliases') or [])]))
            # Require a registry alias in the headline; query hits alone are too weak.
            if not any(re.search(r'(?<!\w)'+re.escape(a)+r'(?!\w)',title,re.I) for a in aliases):
                continue
            id='news-'+hashlib.sha256(url.encode()).hexdigest()[:20]
            existing=db.get('event',id)
            if existing:
                if entity_id not in existing.get('entities',[]):
                    existing['entities']=sorted(set(existing.get('entities',[])+[entity_id]))
                    db.put('event',existing)
                continue
            raw_date=article.get('seendate','')
            try:
                published=datetime.strptime(raw_date,'%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc).isoformat()
            except (ValueError,TypeError):
                published=started
            publisher=urlparse(url).hostname
            provenance=evidence_policy.envelope('reporting_lead',retrieved_at=started)
            record=dict(id=id,entity_id=entity_id,title=title[:500],event_type='News lead',priority='Unranked',summary='Discovered headline only. Open the publisher source to verify context. This record has not been corroborated or interpreted as a confirmed company action.',entities=[entity_id],published_at=published,observed_at=started,source_id='gdelt',source_name=publisher,source_url=url,status='Reported',demo=False,evidence=[dict(id=id+'-headline',text=title[:500],url=url,publisher=publisher,kind='headline',**provenance)])
            db.put('event',record)
            inserted+=1
        state.update(status='Healthy',last_success=started,inserted=inserted,error=None)
    except (httpx.HTTPError,ValueError,TypeError):
        state.update(status='Error',error='Source unavailable, rate limited, or returned an invalid response. No coverage is implied. Retry later.')
    db.put('source_run',state)
    db.put('source_entity_run',{**state,'id':f'gdelt:{entity_id}'})
    return state
