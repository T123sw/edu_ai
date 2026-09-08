import copy
import json
import pytest
from app.services.course_knowledge_proposals import generate_proposal, select_proposal, ProposalSelection, validate_proposal
from app.persistence.postgres_knowledge_repository import KnowledgeBuildRevisionConflict
from app.services.course_knowledge_source_discovery import execution_topics
from app.services.course_knowledge_plan_builder import _published_graph


def graph(extra=False):
    leaves = [{"id": "a", "label": "循环结构", "data": {"type": "knowledge_point", "summary": "理解循环", "document_ids": ["old"]}, "children": []}]
    if extra:
        leaves.append({"id": "b", "label": "递归", "data": {"type": "knowledge_point", "summary": "理解递归"}, "children": []})
    return {"id": "root", "label": "计算思维", "data": {"type": "course", "summary": "课程"}, "children": [
        {"id": "module", "label": "程序设计", "data": {"type": "knowledge_module", "summary": "程序设计基础"}, "children": leaves}]}


class Repo:
    def __init__(self, baseline=None):
        self.version = 1 if baseline else None
        self.build = {"library_id": "c", "build_id": "b", "revision": 1, "baseline_graph_version": self.version,
                      "baseline_graph": baseline, "config": {"maximum_ai_materials_per_leaf": 1}, "textbooks": []}
    def get_build(self, _): return copy.deepcopy(self.build)
    def get_latest_graph_version(self, _): return {"version": self.version}
    def list_documents(self, _): return [{"id": "old", "name": "已有讲义", "scope_id": "a", "status": "ready", "chunk_count": 3, "source_type": "web"}]
    def update_build_draft(self, _, expected_revision, changes, phase):
        if self.build["revision"] != expected_revision: raise KnowledgeBuildRevisionConflict('stale')
        self.build.update(changes, revision=expected_revision + 1, graph_confirmed_at=None)
        return copy.deepcopy(self.build)


class Model:
    def __init__(self, output): self.output = output
    def complete(self, messages, **__):
        if '独立检查' in messages[0]['content']: return '{"approved":true,"issues":[]}', 'test'
        return json.dumps(self.output, ensure_ascii=False), 'test'


def test_three_outlines_preserve_core_and_selection_is_not_confirmation():
    repo = Repo()
    raw = {"core_topics": ["循环结构"], "options": [{"level": level, "description": level, "root": graph(level == "complete")} for level in ['brief','standard','complete']]}
    result = generate_proposal('c','b', expected_revision=1, requirements='本科课程', owner_user_id='t', repository=repo, adapter=Model(raw))
    assert len(result['knowledge_proposal']['options']) == 3
    result = select_proposal('c','b', ProposalSelection(expected_revision=2, option_id='complete'), repository=repo)
    assert result['selected_topic_ids'] == ['a','b']
    assert not result['graph_confirmed_at']
    assert result['graph_draft'] == graph(True)
    with pytest.raises(KnowledgeBuildRevisionConflict):
        select_proposal('c','b', ProposalSelection(expected_revision=2, option_id='brief'), repository=repo)


def test_supplement_only_selected_topics_preserves_entire_graph_and_old_documents():
    repo = Repo(graph(True))
    raw = {"items": [{"kind":"materials", "target_id":"a", "title":"循环结构", "reason":"根据标题推断缺少练习", "materials":["边界练习"], "evidence_document_ids":["old"]},
                     {"kind":"materials", "target_id":"b", "title":"递归", "reason":"无关联资料", "materials":["讲义"]}]}
    result = generate_proposal('c','b', expected_revision=1, requirements='补练习', owner_user_id='t', repository=repo, adapter=Model(raw))
    item = result['knowledge_proposal']['items'][0]
    result = select_proposal('c','b', ProposalSelection(expected_revision=2, item_ids=[item['id']]), repository=repo)
    assert result['graph_draft'] == graph(True)
    assert [t['topic_id'] for t in execution_topics(result)] == ['a']
    assert execution_topics(result)[0]['target_units'] == 2
    published = _published_graph(result, [{'document_id':'new', 'scope_id':'a'}])
    assert published['children'][0]['children'][0]['data']['document_ids'] == ['old','new']
    assert len(published['children'][0]['children']) == 2


def test_baseline_change_blocks_plan_and_unknown_evidence_is_rejected():
    repo = Repo(graph())
    repo.version = 2
    with pytest.raises(KnowledgeBuildRevisionConflict):
        generate_proposal('c','b', expected_revision=1, requirements='', owner_user_id='t', repository=repo)
    with pytest.raises(ValueError, match='不存在的资料'):
        validate_proposal({'items':[{'kind':'materials','target_id':'a','reason':'缺少','evidence_document_ids':['fake']}]}, {'baseline_graph':graph()}, [])


def test_revision_feedback_invalidates_selected_plan_and_confirmation():
    repo = Repo(graph())
    repo.build.update(graph_confirmed_at='old', proposal_selection={'old':True}, selected_topic_ids=['a'])
    result = generate_proposal('c','b', expected_revision=1, requirements='暂不补充', owner_user_id='t', repository=repo, adapter=Model({'items':[]}))
    assert result['graph_draft'] is None
    assert result['proposal_selection'] is None
    assert result['selected_topic_ids'] is None
    assert not result['graph_confirmed_at']


def test_model_review_can_reject_scope_expansion_and_request_repair():
    repo = Repo(graph())
    class ReviewedModel:
        def __init__(self): self.reviews = 0
        def complete(self, messages, **kwargs):
            if '独立检查' in messages[0]['content']:
                self.reviews += 1
                return json.dumps({'approved': self.reviews > 1, 'issues': [] if self.reviews > 1 else ['仅补练习，不应新增目录']}), 'test'
            return json.dumps({'items': []}), 'test'
    model = ReviewedModel()
    result = generate_proposal('c','b', expected_revision=1, requirements='仅补练习', owner_user_id='t', repository=repo, adapter=model)
    assert model.reviews == 2
    assert result['knowledge_proposal']['review']['approved']


def test_cross_course_build_and_invalid_item_selection_fail_closed():
    repo = Repo(graph())
    with pytest.raises(ValueError, match='不存在'):
        generate_proposal('other','b', expected_revision=1, requirements='', owner_user_id='t', repository=repo, adapter=Model({}))
    generate_proposal('c','b', expected_revision=1, requirements='', owner_user_id='t', repository=repo, adapter=Model({'items':[]}))
    with pytest.raises(ValueError, match='有效'):
        select_proposal('c','b', ProposalSelection(expected_revision=2, item_ids=['forged']), repository=repo)


def test_proposal_api_requires_course_generation_access(tmp_path, monkeypatch):
    from tests.course_api_test_support import CourseApiTestFactory
    from app.api import courses
    factory = CourseApiTestFactory(tmp_path, monkeypatch)
    monkeypatch.setattr(courses, 'generate_proposal', lambda *a, **k: pytest.fail('unauthorized model execution'))
    response = factory.client_for('outsider', 'teacher').post('/api/courses/course-1/knowledge-builds/b/proposal', json={'expected_revision':1})
    assert response.status_code == 403
