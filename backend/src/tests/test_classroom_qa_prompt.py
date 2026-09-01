from __future__ import annotations

import json

import pytest

from app.services.classroom_qa_prompt import (
    ClassroomQaAnswerError,
    StaleClassroomCheckpointError,
    build_classroom_qa_context,
    build_classroom_qa_messages,
    parse_classroom_qa_answer,
    select_relevant_classroom_sections,
)


@pytest.fixture
def material() -> dict:
    return {
        'title': '算法课堂',
        'scenes': [
            {
                'id': 'scene-1',
                'title': '前置知识',
                'actions': [
                    {'id': 'speech-1a', 'type': 'speech', 'text': '第一页第一句'},
                    {'id': 'speech-1b', 'type': 'speech', 'text': '第一页倒数第三句'},
                    {'id': 'speech-1c', 'type': 'speech', 'text': '第一页倒数第二句'},
                    {'id': 'speech-1d', 'type': 'speech', 'text': '第一页最后一句'},
                ],
            },
            {
                'id': 'scene-2',
                'title': '快速排序',
                'actions': [
                    {'id': 'speech-2a', 'type': 'speech', 'text': '第二页第一句'},
                    {'id': 'speech-2b', 'type': 'speech', 'text': '第二页第二句'},
                    {'id': 'spot-2c', 'type': 'spotlight', 'elementId': 'pivot'},
                    {'id': 'speech-2d', 'type': 'speech', 'text': '第二页第三句'},
                ],
            },
        ],
    }


def active_checkpoint(**overrides) -> dict:
    value = {
        'scene_id': 'scene-2',
        'scene_index': 1,
        'action_index': 1,
        'action_id': 'speech-2b',
        'phase': 'executing_action',
        'page_revision': 4,
    }
    value.update(overrides)
    return value


def test_context_is_reconstructed_from_trusted_material(material):
    history = [
        {
            'question': f'历史问题 {index}',
            'answer_text': f'历史回答 {index}',
        }
        for index in range(8)
    ]

    context = build_classroom_qa_context(
        material=material,
        checkpoint=active_checkpoint(),
        recent_turns=history,
    )

    assert context.completed_speech == ('第二页第一句',)
    assert context.interrupted_speech == '第二页第二句'
    assert context.previous_scene_speech == (
        '第一页倒数第三句',
        '第一页倒数第二句',
        '第一页最后一句',
    )
    assert len(context.recent_turns) == 6
    assert context.recent_turns[0]['question'] == '历史问题 2'


@pytest.mark.parametrize(
    'checkpoint',
    [
        active_checkpoint(scene_id='wrong-scene'),
        active_checkpoint(scene_index=0),
        active_checkpoint(action_index=99),
        active_checkpoint(action_id='wrong-action'),
        active_checkpoint(
            action_index=2,
            action_id='spot-2c',
            phase='executing_action',
        ),
    ],
)
def test_context_rejects_stale_or_non_speech_interruption(material, checkpoint):
    with pytest.raises(StaleClassroomCheckpointError):
        build_classroom_qa_context(
            material=material,
            checkpoint=checkpoint,
            recent_turns=[],
        )


def test_prompt_limits_agent_to_focused_json_answer(material):
    context = build_classroom_qa_context(
        material=material,
        checkpoint=active_checkpoint(),
        recent_turns=[],
    )

    messages = build_classroom_qa_messages(question='为什么选择基准值？', context=context)

    assert messages[0]['role'] == 'system'
    assert '只回答学生当前问题' in messages[0]['content']
    assert '只输出 JSON' in messages[0]['content']
    assert '第二页第二句' in messages[1]['content']
    assert '为什么选择基准值？' in messages[1]['content']
    assert '课程知识库参考' not in messages[1]['content']
    assert 'RAG' not in messages[0]['content']
    assert not hasattr(context, 'rag_answer')


def test_prompt_can_retrieve_content_from_a_later_classroom_scene(material):
    material['scenes'].append(
        {
            'id': 'scene-3',
            'title': '哈希表冲突处理',
            'content': {
                'summary': '开放寻址会在发生哈希冲突时继续探测空槽。',
                'details': ['链地址法把同一桶中的元素组织成链表。'],
            },
            'actions': [
                {'id': 'speech-3a', 'type': 'speech', 'text': '还可以通过再哈希缓解聚集。'},
            ],
        }
    )
    checkpoint = {
        'scene_id': 'scene-1',
        'scene_index': 0,
        'action_index': 0,
        'action_id': 'speech-1a',
        'phase': 'executing_action',
        'page_revision': 1,
    }

    context = build_classroom_qa_context(
        material=material,
        checkpoint=checkpoint,
        recent_turns=[],
    )

    assert any('哈希冲突' in section for section in context.full_classroom_sections)
    selected = select_relevant_classroom_sections(
        '后面如何处理哈希冲突？',
        context.full_classroom_sections,
    )
    assert any('开放寻址' in section for section in selected)
    messages = build_classroom_qa_messages(
        question='后面如何处理哈希冲突？',
        context=context,
    )
    assert '哈希冲突' in messages[-1]['content']


@pytest.mark.parametrize(
    ('raw', 'expected_answer', 'expected_transition'),
    [
        (
            json.dumps(
                {
                    'answer_text': '基准值用于划分数据。',
                    'transition_text': '下面继续观察划分过程。',
                },
                ensure_ascii=False,
            ),
            '基准值用于划分数据。',
            '下面继续观察划分过程。',
        ),
        (
            '```json\n{"answer_text":"围栏回答","transition_text":"围栏衔接"}\n```',
            '围栏回答',
            '围栏衔接',
        ),
        (
            '  这是纯文本回答。  ',
            '这是纯文本回答。',
            '好，我们回到刚才“快速排序”的讲解。',
        ),
    ],
)
def test_answer_parser_supports_json_fences_and_text_fallback(
    raw,
    expected_answer,
    expected_transition,
):
    assert parse_classroom_qa_answer(raw, scene_title='快速排序') == (
        expected_answer,
        expected_transition,
    )


def test_answer_parser_rejects_empty_and_clamps_lengths():
    with pytest.raises(ClassroomQaAnswerError):
        parse_classroom_qa_answer('   ', scene_title='快速排序')

    answer, transition = parse_classroom_qa_answer(
        json.dumps({'answer_text': '答' * 1300, 'transition_text': '接' * 200}),
        scene_title='快速排序',
    )
    assert len(answer) == 1200
    assert len(transition) == 120
