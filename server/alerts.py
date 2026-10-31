"""Deterministic in-app alerts; never sends external messages."""
import hashlib
import re
from datetime import datetime,timezone

from . import db

SOURCE_IDS={'gdelt','sec','india-filings'}


def materiality(event):
    if event.get('event_type')=='Financial observation':
        return 1,[]
    text=(event.get('title','')+' '+event.get('summary','')).casefold()
    terms=['acquisition','acquires','merger','funding','bankruptcy','breach','recall','sanction','lawsuit','investment','contract','resigns']
    reasons=[term for term in terms if re.search(r'\b'+term+r'\b',text)]
    score=min(5,1+len(reasons)*2)
    return score,reasons


def evaluate(event):
    if event.get('demo'):
        return
    if event.get('status') in ('Disputed','Retracted'):
        for alert in db.records('alert'):
            if alert['event_id']==event['id']:
                alert['status']='withdrawn' if event['status']=='Retracted' else 'needs_review'
                db.put('alert',alert)
        return
    with db.connect() as connection:
        watched={row['entity_id'] for row in connection.execute('SELECT entity_id FROM watchlist')}
    score,reasons=materiality(event)
    for entity_id in watched & set(event.get('entities',[])):
        rule=db.get('watch_rule',entity_id) or {'enabled':True,'sources':sorted(SOURCE_IDS),'event_types':[],'min_materiality':3}
        if not rule['enabled'] or event.get('source_id') not in rule['sources'] or score<rule['min_materiality']:
            continue
        if rule.get('event_types') and event.get('event_type') not in rule['event_types']:
            continue
        id='alert-'+hashlib.sha256((entity_id+event['id']).encode()).hexdigest()[:24]
        prior=db.get('alert',id)
        if prior:
            continue
        db.put('alert',{'id':id,'entity_id':entity_id,'event_id':event['id'],'title':event['title'],'score':score,
                       'reasons':reasons,'status':'unread','created_at':datetime.now(timezone.utc).isoformat(),
                       'meaning':'Heuristic materiality signal; open the source before treating it as a confirmed action.'})
