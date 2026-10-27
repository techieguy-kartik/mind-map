"""Explicitly illustrative fixtures; no synthetic event is a real-world assertion."""
from datetime import datetime, timedelta, timezone


def seed_data(demo=True):
    companies = [
        ('reliance', 'Reliance Industries', 'RI', 'India', 'Energy', 'Reliance', '#ad713d', ['Reliance Industries', 'RIL']),
        ('jio', 'Jio Platforms', 'J', 'India', 'Telecom & AI', 'Reliance', '#6573bc', ['Jio Platforms']),
        ('tata-sons', 'Tata Sons', 'T', 'India', 'Holding company', 'Tata', '#427b9b', ['Tata Sons']),
        ('tata-power', 'Tata Power', 'TP', 'India', 'Clean energy', 'Tata', '#3b8b72', ['Tata Power']),
        ('tata-motors', 'Tata Motors', 'TM', 'India', 'Mobility', 'Tata', '#59748f', ['Tata Motors']),
        ('tcs', 'Tata Consultancy Services', 'TC', 'India', 'Enterprise AI', 'Tata', '#8d689d', ['Tata Consultancy Services', 'TCS']),
        ('adani', 'Adani Enterprises', 'AE', 'India', 'Infrastructure', 'Adani', '#6d81a7', ['Adani Enterprises']),
        ('mahindra', 'Mahindra & Mahindra', 'M', 'India', 'Mobility', 'Mahindra', '#9f635c', ['Mahindra & Mahindra', 'Mahindra and Mahindra']),
        ('bharti', 'Bharti Airtel', 'BA', 'India', 'Telecom', 'Bharti', '#b26257', ['Bharti Airtel']),
        ('jsw', 'JSW Steel', 'JS', 'India', 'Materials', 'JSW', '#667cb0', ['JSW Steel']),
        ('tesla', 'Tesla', 'TS', 'United States', 'Mobility & AI', 'Tesla', '#9a5c5c', ['Tesla']),
        ('nvidia', 'NVIDIA', 'NV', 'United States', 'AI & compute', 'NVIDIA', '#75934b', ['NVIDIA']),
        ('microsoft', 'Microsoft', 'MS', 'United States', 'AI & cloud', 'Microsoft', '#5b83a6', ['Microsoft']),
        ('alphabet', 'Alphabet', 'G', 'United States', 'AI & cloud', 'Alphabet', '#9a7853', ['Alphabet']),
        ('siemens', 'Siemens', 'S', 'Germany', 'Industrial technology', 'Siemens', '#4c8985', ['Siemens']),
        ('samsung', 'Samsung Electronics', 'SE', 'South Korea', 'Semiconductors', 'Samsung', '#646b9f', ['Samsung Electronics']),
    ]
    entities = [dict(id=i, name=n, initials=initials, country=c, sector=s, group=g, color=color,
                     aliases=aliases, type='company', qualification='Not yet verified',
                     description=f'{n} is a candidate in the {g} research watchlist. Financial qualification and current leadership require source verification.',
                     demo=False) for i,n,initials,c,s,g,color,aliases in companies]
    entities += [
        dict(id='mukesh-ambani',name='Mukesh Ambani',initials='MA',country='India',sector='Business leadership',group='Professional profile',color='#957250',aliases=['Mukesh Ambani'],type='person',qualification='Not applicable',description='Professional-profile registry entry. Current roles, investments and statements must be attached with dated evidence.',demo=False),
        dict(id='elon-musk',name='Elon Musk',initials='EM',country='United States',sector='Business leadership',group='Professional profile',color='#737a94',aliases=['Elon Musk'],type='person',qualification='Not applicable',description='Professional-profile registry entry. Keep personal activity distinct from actions by any company.',demo=False),
        dict(id='tata-trusts',name='Tata Trusts',initials='TT',country='India',sector='Philanthropy',group='Tata',color='#6d8e9a',aliases=['Tata Trusts'],type='trust',qualification='Not applicable',description='Trust umbrella registry entry. Ownership and control require precisely scoped evidence; individual trusts may require separate legal entities.',demo=False),
    ]
    if not demo:
        return entities, [], [], []
    entities += [
        dict(id='demo-power',name='Grid capacity',initials='GC',country='Global',sector='Infrastructure',group='Concept',color='#a08c55',aliases=[],type='technology',qualification='Not applicable',description='Illustrative technology node connecting the demonstration events.',demo=True),
        dict(id='demo-compute',name='AI infrastructure',initials='AI',country='Global',sector='AI',group='Concept',color='#82649f',aliases=[],type='technology',qualification='Not applicable',description='Illustrative thematic node, not a verified company commitment.',demo=True),
        dict(id='demo-mobility',name='Electric mobility',initials='EV',country='Global',sector='Mobility',group='Concept',color='#517e79',aliases=[],type='technology',qualification='Not applicable',description='Illustrative technology node.',demo=True),
    ]
    now = datetime.now(timezone.utc)
    specs = [
        ('demo-1','jio','AI infrastructure moves from discussion to execution','Partnership','High','A fictional partnership scenario demonstrates how Atlas connects an announcement to infrastructure dependencies. No real partnership is asserted.', ['jio','reliance','demo-compute'], 1),
        ('demo-2','tata-power','A power commitment changes the infrastructure picture','Capital commitment','High','An illustrative grid-capacity commitment. The amount, counterparty and closing status would require primary evidence in a real investigation.', ['tata-power','demo-power','demo-compute'], 3),
        ('demo-3','tesla','A public appearance creates a follow-up question','Public appearance','Medium','A fictional conference appearance illustrates the difference between attending an event and holding a verified meeting.', ['tesla','demo-mobility'], 5),
        ('demo-4','nvidia','Compute demand meets an energy constraint','Research signal','High','An illustrative cross-sector signal. It demonstrates a hypothesis about power availability without asserting a current NVIDIA plan.', ['nvidia','demo-compute','demo-power'], 8),
        ('demo-5','tata-motors','An operating milestone gives a strategy a reality check','Operational milestone','Medium','A fictional milestone used to demonstrate monitoring of actions against prior statements.', ['tata-motors','demo-mobility'], 12),
        ('demo-6','reliance','New technical roles suggest a question worth investigating','Hiring signal','Low','A synthetic hiring example. Hiring is a signal for investigation, not proof of a product launch or investment.', ['reliance','demo-compute'], 20),
    ]
    events = [dict(id=i,entity_id=e,title=t,event_type=ty,priority=p,summary=s,entities=es,
                   published_at=(now-timedelta(hours=h)).isoformat(),observed_at=now.isoformat(),
                   source_id='demo',source_name='Illustrative scenario',source_url=None,status='Illustrative',demo=True,
                   evidence=[dict(id=f'{i}-evidence',text=s,url=None,publisher='Atlas demonstration fixture',kind='synthetic')])
              for i,e,t,ty,p,s,es,h in specs]
    edges = []
    for event in events:
        for target in event['entities'][1:]:
            edges.append(dict(id=f"{event['id']}:{target}",source=event['entity_id'],target=target,
                              relation='scenario connection',event_id=event['id'],evidence=event['evidence'],
                              observed_at=event['observed_at'],status='Illustrative',demo=True))
    hypotheses = [
        dict(id='hyp-1',entity_id='jio',title='Could connectivity become an AI infrastructure platform?',status='Emerging',horizon='3–12 months',
             summary='Illustrative hypothesis: related compute and infrastructure commitments might indicate expansion beyond connectivity.',
             supporting=['demo-1','demo-6'],contradicting=['No verified customer, procurement or delivery evidence is present in this demo.'],
             alternatives=['Capacity may serve existing services rather than a new platform.','The apparent connection may be incidental.'],
             next_checks=['Find a primary procurement disclosure.','Verify the legal entity making the commitment.','Look for an actual customer or commissioning milestone.'],demo=True),
        dict(id='hyp-2',entity_id='tata-power',title='Could grid capacity become a competitive advantage for AI?',status='Insufficient',horizon='6–12 months',
             summary='Illustrative hypothesis connecting electricity infrastructure to potential compute demand.',supporting=['demo-2','demo-4'],
             contradicting=['There is no verified link between these synthetic events.'],alternatives=['Expansion could support ordinary industrial demand.'],
             next_checks=['Verify named offtake counterparties.','Separate announced capacity from commissioned capacity.'],demo=True),
    ]
    return entities, events, edges, hypotheses
