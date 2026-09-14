import copy
import json
import pytest
from app.services.course_knowledge_proposals import _effective_outline_config, generate_proposal, select_proposal, ProposalSelection, validate_proposal, validate_proposal_against_intent
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
    def __init__(self, output): self.output = output; self.calls = []
    def complete(self, messages, **__):
        self.calls.append(messages)
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


def test_compact_tiered_outline_expands_to_three_stable_options():
    repo = Repo()
    repo.build['config'].update(target_module_count=1, target_points_per_module=1)
    tiered = graph(extra=True)
    tiered['children'][0]['children'][0]['data']['tier'] = 'brief'
    tiered['children'][0]['children'][1]['data']['tier'] = 'complete'
    generated = generate_proposal(
        'c', 'b', expected_revision=1, requirements='本科课程',
        owner_user_id='t', repository=repo,
        adapter=Model({'summary': '按学习深度分层', 'tiered_root': tiered}),
    )

    options = generated['knowledge_proposal']['options']
    assert [item['id'] for item in options] == ['brief', 'standard', 'complete']
    assert [item['metrics']['leaf_count'] for item in options] == [1, 1, 2]
    assert options[0]['root']['children'][0]['children'][0]['id'] == 'a'
    assert options[2]['root']['children'][0]['children'][0]['id'] == 'a'


def test_compact_tiered_outline_deterministically_trims_model_overrun():
    repo = Repo()
    repo.build['config'].update(target_module_count=1, target_points_per_module=2)
    tiered = graph(extra=True)
    tiered['children'][0]['children'].extend([
        {"id": "c", "label": "函数", "data": {"type": "knowledge_point", "summary": "函数", "tier": "standard"}, "children": []},
        {"id": "d", "label": "数组", "data": {"type": "knowledge_point", "summary": "数组", "tier": "complete"}, "children": []},
    ])
    tiered['children'][0]['children'][0]['data']['tier'] = 'brief'
    tiered['children'][0]['children'][1]['data']['tier'] = 'standard'

    generated = generate_proposal(
        'c', 'b', expected_revision=1, requirements='本科课程',
        owner_user_id='t', repository=repo,
        adapter=Model({'summary': '模型多给了节点', 'tiered_root': tiered}),
    )

    assert [item['metrics']['leaf_count'] for item in generated['knowledge_proposal']['options']] == [2, 2, 3]


def test_explicit_scope_adapts_default_module_count_without_expanding_leaf_budget():
    config = _effective_outline_config(
        {"preset": "standard", "target_module_count": 4, "target_points_per_module": 4},
        {"scope": {"include_topics": ["进程", "调度", "同步", "死锁", "虚拟内存"]}},
        None,
    )

    assert config == {
        "preset": "custom",
        "target_module_count": 5,
        "target_points_per_module": 3,
    }


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


def test_intent_contract_is_persisted_and_reaches_planning_and_execution():
    repo = Repo(graph(True))
    raw = {"items": [{"kind": "add_node", "target_id": "module", "title": "Linux cgroups 与容器资源隔离",
                      "reason": "新增资源隔离知识点", "materials": ["Docker 配置案例", "带解析练习"],
                      "evidence_document_ids": []}]}
    model = Model(raw)
    requirements = ("新增知识点“Linux cgroups 与容器资源隔离”，提供 1 个 Docker 配置案例和 3 道带解析练习；"
                    "优先 Linux Kernel 与 Docker 官方资料，保留现有目录和全部已有资料。")

    generated = generate_proposal('c', 'b', expected_revision=1, requirements=requirements,
                                  owner_user_id='t', repository=repo, adapter=model)

    intent = generated['intent_contract']
    assert intent['source_policy']['preferred_domains'] == ['docs.docker.com', 'docs.kernel.org']
    assert {item['type']: item['count'] for item in intent['deliverables']} == {
        'worked_case': 1, 'exercise_with_solution': 3,
    }
    planning_payload = json.loads(model.calls[0][1]['content'])
    assert planning_payload['intent'] == intent

    selected = select_proposal('c', 'b', ProposalSelection(
        expected_revision=2,
        item_ids=[generated['knowledge_proposal']['items'][0]['id']],
    ), repository=repo)
    topic = execution_topics(selected)[0]
    assert topic['source_policy']['preferred_domains'] == ['docs.docker.com', 'docs.kernel.org']
    assert {item['type']: item['count'] for item in topic['deliverables']} == {
        'worked_case': 1, 'exercise_with_solution': 3,
    }


def test_vague_depth_and_source_requirements_require_clarification_before_model_call():
    repo = Repo()
    model = Model({})

    with pytest.raises(ValueError, match='需要补充确认'):
        generate_proposal('c', 'b', expected_revision=1,
                          requirements='内容讲深一点，资料质量要好一些。',
                          owner_user_id='t', repository=repo, adapter=model)

    assert model.calls == []


def test_deterministic_intent_check_rejects_omitted_and_excluded_topics():
    proposal = validate_proposal({
        "summary": "补充建议",
        "items": [{"kind": "add_node", "target_id": "module", "title": "进程调度",
                   "reason": "补充调度", "materials": [], "evidence_document_ids": []}],
    }, Repo(graph(True)).build, [])

    with pytest.raises(ValueError, match="遗漏教师指定主题"):
        validate_proposal_against_intent(proposal, {
            "scope": {"include_topics": ["Linux cgroups"], "exclude_topics": []}
        })
    with pytest.raises(ValueError, match="明确排除"):
        validate_proposal_against_intent(proposal, {
            "scope": {"include_topics": [], "exclude_topics": ["进程调度"]}
        })


def test_single_requested_new_topic_rejects_materials_attached_to_old_leaf():
    proposal = {
        "mode": "supplement",
        "items": [
            {"kind": "add_node", "target_id": "process-module",
             "title": "Linux cgroups 与容器资源隔离", "materials": ["官方资料"]},
            {"kind": "materials", "target_id": "proc-model",
             "title": "进程机制补充", "materials": ["Docker 案例"]},
        ],
    }

    with pytest.raises(ValueError, match="合并写入 add_node.materials"):
        validate_proposal_against_intent(proposal, {
            "scope": {
                "include_topics": ["Linux cgroups 与容器资源隔离"],
                "exclude_topics": [],
            }
        })


def test_cgroups_increment_rejects_virtual_memory_parent_and_accepts_process_branch():
    baseline = {
        "id": "root",
        "label": "操作系统",
        "data": {"type": "course"},
        "children": [
            {
                "id": "process-module",
                "label": "进程与线程",
                "data": {
                    "type": "knowledge_module",
                    "summary": "进程、线程与系统调用",
                },
                "children": [
                    {"id": "process-leaf", "label": "进程状态", "children": []}
                ],
            },
            {
                "id": "memory-module",
                "label": "虚拟内存",
                "data": {
                    "type": "knowledge_module",
                    "summary": "分页、缺页与地址转换",
                },
                "children": [
                    {"id": "memory-leaf", "label": "分页", "children": []}
                ],
            },
        ],
    }
    intent = {"scope": {"include_topics": ["Linux cgroups 与容器资源隔离"]}}
    proposal = {
        "mode": "supplement",
        "items": [
            {
                "kind": "add_node",
                "target_id": "memory-module",
                "title": "Linux cgroups 与容器资源隔离",
                "materials": ["Docker 案例"],
            }
        ],
    }

    with pytest.raises(ValueError, match="语义不一致.*process-module"):
        validate_proposal_against_intent(proposal, intent, baseline)

    proposal["items"][0]["target_id"] = "process-module"
    assert validate_proposal_against_intent(proposal, intent, baseline) is proposal


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


def test_invalid_target_feedback_includes_allowed_ids_and_self_repairs():
    repo = Repo(graph())

    class RepairingModel:
        def __init__(self):
            self.planning_calls = 0
            self.feedback = None

        def complete(self, messages, **kwargs):
            if '独立检查' in messages[0]['content']:
                return json.dumps({'approved': True, 'issues': []}), 'test'
            self.planning_calls += 1
            if self.planning_calls == 1:
                return json.dumps({
                    'items': [{'kind': 'add_node', 'target_id': 'invented-module',
                               'title': 'Linux cgroups', 'reason': '教师要求新增',
                               'materials': ['官方资料'], 'evidence_document_ids': []}],
                }), 'test'
            self.feedback = json.loads(messages[-1]['content'])
            return json.dumps({
                'items': [{'kind': 'add_node', 'target_id': 'module',
                           'title': 'Linux cgroups', 'reason': '教师要求新增',
                           'materials': ['官方资料'], 'evidence_document_ids': []}],
            }), 'test'

    model = RepairingModel()
    result = generate_proposal(
        'c', 'b', expected_revision=1, requirements='新增 Linux cgroups',
        owner_user_id='t', repository=repo, adapter=model,
    )

    assert model.planning_calls == 2
    assert any(item['id'] == 'module' for item in model.feedback['valid_targets'])
    assert result['knowledge_proposal']['items'][0]['target_id'] == 'module'


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
