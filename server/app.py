import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from . import cloud, db, evidence as evidence_policy, research, sources

load_dotenv()
pool=ThreadPoolExecutor(max_workers=2)
sync_lock=threading.Lock()
login_attempts={}


@asynccontextmanager
async def lifespan(app):
    token=os.getenv('ATLAS_ACCESS_TOKEN','')
    host=os.getenv('ATLAS_HOST','127.0.0.1')
    if (host not in ('127.0.0.1','localhost','::1') and len(token)<24) or (token and len(token)<24):
        raise RuntimeError('Use an access token of at least 24 characters before exposing the service.')
    db.initialize()
    yield


app=FastAPI(title='Atlas Intelligence',version='0.2.0',lifespan=lifespan)


def session_valid(value,token):
    try:
        expires,signature=value.split('.',1)
        expected=hmac.new(token.encode(),expires.encode(),hashlib.sha256).hexdigest()
        return int(expires)>time.time() and hmac.compare_digest(expected,signature)
    except (ValueError,AttributeError):
        return False


@app.middleware('http')
async def guard(request:Request,call_next):
    if request.method not in ('GET','HEAD','OPTIONS'):
        origin=request.headers.get('origin')
        if origin and origin.rstrip('/') != str(request.base_url).rstrip('/'):
            # The Vite dev proxy forwards browser origin from 5173.
            local_dev=(request.url.hostname in ('127.0.0.1','localhost') and origin in ('http://127.0.0.1:5173','http://localhost:5173'))
            if not local_dev:
                return JSONResponse({'detail':'Origin not allowed'},status_code=403)
    token=os.getenv('ATLAS_ACCESS_TOKEN','')
    protected=request.url.path.startswith('/api/') and request.url.path not in ('/api/health','/api/session')
    if protected and token and not session_valid(request.cookies.get('atlas_session'),token):
        return JSONResponse({'detail':'Sign in to your private workspace'},status_code=401)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Referrer-Policy']='no-referrer'
    if request.url.path.startswith('/api/'):
        response.headers['Cache-Control']='no-store'
    return response


class Login(BaseModel):
    token:str=Field(max_length=512)


@app.post('/api/session')
def login(body:Login,request:Request,response:Response):
    ip=request.client.host if request.client else 'unknown'
    now=time.time()
    attempts=[t for t in login_attempts.get(ip,[]) if now-t<60]
    if len(attempts)>=5:
        raise HTTPException(429,'Too many attempts. Wait one minute.')
    login_attempts[ip]=attempts+[now]
    token=os.getenv('ATLAS_ACCESS_TOKEN','')
    if not token or not secrets.compare_digest(body.token,token):
        raise HTTPException(401,'Invalid workspace access token')
    expires=str(int(now)+43200)
    signature=hmac.new(token.encode(),expires.encode(),hashlib.sha256).hexdigest()
    response.set_cookie('atlas_session',expires+'.'+signature,httponly=True,samesite='strict',secure=os.getenv('ATLAS_SECURE_COOKIE')=='true',max_age=43200)
    return {'ok':True}


@app.get('/api/health')
def health():
    return {'status':'ok','version':'0.2.0','authentication_required':bool(os.getenv('ATLAS_ACCESS_TOKEN')),'durable_ingestion':cloud.enabled('ingestion'),'durable_analysis':cloud.enabled('analysis')}


@app.get('/api/workspace')
def workspace():
    with db.connect() as connection:
        watched=[r['entity_id'] for r in connection.execute('SELECT entity_id FROM watchlist')]
        row=connection.execute('SELECT investigations FROM usage WHERE day=?',(datetime.now(timezone.utc).date().isoformat(),)).fetchone()
    runs={r['id']:r for r in db.records('source_run')}
    return {'entities':db.records('entity'),'events':db.records('event'),'edges':db.records('edge'),'hypotheses':db.records('hypothesis'),'watchlist':watched,'investigations':db.jobs(),'sources':[{**s,**runs.get(s['id'],{})} for s in sources.CATALOG],'settings':{'groq_configured':bool(os.getenv('GROQ_API_KEY')),'model':os.getenv('GROQ_MODEL','openai/gpt-oss-20b'),'daily_limit':int(os.getenv('ATLAS_DAILY_INVESTIGATIONS','10')),'used_today':row['investigations'] if row else 0,'storage':'SQLite pilot with durable AWS control plane' if cloud.enabled('analysis') else 'SQLite pilot','paid_sources':False,'durable_ingestion':cloud.enabled('ingestion'),'durable_analysis':cloud.enabled('analysis')}}


@app.get('/api/entities/{entity_id}')
def entity(entity_id:str):
    value=db.get('entity',entity_id)
    if not value: raise HTTPException(404,'Entity not found')
    return value


class Watch(BaseModel):
    watched:bool


@app.put('/api/watchlist/{entity_id}')
def watch(entity_id:str,body:Watch):
    entity(entity_id)
    with db.connect() as connection:
        if body.watched:
            connection.execute('INSERT OR IGNORE INTO watchlist VALUES(?)',(entity_id,))
        else:
            connection.execute('DELETE FROM watchlist WHERE entity_id=?',(entity_id,))
    return {'ok':True}


class Investigation(BaseModel):
    entity_id:str
    question:str=Field(min_length=8,max_length=1500)
    demo:bool=False


@app.post('/api/investigations',status_code=202)
def investigate(body:Investigation):
    entity(body.entity_id)
    now=datetime.now(timezone.utc)
    with db.connect() as connection:
        connection.execute('BEGIN IMMEDIATE')
        day=now.date().isoformat()
        connection.execute('INSERT OR IGNORE INTO usage(day) VALUES(?)',(day,))
        count=connection.execute('SELECT investigations FROM usage WHERE day=?',(day,)).fetchone()[0]
        if count>=int(os.getenv('ATLAS_DAILY_INVESTIGATIONS','10')):
            raise HTTPException(429,'Daily investigation cap reached. It resets at 00:00 UTC.')
        connection.execute('UPDATE usage SET investigations=investigations+1 WHERE day=?',(day,))
        job=dict(id=str(uuid4()),created_at=now.isoformat(),entity_id=body.entity_id,question=body.question,demo=body.demo,status='queued',evidence=[])
        connection.execute('INSERT INTO investigations VALUES(?,?,?)',(job['id'],job['created_at'],json.dumps(job)))
    if cloud.enabled('analysis'):
        try:
            cloud.dispatch('analysis','run_investigation',job_id=job['id'],investigation_id=job['id'])
        except Exception:
            job.update(status='failed',error='Durable analysis dispatch failed; no work was silently dropped.')
            db.save_job(job)
            raise HTTPException(503,'Durable analysis dispatch failed')
    else:
        pool.submit(research.run,job.copy())
    return job


@app.get('/api/investigations/{id}')
def investigation(id:str):
    with db.connect() as connection:
        row=connection.execute('SELECT data FROM investigations WHERE id=?',(id,)).fetchone()
    if not row: raise HTTPException(404,'Investigation not found')
    return json.loads(row['data'])


class Sync(BaseModel):
    entity_id:str


class ReviewedEvidence(BaseModel):
    source_entity:str
    target_entity:str
    relation:Literal['subsidiary_of','invests_in','partners_with','serves_as','announced','develops','owns_stake_in','supplies']
    statement:str=Field(min_length=20,max_length=3000)
    source_url:str=Field(max_length=2000)
    publisher:str=Field(min_length=2,max_length=150)
    effective_date:str=Field(pattern=r'^\d{4}-\d{2}-\d{2}$')
    reviewed:Literal[True]


@app.post('/api/evidence',status_code=201)
def add_evidence(body:ReviewedEvidence):
    a,b=entity(body.source_entity),entity(body.target_entity)
    if a['demo'] or b['demo'] or a['id']==b['id']:
        raise HTTPException(422,'Choose two different real registry entities')
    url=sources.safe_url(body.source_url)
    if not url: raise HTTPException(422,'Provide an http or https source URL')
    try:
        effective=datetime.strptime(body.effective_date,'%Y-%m-%d').replace(tzinfo=timezone.utc)
    except ValueError:
        raise HTTPException(422,'Invalid effective date')
    observed=datetime.now(timezone.utc).isoformat()
    digest=hashlib.sha256(json.dumps(body.model_dump(),sort_keys=True).encode()).hexdigest()[:20]
    id='review-'+digest
    evidence=[dict(id=id+'-evidence',text=body.statement,url=url,publisher=body.publisher,kind='user-reviewed',**evidence_policy.envelope('user_reviewed',retrieved_at=observed))]
    event=dict(id=id,entity_id=a['id'],title=f"{a['name']} → {body.relation.replace('_',' ')} → {b['name']}",event_type='Reviewed relationship',priority='Unranked',summary=body.statement,entities=[a['id'],b['id']],published_at=effective.isoformat(),observed_at=observed,source_id='user-review',source_name=body.publisher,source_url=url,status='User-reviewed',demo=False,evidence=evidence)
    edge=dict(id=id+'-edge',source=a['id'],target=b['id'],relation=body.relation,event_id=id,evidence=evidence,observed_at=observed,effective_from=effective.isoformat(),status='User-reviewed',demo=False)
    with db.connect() as connection:
        for kind,row in [('event',event),('edge',edge)]:
            connection.execute('INSERT OR IGNORE INTO records VALUES(?,?,?)',(kind,row['id'],json.dumps(row)))
    return event


@app.post('/api/sources/gdelt/sync')
def sync(body:Sync):
    entity(body.entity_id)
    if not sync_lock.acquire(blocking=False): raise HTTPException(409,'Another source sync is running')
    try:
        previous=db.get('source_run','gdelt')
        if previous and (datetime.now(timezone.utc)-datetime.fromisoformat(previous['last_attempt'])).total_seconds()<60:
            raise HTTPException(429,'Wait one minute between source requests')
        if cloud.enabled('ingestion'):
            try:
                job_id=cloud.dispatch('ingestion','sync_entity',entity_id=body.entity_id)
            except Exception:
                raise HTTPException(503,'Durable ingestion dispatch failed')
            state=dict(id='gdelt',status='Queued',last_attempt=datetime.now(timezone.utc).isoformat(),entity_id=body.entity_id,job_id=job_id)
            db.put('source_run',state)
            return state
        return sources.sync(body.entity_id)
    finally:
        sync_lock.release()


dist=Path(__file__).resolve().parent.parent/'dist'
if dist.exists():
    app.mount('/assets',StaticFiles(directory=dist/'assets'),name='assets')
    @app.get('/favicon.svg')
    def favicon(): return FileResponse(dist/'favicon.svg')
    @app.get('/')
    def index(): return FileResponse(dist/'index.html')
