"""Actual-framework tests run in the isolated Python 3.13 CI job."""
import json
import pytest

crewai=pytest.importorskip('crewai')

from server.intelligence.crew import analyze


class DeterministicLLM(crewai.BaseLLM):
    def __init__(self,citation='demo-1'):
        super().__init__(model='deterministic-test')
        self.calls=0
        self.citation=citation

    def supports_function_calling(self):
        return False

    def call(self,messages,**kwargs):
        self.calls+=1
        return json.dumps({'result':'Illustrative fictional hypothesis only.',
            'citations':[self.citation],'alternatives':['Routine operations.'],
            'missing_evidence':['No primary disclosure.']})


def test_three_real_crew_tasks_with_no_live_model(monkeypatch):
    monkeypatch.setenv('ATLAS_CREW_ENABLED','true')
    llm=DeterministicLLM()
    result=analyze({'entity':'Jio Platforms','question':'What changed?',
                    'evidence':json.dumps({'id':'demo-1','summary':'Synthetic example'})},llm=llm)
    assert llm.calls==3
    assert result['citations']==['demo-1']


def test_crew_rejects_unknown_evidence(monkeypatch):
    monkeypatch.setenv('ATLAS_CREW_ENABLED','true')
    with pytest.raises((ValueError,RuntimeError)):
        analyze({'entity':'Jio Platforms','question':'What changed?',
                 'evidence':json.dumps({'id':'demo-1','summary':'Synthetic example'})},llm=DeterministicLLM('invented-id'))
