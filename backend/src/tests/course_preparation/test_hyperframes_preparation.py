"""Preparation owns requirements and receipts, not video authorship."""
from types import SimpleNamespace
import copy
import pytest
from app.course_preparation.adapters.classroom import generate_classroom_draft
from app.integrations.hyperframes import generation as native
from app.integrations.hyperframes.projects import ProjectStore
from app.chat.harness.reviewed_resource import verified_resource
from tests.hyperframes.native_workflow_fixtures import Checkpoint, Runner, Runtime, Gateway


def test_preparation_uses_native_workflow_and_measured_delivery(monkeypatch,tmp_path):
    original=native.generate_content
    monkeypatch.setattr(native,'generate_content',lambda payload,**kwargs:original(payload,**kwargs,
        store=ProjectStore(tmp_path/'projects'),runtime=Runtime(),runner_factory=Runner))
    teaching={'request_goal':'用户只要视频','learning_activities':['不应强加给视频的活动']}
    result=generate_classroom_draft(SimpleNamespace(title='T',teaching_context=teaching),gateway=Gateway(),
        context=None,artifact={'resource_id':'r','spec_digest':'s'},checkpoint=Checkpoint())
    assert result['generation_state']['preparation']['generator']=='hyperframes-native-workflow'
    assert result['generation_state']['preparation']['duration']['value_minutes']==2.75/60
    assert result['generation_state']['resource_review']['decision']=='skipped'
    assert verified_resource(result,'classroom')
    changed=copy.deepcopy(result);changed['content']['timeline']['segments'][0]['narration']+='changed'
    assert not verified_resource(changed,'classroom')


def test_canceled_preparation_cannot_start_or_publish(tmp_path):
    Runner.calls=[]
    with pytest.raises(RuntimeError,match='CANCELED'):
        native.generate_content(SimpleNamespace(title='T',focus='需求'),gateway=Gateway(),
            context=SimpleNamespace(is_cancel_requested=lambda:True),artifact={'resource_id':'r'},
            runner_factory=Runner,store=ProjectStore(tmp_path/'projects'))
    assert not Runner.calls


def test_native_video_alone_can_pass_course_delivery_without_quiz_bindings(monkeypatch,tmp_path):
    from app.course_preparation.resource_alignment import validate_artifact, node_objective_issues, node_requirement_issues
    from app.course_preparation.tool_registry import digest
    original=native.generate_content
    monkeypatch.setattr(native,'generate_content',lambda payload,**kwargs:original(payload,**kwargs,
        store=ProjectStore(tmp_path/'projects'),runtime=Runtime(),runner_factory=Runner))
    teaching={'request_goal':'只要视频，不需要习题','node_id':'n1','objective_ids':['n1:o1'],
              'requirements':[{'requirement_id':'r1','text':'讲清截距'}],'requirement_ids':['r1']}
    spec={'schema_version':2,'node_id':'n1','objective_ids':['n1:o1'],'teaching_context':teaching}
    result=generate_classroom_draft(SimpleNamespace(title='截距',teaching_context=teaching),gateway=Gateway(),
        context=None,artifact={'resource_id':'r','spec_digest':digest(spec)},checkpoint=Checkpoint())
    artifact={'artifact_id':'a','resource_type':'classroom','spec':spec,'spec_digest':digest(spec),
              'content':result,'content_digest':digest(result)}
    nodes=[{'node_key':'n1','objectives':['理解截距'],'requirement_ids':['r1']}]
    validate_artifact(artifact)
    assert node_requirement_issues([artifact],nodes)==[]
    assert node_objective_issues([artifact],nodes)==[]
