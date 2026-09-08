import json
from types import SimpleNamespace
import pytest
from app.chat.harness.reviewed_report import (
    CRITERIA, ReportReviewFailed, digest, generate_reviewed_report, verified_review,
)

CHAPTERS=[{'title':x,'points':['解释与实例']} for x in ('概念','例子','检查')]
BODY='\n\n'.join('## '+c['title']+'\n\n'+('这是展开的正文解释，包含具体的例子和推理。'*15) for c in CHAPTERS)

def review(passed=True):
    return {'checks':[{'criterion':c,'passed':passed,'reason':'已检查对应正文的位置与依据。'} for c in sorted(CRITERIA)],
            'blocking_issues':[] if passed else ['第二章例子与结论矛盾，需要修正。'], 'suggestions':['可适当补充练习。']}

class Gateway:
    def __init__(self, reviews):
        self.reviews=iter(reviews)
        self.writes=[]
    def chat(self, messages, **kwargs):
        payload=json.loads(messages[-1]['content'])
        if 'schema' in payload:
            return json.dumps(next(self.reviews))
        self.writes.append(payload)
        return BODY + ('\n修订了例子。' if payload['feedback'] else '')

def payload():
    return SimpleNamespace(subject='递归终止条件',harness_chapters=CHAPTERS,
                           harness_organization={'objectives':['能够识别终止条件']},focus='完整报告')

def test_rewrite_is_reviewed_again_and_hash_bound():
    gateway=Gateway([review(False),review(True)])
    body,state=generate_reviewed_report(payload(),gateway)
    assert len(gateway.writes)==2 and gateway.writes[1]['feedback']
    assert gateway.writes[0]['specification']['organization']['objectives']
    artifact={'content':body,'generation_state':state}
    assert verified_review(artifact)
    assert state['report_review']['version']==2
    assert len(state['report_review']['history'])==2
    assert not verified_review({**artifact,'content':body+' changed'})

def test_failed_review_never_returns_publishable_artifact():
    gateway=Gateway([review(False)]*3)
    with pytest.raises(ReportReviewFailed,match='after_two_revisions'):
        generate_reviewed_report(payload(),gateway)
    assert len(gateway.writes)==3

def test_malformed_review_does_not_implicitly_pass():
    with pytest.raises(ReportReviewFailed,match='response_invalid'):
        generate_reviewed_report(payload(),Gateway([{'checks':[]}]))
    assert not verified_review({'content':BODY})

def test_incomplete_or_failed_criteria_cannot_pass():
    bad=review(True)
    bad['checks'][0]['passed']=False
    gateway=Gateway([bad]*3)
    with pytest.raises(ReportReviewFailed):
        generate_reviewed_report(payload(),gateway)


def test_harness_adapter_runs_reviewed_pipeline(monkeypatch):
    from app.services.generation_task_handlers import _AgentReportGenerationAdapter
    from app.chat.harness import reviewed_report
    calls=[]
    def generate(value):
        calls.append(value)
        return BODY, {'report_review':{'decision':'pass'}}
    monkeypatch.setattr(reviewed_report,'generate_reviewed_report',generate)
    value=payload()
    value.harness_outline_id='outline-test'
    result=_AgentReportGenerationAdapter().generate(value,job_id='job',config_snapshot_id='snapshot')
    assert calls==[value] and result['artifacts'][0]['generation_state']['report_review']['decision']=='pass'


def test_publish_guard_rejects_unreviewed_harness_report():
    from app.services.generation_task_handlers import GenerationTaskHandler
    handler=object.__new__(GenerationTaskHandler)
    class Storage:
        def save_generated_material(self, **kwargs):
            pytest.fail('unreviewed report must not be published')
    handler.course_storage_manager=Storage()
    with pytest.raises(ValueError,match='review_missing_or_stale'):
        handler._publish_artifact(command={'config':{'harness_outline_id':'outline'}},
            context=None,resource_type='report',execution_context=None,
            result={'artifacts':[{'artifact_type':'report','content':BODY}]})


def test_review_failure_has_a_stable_task_failure_code(monkeypatch):
    from app.services.generation_task_handlers import _AgentReportGenerationAdapter
    from app.services.durable_task_handlers import DurableTaskExecutionError
    from app.chat.harness import reviewed_report
    def fail(value):
        raise ReportReviewFailed('review rejected')
    monkeypatch.setattr(reviewed_report,'generate_reviewed_report',fail)
    value=payload()
    value.harness_outline_id='outline-test'
    with pytest.raises(DurableTaskExecutionError) as error:
        _AgentReportGenerationAdapter().generate(value,job_id='job',config_snapshot_id='snapshot')
    assert error.value.code=='REPORT_REVIEW_FAILED'


def test_external_feedback_is_carried_into_revision_and_recorded():
    gateway=Gateway([review(True)])
    body,state=generate_reviewed_report(payload(),gateway,initial_body=BODY,
        initial_feedback=['修正问题规模与调用栈深度的混淆。'])
    assert gateway.writes[0]['previous_draft']==BODY
    assert gateway.writes[0]['feedback']==['修正问题规模与调用栈深度的混淆。']
    assert state['report_review']['external_review']['previous_content_sha256']==digest(BODY)
    assert verified_review({'content':body,'generation_state':state})


def test_writer_receives_current_execution_and_confirmed_facts():
    value = payload()
    value.focus = '先只给大纲'
    value.harness_execution_context = {'stage': 'write_and_review_report', 'decision': {'user_message': 'Go ahead'},
                                       'working_memory': {'confirmed_facts': ['面向初学者，约1000字']}}
    gateway = Gateway([review(True)])
    generate_reviewed_report(value, gateway)
    specification = gateway.writes[0]['specification']
    assert specification['current_execution']['decision']['user_message'] == 'Go ahead'
    assert specification['current_execution']['working_memory']['confirmed_facts']
