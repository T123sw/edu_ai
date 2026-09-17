from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4
import pytest
from app.course_preparation.schemas import PreparationRequest
from app.course_preparation.route_adjustment import eligible,plan,validate
from tests.course_preparation.test_delivery import ready
from tests.course_preparation.test_generation_adapter import generation


def test_existing_route_adjustment_needs_one_bounded_decision_and_no_sources(ready):
    repo,original,delivery=ready;course=delivery.commit(original).result_ref['course_id'];base=delivery.read('alice',course)
    request=PreparationRequest(request_id=uuid4(),operation='adjust_course',goal='只调整学习时长，保留原资料',
        target={'course_id':course,'base_manifest_version':1,'base_route_version':1},requested_changes=['改为20分钟'])
    assert eligible(request)
    calls=[]
    class Model:
        def decide(self,context,tools,timeout):
            calls.append(context);assert len(tools)==1 and timeout==90
            return 'save_route_adjustment',{'nodes':[{'node_id':n['node_id'],'title':n['title'],'minutes':20,'prerequisite_node_ids':[]} for n in base['nodes']]}
    stages=SimpleNamespace(_request=lambda _:request,memory=SimpleNamespace(validate=lambda *_:None),agent_factory=lambda *_:SimpleNamespace(model=Model()))
    cp=deepcopy(original.checkpoint);cp['target_snapshot']={'manifest':base};cp['route_only_adjustment']=True
    result=plan(stages,original.model_copy(update={'checkpoint':cp}))
    assert result.next_stage=='research_nodes' and len(calls)==1
    assert result.checkpoint['node_evidence']=={'tools':[]}
    assert result.checkpoint['plan']['nodes'][0]['objectives']==[o['text'] for o in base['nodes'][0]['objectives']]
    result.checkpoint['plan']['nodes'][0]['objectives']=['unauthorized']
    with pytest.raises(Exception,match='目标'):validate(request,result.checkpoint)


def test_new_content_request_does_not_take_route_only_path():
    r=PreparationRequest(request_id=uuid4(),operation='adjust_course',goal='保留原资料，只调整时长并新增知识点',
        target={'course_id':'course','base_manifest_version':1,'base_route_version':1},requested_changes=['新增知识点'])
    assert not eligible(r)
