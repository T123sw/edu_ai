from types import SimpleNamespace
import copy
from uuid import uuid4
import pytest
from tests.course_preparation.test_resource_alignment import quiz, checkpoint
from app.course_preparation.quality import QualityStages
from app.course_preparation.tool_registry import digest
from app.course_preparation.schemas import PreparationRequest


def test_missing_manifest_check_is_repaired_on_quiz_without_lowering_gate(monkeypatch):
    import app.course_preparation.quality as module
    monkeypatch.setattr(module.ResearchState,'model_validate',lambda _:SimpleNamespace(path={}))
    monkeypatch.setattr(module.ResearchAgent,'_validate_path',lambda *_:None)
    a=quiz();a['content']['generation_state']['preparation']['objective_bindings'][0]['role']='explanation'
    a['content_digest']=digest(a['content']); cp=checkpoint(a)
    cp.update(research_state={},resource_specs=[a['spec']],generation_receipts={a['spec_digest']:{}})
    request=PreparationRequest(request_id=uuid4(),operation='create_course',goal='学习加法')
    stages=QualityStages(SimpleNamespace(get=lambda **_:SimpleNamespace(request=request)),
        SimpleNamespace(read_result=lambda *_:a),SimpleNamespace(validate=lambda *_:None),
        lambda *_:pytest.fail('do not spend a model call before deterministic coverage validation'))
    context=SimpleNamespace(checkpoint=cp,owner_user_id='alice',preparation_id='prep-x')
    result=stages.review(context)
    assert result.next_stage=='repair'
    issue=result.checkpoint['quality']['issues'][0]
    assert issue['artifact_ids']==['a'] and 'n:o1' in issue['reason']


def test_fractional_duration_targets_are_valid_context_but_zero_and_nan_are_not():
    from app.course_preparation.teaching_context import TeachingContext
    from tests.course_preparation.test_generated_content_constraints import context
    assert TeachingContext.model_validate({**context(), 'resource_target_minutes': 2.37}).resource_target_minutes==2.37
    integer_context = {**context(), 'resource_target_minutes': 2}
    assert isinstance(TeachingContext.model_validate(integer_context).model_dump()['resource_target_minutes'], int)
    for value in (0,-1,float('inf'),float('nan')):
        with pytest.raises(ValueError):TeachingContext.model_validate({**context(), 'resource_target_minutes': value})
