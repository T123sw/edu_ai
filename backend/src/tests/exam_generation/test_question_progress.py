import asyncio
from dataclasses import replace

import pytest

from app.exam_generation.progress import question_progress
from app.exam_generation.service import ExamGenerationHandler
from app.exam_generation.sources import GenerationSources
from app.integrations.deeptutor.client import DeepTutorError
from test_generation import repo, codec, create, context, Client


def slot(seq, index, total=4):
    return {'seq': seq, 'type': 'content', 'stage': 'quizzing', 'content': 'PRIVATE ANSWER',
            'metadata': {'call_kind': 'quiz_question_emitted', 'question_index': index,
                         'total_questions': total, 'qa_pair': {'correct_answer': 'PRIVATE ANSWER'}}}


@pytest.mark.parametrize('index,total', [(-1, 4), (4, 4), (0, 0), (True, 4), ('1', 4), (0, None)])
def test_invalid_slot_counts_are_not_progress(index, total):
    assert question_progress(slot(1, index, total)) is None


def test_resume_restores_persisted_count_and_does_not_regress(repo, codec):
    row = create(repo, codec)
    published = []

    class StreamingClient(Client):
        interrupted = False

        async def internal_events(self, *, after_seq, **kwargs):
            self.cursors.append(after_seq)
            events = [
                {'seq': 1, 'type': 'stage_start', 'stage': 'quizzing'},
                slot(2, 0), slot(3, 1),
                {'seq': 4, 'type': 'thinking', 'stage': 'quizzing', 'content': 'PRIVATE REASONING'},
                slot(5, 0),  # Out-of-order duplicate must not lower progress.
                slot(6, 2), slot(7, 3),
                {'seq': 8, 'type': 'result', 'metadata': {'summary': {
                    'success': True, 'completed': 1, 'failed': 0,
                    'results': [{'qa_pair': {'correct_answer': 'PRIVATE ANSWER'}}]}}},
            ]
            for event in events:
                if event['seq'] <= after_seq:
                    continue
                yield event
                if event['seq'] == 3 and not self.interrupted:
                    self.interrupted = True
                    raise DeepTutorError(503, 'Disconnect')

    client = StreamingClient()
    handler = ExamGenerationHandler(repo, GenerationSources(), codec, lambda: client)
    ctx = replace(context(row), progress=lambda *args: published.append(args))
    with pytest.raises(DeepTutorError):
        asyncio.run(handler.run({'generation_id': row['id']}, ctx))
    assert repo.get('alice', row['id'])['question_progress'] == {'processed': 2, 'total': 4}
    assert published[-1] == (67, 'quizzing', '已处理 2/4 题，正在生成第 3 题')
    before = len(published)
    assert asyncio.run(handler.run({'generation_id': row['id']}, replace(ctx, attempt_count=2)))['saved']
    assert published[before] == published[before - 1]
    assert [p[0] for p in published] == sorted(p[0] for p in published)
    assert published[-2][0] == 95 and '4/4' in published[-2][2]
    assert published[-1] == (100, 'completed', '试卷已生成')
    assert 'PRIVATE' not in str(published)
    assert client.cursors == [0, 3]
    assert repo.get('alice', row['id'])['question_progress'] == {'processed': 4, 'total': 4}
