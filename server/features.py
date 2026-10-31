"""Primary-source, qualification, dossier, monitoring and correction APIs."""
import hashlib
from datetime import datetime,timezone
from typing import Literal

from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field,field_validator

from . import db,financials,primary_sources,sources,cloud
from .alerts import SOURCE_IDS

router=APIRouter(prefix='/api')


def registry_entities():
    rows=db.records('entity')
    financial_ids={item['entity_id'] for item in db.records('financial')}
    labels={'qualified':'Qualified by recorded evidence','below_threshold':'Below threshold','stale':'Financial evidence stale','unverified':'Not yet verified'}
    for row in rows:
        if row['id'] in financial_ids:
            row['qualification']=labels[financials.qualification(row['id'])['status']]
    return rows


def require_entity(id):
    row=db.get('entity',id)
    if not row:raise HTTPException(404,'Unknown entity')
    return row


@router.get('/entities/{id}/dossier')
def dossier(id:str):
    require_entity(id)
    return {'financials':financials.qualification(id),
        'relationships':[row for row in db.records('edge') if id in (row['source'],row['target']) and not row.get('demo')],
        'identifiers':[row for row in db.records('identifier') if row.get('entity_id')==id],
        'source_health':[row for row in db.records('source_entity_run') if row.get('entity_id')==id],
        'watch_rule':db.get('watch_rule',id),'alerts':[row for row in db.records('alert') if row['entity_id']==id]}


@router.post('/entities/{id}/financials',status_code=201)
def add_financial(id:str,body:financials.FinancialObservation):
    entity=require_entity(id)
    if entity['type']!='company' or entity.get('demo'):raise HTTPException(422,'Financial qualification requires a real company')
    financials.record(id,body)
    return financials.qualification(id)


class SECMapping(BaseModel):
    cik:str=Field(pattern=r'^\d{1,10}$')
    source_url:str
    reviewed:Literal[True]


@router.put('/entities/{id}/sec-mapping')
def map_sec(id:str,body:SECMapping):
    entity=require_entity(id)
    if not sources.safe_url(body.source_url):raise HTTPException(422,'Invalid source URL')
    entity.update(sec_cik=body.cik.zfill(10),sec_mapping_reviewed=True)
    db.put('entity',entity)
    row={'id':'sec:'+id,'entity_id':id,'cik':entity['sec_cik'],'method':'User-reviewed SEC mapping','source_url':body.source_url}
    db.put('identifier',row)
    return row


class PrimarySync(BaseModel):
    entity_id:str
    feed:Literal['announcements','results','board','ownership','annual']='announcements'


@router.post('/sources/{source_id}/primary-sync')
def sync_primary(source_id:str,body:PrimarySync):
    require_entity(body.entity_id)
    if source_id not in {'sec','india-filings'}:raise HTTPException(404,'Unknown official-source adapter')
    if cloud.enabled('ingestion'):
        job_id=cloud.dispatch('ingestion','sync_entity',entity_id=body.entity_id,source_id=source_id,feed=body.feed)
        return {'id':source_id,'status':'Queued','job_id':job_id,'entity_id':body.entity_id}
    return primary_sources.sync(body.entity_id,source_id,feed=body.feed)


class WatchRule(BaseModel):
    enabled:bool=True
    priority:int=Field(default=3,ge=1,le=5)
    interval_seconds:int=Field(default=1800,ge=300,le=86400)
    sources:list[str]=Field(default_factory=lambda:['gdelt'],min_length=1,max_length=3)
    event_types:list[str]=Field(default_factory=list,max_length=20)
    min_materiality:int=Field(default=3,ge=1,le=5)

    @field_validator('sources')
    @classmethod
    def valid_sources(cls,value):
        if not set(value)<=SOURCE_IDS:raise ValueError('Unsupported source')
        return sorted(set(value))


@router.put('/watchlist/{id}/rule')
def watch_rule(id:str,body:WatchRule):
    require_entity(id)
    row={'id':id,**body.model_dump()}
    with db.connect() as connection:
        connection.execute('INSERT OR IGNORE INTO watchlist VALUES(?)',(id,))
    db.put('watch_rule',row)
    return row


@router.get('/alerts')
def alerts():
    return sorted(db.records('alert'),key=lambda row:row['created_at'],reverse=True)[:200]


@router.post('/alerts/{id}/read')
def read_alert(id:str):
    row=db.get('alert',id)
    if not row:raise HTTPException(404,'Unknown alert')
    if row['status']=='unread':row['status']='read'
    db.put('alert',row)
    return row


class NewEntity(BaseModel):
    name:str=Field(min_length=2,max_length=160)
    country:str=Field(min_length=2,max_length=100)
    type:Literal['company','person','trust','fund','technology']
    sector:str=Field(min_length=2,max_length=100)
    source_url:str
    description:str=Field(min_length=10,max_length=2000)


@router.post('/entities',status_code=201)
def new_entity(body:NewEntity):
    if not sources.safe_url(body.source_url):raise HTTPException(422,'Invalid source URL')
    id='entity-'+hashlib.sha256((body.name.casefold()+body.country+body.type).encode()).hexdigest()[:24]
    existing=db.get('entity',id)
    if existing:return existing
    row={'id':id,**body.model_dump(),'initials':''.join(x[0] for x in body.name.split()[:2]).upper(),
         'group':'Attribution pending','aliases':[body.name],'color':'#6573bc','qualification':'Not yet verified','demo':False}
    db.put('entity',row)
    return row


class Correction(BaseModel):
    status:Literal['Disputed','Retracted','User-reviewed']
    statement:str=Field(min_length=20,max_length=3000)
    source_url:str
    reviewed:Literal[True]


@router.post('/events/{id}/review')
def correct_event(id:str,body:Correction):
    row=db.get('event',id)
    if not row:raise HTTPException(404,'Unknown event')
    if not sources.safe_url(body.source_url):raise HTTPException(422,'Invalid correction source')
    now=datetime.now(timezone.utc).isoformat()
    db.put('event_revision',{'id':id+':'+now,'event_id':id,'before':row,'review':body.model_dump(),'observed_at':now})
    row.update(status=body.status,review_note=body.statement,review_source_url=body.source_url,revised_at=now)
    db.put('event',row)
    if row.get('financial_id'):
        financial=db.get('financial',row['financial_id'])
        if financial:
            financial.update(status=body.status,revised_at=now)
            db.put('financial',financial)
    affected=[]
    for edge in db.records('edge'):
        if edge.get('event_id')==id:
            edge.update(status=body.status,revised_at=now)
            db.put('edge',edge)
    for hypothesis in db.records('hypothesis'):
        if id in hypothesis.get('supporting',[]):
            hypothesis.update(status='Needs review',review_reason=body.statement)
            db.put('hypothesis',hypothesis)
            affected.append(hypothesis['id'])
    return {'event':row,'affected_hypotheses':affected}
