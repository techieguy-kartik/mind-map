"""Offline, versioned company catalog migration; never fetch on startup."""
import hashlib
import json
from pathlib import Path

CATALOG_PATH=Path(__file__).parent/'data/company_registry.json'


def migrate(connection):
    if not CATALOG_PATH.exists():
        return
    raw=CATALOG_PATH.read_bytes()
    version=hashlib.sha256(raw).hexdigest()
    prior=connection.execute("SELECT value FROM meta WHERE key='registry_version'").fetchone()
    if prior and prior['value']==version:
        return
    catalog=json.loads(raw)
    existing=[json.loads(row['data']) for row in connection.execute("SELECT data FROM records WHERE kind='entity'")]
    by_qid={item['wikidata_id']:item for item in existing if item.get('wikidata_id')}
    names={}
    for item in existing:
        if item.get('type')!='company':
            continue
        for name in {value.casefold() for value in [item['name'],*item.get('aliases',[])]}:
            names.setdefault(name,[]).append(item)
    for row in catalog['companies']:
        if row.get('type')!='company' or not row.get('wikidata_id') or not row.get('name'):
            raise ValueError('Invalid catalog company')
        current=by_qid.get(row['wikidata_id'])
        matches=names.get(row['name'].casefold(),[])
        if current is None and len(matches)==1 and not matches[0].get('wikidata_id'):
            current=matches[0]
        if current:
            merged={**row,**current}
            merged['sectors']=sorted(set(row.get('sectors',[])+current.get('sectors',[current['sector']])))
            merged['wikidata_id']=row['wikidata_id']
            merged['source_url']=current.get('source_url') or row['source_url']
        else:
            merged=row
        connection.execute('INSERT INTO records VALUES(?,?,?) ON CONFLICT(kind,id) DO UPDATE SET data=excluded.data',('entity',merged['id'],json.dumps(merged)))
        by_qid[row['wikidata_id']]=merged
    connection.execute("INSERT INTO meta VALUES('registry_version',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(version,))


def coverage(entities):
    counts={}
    target=100
    generated=None
    if CATALOG_PATH.exists():
        catalog=json.loads(CATALOG_PATH.read_text())
        counts={sector:0 for sector in catalog['sector_coverage']}
        generated=catalog['generated_at']
        target=catalog['target_per_sector']
    configured=set(counts)
    for row in entities:
        if row.get('type')=='company':
            for sector in row.get('sectors',[row['sector']]):
                if configured and sector not in configured:
                    continue
                counts[sector]=counts.get(sector,0)+1
    return {'generated_at':generated,'target_per_sector':target,'sectors':[
        {'sector':sector,'candidates':count,'gap':max(0,target-count)} for sector,count in sorted(counts.items())
    ],'qualification':'Candidate counts do not establish the USD 500m financial threshold.'}
