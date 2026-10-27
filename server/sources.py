"""Fixed-host, metadata-only discovery. Never fetch arbitrary user supplied URLs."""
import hashlib
import re
from datetime import datetime, timezone
from urllib.parse import urlparse
import httpx
from . import db

CATALOG=[
    dict(id='gdelt',name='GDELT discovery',type='Global news metadata',access='Free public API',status='Ready',description='Fetches up to 75 news leads for a selected company. Titles and publisher links only; no article scraping.',url='https://gdeltproject.org/data.html',can_sync=True),
    dict(id='india-filings',name='India company disclosures',type='Primary evidence',access='Public websites',status='Planned',description='NSE/BSE and issuer disclosures. Automated connectors require access validation; not connected in this release.',url='https://www.sebi.gov.in/curation/corporate_filings.html',can_sync=False),
    dict(id='sec',name='SEC EDGAR',type='Regulatory filings',access='Free official API',status='Planned',description='CIK mapping, contact-identifying user agent and extraction are planned. No filings have been synchronized.',url='https://www.sec.gov/search-filings/edgar-application-programming-interfaces',can_sync=False),
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
    entity=db.get('entity',entity_id)
    if not entity or entity['type']!='company':
        raise ValueError('Select a company')
    started=datetime.now(timezone.utc).isoformat()
    state=dict(id='gdelt',status='Syncing',last_attempt=started,entity_id=entity_id)
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
            aliases=entity['aliases']
            # Require a registry alias in the headline; query hits alone are too weak.
            if not any(re.search(r'(?<!\w)'+re.escape(a)+r'(?!\w)',title,re.I) for a in aliases):
                continue
            id='news-'+hashlib.sha256(url.encode()).hexdigest()[:20]
            if db.get('event',id):
                continue
            raw_date=article.get('seendate','')
            try:
                published=datetime.strptime(raw_date,'%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc).isoformat()
            except (ValueError,TypeError):
                published=started
            publisher=urlparse(url).hostname
            record=dict(id=id,entity_id=entity_id,title=title[:500],event_type='News lead',priority='Unranked',summary='Discovered headline only. Open the publisher source to verify context. This record has not been corroborated or interpreted as a confirmed company action.',entities=[entity_id],published_at=published,observed_at=started,source_id='gdelt',source_name=publisher,source_url=url,status='Reported',demo=False,evidence=[dict(id=id+'-headline',text=title[:500],url=url,publisher=publisher,kind='headline')])
            db.put('event',record)
            inserted+=1
        state.update(status='Healthy',last_success=started,inserted=inserted,error=None)
    except (httpx.HTTPError,ValueError,TypeError):
        state.update(status='Error',error='Source unavailable, rate limited, or returned an invalid response. No coverage is implied. Retry later.')
    db.put('source_run',state)
    return state
