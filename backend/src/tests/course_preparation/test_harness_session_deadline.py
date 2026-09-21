from datetime import datetime,timezone,timedelta
from types import SimpleNamespace
import importlib
import pytest
from app.course_preparation.harness_generation import PreparationHarnessGateway
from app.course_preparation.research_agent import ResearchError

@pytest.mark.parametrize('accepted,remaining,expected',[(False,3600,'PROVIDER_TIMEOUT'),(False,10,'BUDGET_EXHAUSTED'),(True,3600,None),(True,10,'BUDGET_EXHAUSTED')])
def test_session_timeout_is_not_parent_exhaustion_and_accepted_result_survives_cleanup(monkeypatch,accepted,remaining,expected):
    module=importlib.import_module('app.course_preparation.harness_generation')
    clock=[0.0]
    monkeypatch.setattr(module,'time',SimpleNamespace(monotonic=lambda:clock[0]))
    def run(self,context,tools,*,toolset,**kwargs):
        if accepted:toolset.call('submit_resource_text',{'text':'real accepted submission'})
        clock[0]=121.0
        toolset.check()
        return toolset.result
    monkeypatch.setattr(module.HarnessPreparationAdapter,'_run',run)
    model=PreparationHarnessGateway(SimpleNamespace(),None,{},deadline=(datetime.now(timezone.utc)+timedelta(seconds=remaining)).isoformat())
    phase=model.for_phase('resource_review',context={})
    if expected:
        with pytest.raises(ResearchError,match=expected):phase.chat([{'role':'user','content':'body'}])
    else:
        assert phase.chat([{'role':'user','content':'body'}])=='real accepted submission'


@pytest.mark.parametrize('failure',['cancel','lease'])
def test_accepted_result_still_checks_cancel_and_lease_after_session_deadline(monkeypatch,failure):
    module=importlib.import_module('app.course_preparation.harness_generation')
    clock=[0.0];finished=[False]
    monkeypatch.setattr(module,'time',SimpleNamespace(monotonic=lambda:clock[0]))
    def run(self,context,tools,*,toolset,**kwargs):
        toolset.call('submit_resource_text',{'text':'accepted before cutoff'})
        clock[0]=121.0;finished[0]=True
        return toolset.result
    def guard():
        if finished[0] and failure=='lease':raise PermissionError('lease expired')
    monkeypatch.setattr(module.HarnessPreparationAdapter,'_run',run)
    model=PreparationHarnessGateway(SimpleNamespace(),None,{},
        deadline=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),
        canceled=lambda:finished[0] and failure=='cancel',guard=guard)
    with pytest.raises(ResearchError if failure=='cancel' else PermissionError):
        model.for_phase('resource_review',context={}).chat([{'role':'user','content':'body'}])
