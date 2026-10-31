"""Dated financial observations and conservative USD threshold qualification."""
from datetime import date,datetime,timezone
from decimal import Decimal
import hashlib
import json

from pydantic import BaseModel,Field,model_validator
from typing import Literal

from . import db,evidence
from .sources import safe_url


class FinancialObservation(BaseModel):
    metric:Literal['valuation','net_profit']
    amount:Decimal=Field(allow_inf_nan=False)
    currency:str=Field(pattern=r'^[A-Z]{3}$')
    as_of:date
    period_start:date|None=None
    usd_per_unit:Decimal=Field(default=Decimal('1'),gt=0,allow_inf_nan=False)
    fx_source_url:str|None=None
    fx_as_of:date|None=None
    source_url:str=Field(max_length=2000)
    publisher:str=Field(min_length=2,max_length=150)
    reviewed:Literal[True]

    @model_validator(mode='after')
    def valid(self):
        if not safe_url(self.source_url):
            raise ValueError('Provide an http/https source URL')
        if self.as_of>date.today():
            raise ValueError('Future financial observations are not accepted')
        if self.currency=='USD' and self.usd_per_unit!=1:
            raise ValueError('USD observations require an exchange rate of one')
        if self.currency!='USD' and (not safe_url(self.fx_source_url) or not self.fx_as_of or abs((self.fx_as_of-self.as_of).days)>7):
            raise ValueError('Non-USD amounts require a sourced FX rate dated within seven days of the observation')
        if self.metric=='net_profit' and (not self.period_start or not 330<=(self.as_of-self.period_start).days<=400):
            raise ValueError('Net profit qualification requires an annual reporting period, not a quarter')
        if self.metric=='valuation' and self.amount<=0:
            raise ValueError('Valuation must be positive')
        return self


def record(entity_id,observation,*,source_class='user_reviewed'):
    payload=observation.model_dump(mode='json')
    digest=hashlib.sha256(json.dumps([entity_id,payload],sort_keys=True).encode()).hexdigest()[:24]
    row={**payload,'id':'financial-'+digest,'entity_id':entity_id,'amount_usd':str(observation.amount*observation.usd_per_unit),
         'source_class':source_class,'observed_at':datetime.now(timezone.utc).isoformat()}
    existing=db.get('financial',row['id'])
    if existing:
        row=existing
    else:
        db.put('financial',row)
    event_id='financial-observation-'+digest
    if not db.get('event',event_id):
        company=db.get('entity',entity_id) or {'name':entity_id}
        summary=f"Recorded {row['metric']} for {company['name']}: {row['amount']} {row['currency']} (USD {row['amount_usd']}) as of {row['as_of']}. "
        if row.get('period_start'):summary+=f"Annual reporting period starts {row['period_start']}. "
        summary+='Source class: '+row['source_class']+'. This financial observation does not establish an investment or a future strategy.'
        db.put('event',{'id':event_id,'entity_id':entity_id,'entities':[entity_id],
            'title':company['name']+': '+row['metric'].replace('_',' ')+' observation','summary':summary,'financial_id':row['id'],
            'published_at':row['observed_at'],'observed_at':row['observed_at'],'effective_from':row['as_of'],
            'source_id':'sec' if row['source_class']=='primary_regulatory' else 'user-review',
            'source_name':row['publisher'],'source_url':row['source_url'],'event_type':'Financial observation','priority':'Unranked',
            'status':'Source-backed financial observation','demo':False,'evidence':[{'id':event_id+'-evidence','text':summary,
                'url':row['source_url'],'publisher':row['publisher'],'kind':'financial statement',**evidence.envelope(row['source_class'])}]})
    return row


def qualification(entity_id,*,today=None):
    today=today or date.today()
    observations=[row for row in db.records('financial') if row['entity_id']==entity_id]
    latest={}
    for row in sorted(observations,key=lambda item:(item['as_of'],item['observed_at'])):
        if row.get('status') in ('Disputed','Retracted'):
            continue
        latest[row['metric']]=row
    current=[]
    stale=[]
    for row in latest.values():
        days=(today-date.fromisoformat(row['as_of'])).days
        (current if days<=(120 if row['metric']=='valuation' else 550) else stale).append(row)
    qualifying=[row for row in current if Decimal(row['amount_usd'])>Decimal('500000000')]
    return {'entity_id':entity_id,'status':'qualified' if qualifying else ('below_threshold' if current else ('stale' if stale else 'unverified')),
            'threshold_usd':'500000000','rule':'valuation OR annual net profit strictly greater than USD 500 million',
            'supporting':qualifying,'latest':list(latest.values()),'observations':observations,
            'meaning':'Supported by recorded sources and their review class; not an independent financial audit.'}
